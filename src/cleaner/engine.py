"""
清理引擎 — 编排整个清理流程。

流程（对应 1.0项目框架 核心流程）：
    1. 校验：目标存在 / 非系统保护路径 / 条目启用
    2. 扫描：rules.scan_directory 匹配规则
    3. 预览：返回待清理文件清单（GUI 展示，确认后执行）
    4. 执行：文件移入程序回收站（cleaner.recycle）
    5. 记录：写清理日志（database.add_log）
    6. 更新：条目的 last_clean_time / next_due_time

安全红线（技术规范）：
    - 禁止无条件递归删除
    - 删除前校验目标存在、规则匹配、非保护路径
    - 默认移入回收站而非永久删除
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from ..database import Database
from ..models import CleanLog, VirtualEntry
from ..utils.paths import validate_target_path
from .recycle import RecycleBin
from .rules import compute_dir_size, scan_directory


@dataclass
class CleanResult:
    """一次清理的执行结果。"""

    entry_name: str = ""
    scanned: int = 0          # 扫描文件数
    matched: int = 0          # 匹配文件数
    moved: int = 0            # 实际移入回收站数
    skipped: int = 0          # 跳过数（占用/白名单/失败）
    total_bytes: int = 0


class CleanEngine:
    """清理引擎。"""

    def __init__(self, db: Database, recycle_bin: RecycleBin):
        self.db = db
        self.recycle_bin = recycle_bin

    def preview(self, entry: VirtualEntry) -> list[Path]:
        """返回待清理文件清单（不执行）。"""
        self._validate_entry(entry)
        root = Path(entry.physical_path)
        rule = entry.rule
        skip_in_use = self._skip_in_use_enabled()

        # 回收站目录始终排除：防止回收站位于清理目标内部时被重复扫描清理
        ignore_dirs = [self.recycle_bin.recycle_dir]

        matched: list[Path] = []
        results = scan_directory(root, rule, ignore_dirs=ignore_dirs, skip_in_use=skip_in_use)
        for r in results:
            if r.matched:
                matched.append(r.file_path)

        # by_size_mb：目录超限时，取最旧文件补足
        if rule.by_size_mb and rule.by_size_mb > 0:
            total = compute_dir_size(root, ignore_dirs=ignore_dirs)
            limit = rule.by_size_mb * 1024 * 1024
            if total > limit:
                matched = self._apply_size_rule(root, rule, matched, limit, ignore_dirs, skip_in_use)
        return matched

    def _skip_in_use_enabled(self) -> bool:
        """是否启用"跳过正在使用的文件"（设置项）。"""
        return self.db.get_setting("skip_in_use_files", "1") == "1"

    def _apply_size_rule(self, root: Path, rule, matched: list[Path],
                         limit: int,
                         ignore_dirs: list[Path] | None = None,
                         skip_in_use: bool = True) -> list[Path]:
        """目录超限时：除现有匹配外，按"最旧优先"补齐到不超限。"""
        # 收集全部未匹配文件（排除白名单/回收站目录；skip_in_use 时也排除占用文件）
        from .rules import _in_whitelist, is_file_in_use, iter_files
        all_files = []
        total_deletable = 0
        for p in iter_files(root, ignore_dirs):
            if p.is_file() and not _in_whitelist(p, rule):
                if skip_in_use and is_file_in_use(p):
                    continue
                try:
                    st = p.stat()
                    all_files.append((st.st_mtime, p))
                    total_deletable += st.st_size
                except OSError:
                    continue
        # 合并已匹配 + 未匹配（按最旧排序），依次挑入直到不超过 limit。
        # skip_in_use 时只按"可删除文件"的总量判定，避免因占用文件挤占限额而过度删除。
        chosen = set(matched)
        combined = sorted(all_files, key=lambda x: x[0])  # 最旧在前
        current = total_deletable if skip_in_use else compute_dir_size(root, ignore_dirs=ignore_dirs)
        for _, p in combined:
            if current <= limit:
                break
            if p not in chosen:
                chosen.add(p)
                try:
                    current -= p.stat().st_size
                except OSError:
                    continue
        return [Path(p) for p in chosen]

    def clean(self, entry: VirtualEntry, file_paths: list[Path] | None = None,
              trigger: str = "manual") -> CleanResult:
        """执行清理。"""
        self._validate_entry(entry)

        if file_paths is None:
            file_paths = self.preview(entry)

        result = CleanResult(entry_name=entry.name)
        result.matched = len(file_paths)
        result.scanned = result.matched

        for fpath in file_paths:
            fpath = Path(fpath)
            try:
                size = fpath.stat().st_size if fpath.is_file() else 0
                self.recycle_bin.move_to_recycle(fpath, entry.name)
                result.moved += 1
                result.total_bytes += size
            except Exception:
                result.skipped += 1

        # 写日志
        self.db.add_log(
            CleanLog(
                entry_name=entry.name,
                trigger=trigger,
                file_count=result.moved,
                total_bytes=result.total_bytes,
                result="success" if result.skipped == 0 else "partial",
            )
        )

        # 更新条目状态
        entry.last_clean_time = datetime.now()
        entry.next_due_time = self._compute_next_due(entry)
        self.db.update_entry(entry)

        return result

    def _compute_next_due(self, entry: VirtualEntry) -> datetime | None:
        """根据条目的 Schedule 计算下次到期时间。"""
        from ..scheduler import CleanScheduler
        return CleanScheduler(self.db).compute_next_due(entry)

    def _validate_entry(self, entry: VirtualEntry) -> None:
        """校验条目：路径存在、非保护路径。非法时抛异常。"""
        validate_target_path(entry.physical_path)
        if not entry.enabled:
            raise ValueError(f"条目已禁用: {entry.name}")
