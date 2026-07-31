"""
程序回收站（延时删除）— 2.0功能表 ⑦ 模块。

核心：清理时不直接删除，而是把文件"移动"到回收站文件夹暂存。
    - 保留时间到期 → 自动清空（permanently delete）
    - 保留期内 → 可恢复回原路径（误删反悔）

回收站文件夹位置：config.get_recycle_dir()
"""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from ..config import get_recycle_dir
from ..database import Database
from ..models import RecycleItem
from ..utils.paths import format_size


def _unique_target(target: Path) -> Path:
    """重名时给路径加序号（a.txt → a_1.txt → a_2.txt）。"""
    if not target.exists():
        return target
    parent, name = target.parent, target.name
    stem, suffix = target.stem, target.suffix
    i = 1
    while True:
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


class RecycleBin:
    """程序回收站。"""

    def __init__(self, db: Database, recycle_dir: Path | None = None):
        self.db = db
        self._explicit_dir = Path(recycle_dir) if recycle_dir else None
        if self._explicit_dir:
            self._explicit_dir.mkdir(parents=True, exist_ok=True)

    @property
    def recycle_dir(self) -> Path:
        """当前回收站目录。未显式指定时优先取 DB 设置；设置无效/不可用时回退默认目录。"""
        if self._explicit_dir:
            return self._explicit_dir
        custom = self.db.get_setting("recycle_dir", "").strip()
        if custom:
            d = Path(custom)
            try:
                d.mkdir(parents=True, exist_ok=True)
                if not d.is_dir():
                    raise OSError(f"不是目录: {custom}")
                return d
            except OSError:
                pass  # 自定义路径失效（不存在/不可创建/不是目录）→ 回退默认
        d = get_recycle_dir()
        d.mkdir(parents=True, exist_ok=True)
        return d

    def move_to_recycle(self, src_path: Path, entry_name: str) -> RecycleItem:
        """把文件移入回收站（暂存），返回回收站条目。"""
        src_path = Path(src_path)
        if not src_path.exists():
            raise FileNotFoundError(f"文件不存在: {src_path}")

        dest = _unique_target(self.recycle_dir / src_path.name)
        size_bytes = 0
        if src_path.is_file():
            size_bytes = src_path.stat().st_size

        # 同盘 move；跨盘 copy + 删除源
        try:
            shutil.move(str(src_path), str(dest))
        except OSError:
            shutil.copy2(str(src_path), str(dest))
            if src_path.is_dir():
                shutil.rmtree(str(src_path))
            else:
                src_path.unlink()

        item = RecycleItem(
            item_id=uuid.uuid4().hex,
            file_name=src_path.name,
            original_path=str(src_path),
            recycle_path=str(dest),
            size_bytes=size_bytes,
            moved_at=datetime.now(),
        )
        self.db.add_recycle_item(item)
        return item

    def restore(self, item: RecycleItem) -> bool:
        """恢复文件回原路径（误删反悔）。"""
        src = Path(item.recycle_path)
        if not src.exists():
            return False

        original = Path(item.original_path)
        original.parent.mkdir(parents=True, exist_ok=True)
        target = _unique_target(original)

        try:
            if original.exists() and original.is_dir():
                # 原路径是目录被误删，此处恢复为文件时避开目录
                target = _unique_target(target)
            shutil.move(str(src), str(target))
        except OSError:
            shutil.copy2(str(src), str(target))
            if src.is_dir():
                shutil.rmtree(str(src))
            else:
                src.unlink()

        self.db.remove_recycle_item(item.item_id)
        return True

    def purge_expired(self, retention_days: int) -> int:
        """清空已过保留期的文件，返回清除数量。"""
        cutoff = datetime.now() - timedelta(days=retention_days)
        count = 0
        for item in self.db.list_recycle_items():
            if item.moved_at and item.moved_at < cutoff:
                try:
                    p = Path(item.recycle_path)
                    if p.is_dir():
                        shutil.rmtree(str(p), ignore_errors=True)
                    elif p.exists():
                        p.unlink()
                    self.db.remove_recycle_item(item.item_id)
                    count += 1
                except OSError:
                    continue
        return count

    def purge_all(self) -> int:
        """立即清空整个回收站（GUI 手动触发）。"""
        count = 0
        for item in self.db.list_recycle_items():
            try:
                p = Path(item.recycle_path)
                if p.is_dir():
                    shutil.rmtree(str(p), ignore_errors=True)
                elif p.exists():
                    p.unlink()
                self.db.remove_recycle_item(item.item_id)
                count += 1
            except OSError:
                continue
        return count

    def delete_now(self, item: RecycleItem) -> None:
        """立即删除单个条目（不等保留期）。"""
        p = Path(item.recycle_path)
        if p.is_dir():
            shutil.rmtree(str(p), ignore_errors=True)
        elif p.exists():
            p.unlink()
        self.db.remove_recycle_item(item.item_id)
