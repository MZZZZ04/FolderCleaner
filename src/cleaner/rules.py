"""
清理规则匹配 — 判断单个文件是否应被清理。

规则组合语义（2.0功能表 ② 模块）：
- 多条规则同时启用时，满足"任一"即匹配（OR）？
- 还是"全部"（AND）？→ TODO 与用户确认，默认建议：不同维度之间 OR，
  同维度内（如多个后缀）OR。clear_all 特例直接全部匹配。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional

from ..models import CleanRule
from ..utils.paths import is_file_in_use

# 默认白名单子目录（永不扫描）
DEFAULT_IGNORED_DIRS = {".git", "__pycache__", "node_modules", "$RECYCLE.BIN", "System Volume Information"}


def _normalize_ignore_dirs(dirs: Optional[List[Path]]) -> set:
    """规范化忽略目录为"解析后绝对路径（小写）"集合，用于路径比较。"""
    ignored = set()
    for d in dirs or []:
        try:
            ignored.add(str(Path(d).resolve()).casefold())
        except OSError:
            continue
    return ignored


@dataclass
class MatchResult:
    """单个文件的匹配结果。"""

    file_path: Path
    matched: bool
    reason: str = ""          # 命中哪条规则 / 为何跳过


def _in_whitelist(file_path: Path, rule: CleanRule) -> bool:
    """判断文件是否命中白名单（文件名/后缀/路径片段任一匹配即命中）。"""
    name = file_path.name.lower()
    lower = str(file_path).lower()
    for item in rule.whitelist:
        item_l = str(item).strip().lower()
        if not item_l:
            continue
        if item_l.startswith(".") and name.endswith(item_l):
            return True                      # 白名单后缀，如 ".git"
        if item_l in name or item_l in lower:
            return True                      # 白名单文件名 / 路径片段
    return False


def _is_ignored_dir(dir_path: Path) -> bool:
    """判断目录是否为默认忽略的子目录。"""
    return dir_path.name in DEFAULT_IGNORED_DIRS


def match_file(file_path: Path, rule: CleanRule) -> MatchResult:
    """判断 file_path 是否命中清理规则。

    组合语义（OR）：不同维度之间满足"任一"即匹配。
    """
    # 1. 白名单 → 永不删除
    if _in_whitelist(file_path, rule):
        return MatchResult(file_path=file_path, matched=False, reason="whitelist")

    # 2. 清空整个文件夹 → 全匹配
    if rule.clear_all:
        return MatchResult(file_path=file_path, matched=True, reason="clear_all")

    matched = False
    reasons = []

    # 3. 按文件类型（后缀），支持 ".log" 或 "log" 两种写法
    if rule.by_extensions:
        ext = file_path.suffix.lower()  # 如 ".tmp"
        allowed = {e.strip().lower().lstrip(".") for e in rule.by_extensions if e.strip()}
        if ext and ext.lstrip(".") in allowed:
            matched = True
            reasons.append("extensions")

    # 4. 按文件名关键词
    if rule.by_keywords and not matched:
        name = file_path.name.lower()
        if any(k.lower() in name for k in rule.by_keywords):
            matched = True
            reasons.append("keywords")

    # 5. 按文件年龄
    if rule.by_age_days is not None and not matched:
        try:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            age = (datetime.now() - mtime).total_seconds() / 86400.0
            if age >= rule.by_age_days:
                matched = True
                reasons.append(f"age>={rule.by_age_days}d")
        except OSError:
            return MatchResult(file_path=file_path, matched=False, reason="stat_error")

    if not matched:
        return MatchResult(file_path=file_path, matched=False, reason="no_rule_hit")
    return MatchResult(file_path=file_path, matched=True, reason="+".join(reasons))


def iter_files(root: Path,
               ignore_dirs: Optional[List[Path]] = None) -> Iterator[Path]:
    """深度遍历 root 下全部文件，跳过默认忽略子目录与 ignore_dirs（绝对路径）。"""
    if not root.is_dir():
        return
    ignored = _normalize_ignore_dirs(ignore_dirs)
    if str(root.resolve()).casefold() in ignored:
        return
    for dirpath, dirnames, filenames in os.walk(str(root)):
        # 过滤绝对路径忽略目录（如程序回收站目录，可能位于清理目标内部）
        dirnames[:] = [
            d for d in dirnames
            if str(Path(dirpath, d).resolve()).casefold() not in ignored
        ]
        # 过滤默认忽略子目录
        dirnames[:] = [
            d for d in dirnames
            if not _is_ignored_dir(Path(dirpath) / d)
        ]
        for fname in filenames:
            yield Path(dirpath) / fname


def scan_directory(root: Path, rule: CleanRule,
                   ignore_dirs: Optional[List[Path]] = None,
                   skip_in_use: bool = True) -> list[MatchResult]:
    """扫描目录（含子目录），返回所有文件的匹配结果。

    跳过默认白名单子目录（如 .git）、跳过 ignore_dirs 指定的绝对路径目录
    （如程序回收站）。skip_in_use 为 True 时跳过被占用的文件。
    """
    results: list[MatchResult] = []
    if not root.is_dir():
        return results
    ignored = _normalize_ignore_dirs(ignore_dirs)
    if str(root.resolve()).casefold() in ignored:
        return results

    try:
        for dirpath, dirnames, filenames in os.walk(str(root)):
            # 过滤绝对路径忽略目录（如程序回收站目录）
            dirnames[:] = [
                d for d in dirnames
                if str(Path(dirpath, d).resolve()).casefold() not in ignored
            ]
            # 过滤默认忽略子目录
            dirnames[:] = [
                d for d in dirnames
                if not _is_ignored_dir(Path(dirpath) / d)
            ]
            # 过滤白名单子目录
            if rule.whitelist:
                dirnames[:] = [
                    d for d in dirnames
                    if not _in_whitelist(Path(dirpath) / d, rule)
                ]

            for fname in filenames:
                fpath = Path(dirpath) / fname
                if skip_in_use and is_file_in_use(fpath):
                    results.append(MatchResult(file_path=fpath, matched=False, reason="in_use"))
                    continue
                results.append(match_file(fpath, rule))
    except PermissionError:
        pass
    return results


def compute_dir_size(root: Path,
                     ignore_dirs: Optional[List[Path]] = None) -> int:
    """计算目录总大小（字节）— 用于 by_size_mb 规则。"""
    total = 0
    for f in iter_files(root, ignore_dirs):
        try:
            total += f.stat().st_size
        except OSError:
            continue
    return total
