"""
程序回收站测试 — src.cleaner.recycle
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from src.cleaner.recycle import RecycleBin
from src.database import Database
from src.models import RecycleItem


@pytest.fixture
def setup(tmp_path):
    """构造独立测试环境：数据库 + 回收站目录 + 源目录。"""
    db = Database(tmp_path / "test.db")
    recycle_dir = tmp_path / "recycle_bin"
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    bin_ = RecycleBin(db, recycle_dir=recycle_dir)
    return db, bin_, src_dir


def test_move_to_recycle(setup):
    """文件移入回收站，original_path 正确。"""
    db, bin_, src_dir = setup
    f = src_dir / "a.txt"
    f.write_text("hello")

    item = bin_.move_to_recycle(f, "测试条目")

    assert not f.exists()                       # 源文件已移走
    assert Path(item.recycle_path).exists()     # 回收站中有文件
    assert item.original_path == str(f)
    assert db.list_recycle_items()[0].item_id == item.item_id


def test_move_to_recycle_rename_on_conflict(setup):
    """重名文件自动加序号。"""
    db, bin_, src_dir = setup
    f1 = src_dir / "a.txt"
    f2 = src_dir / "b.txt"
    f1.write_text("1")
    f2.write_text("2")

    item1 = bin_.move_to_recycle(f1, "条目")
    item2 = bin_.move_to_recycle(f2, "条目")

    assert item1.recycle_path != item2.recycle_path
    assert Path(item1.recycle_path).exists()
    assert Path(item2.recycle_path).exists()


def test_restore(setup):
    """恢复回原路径。"""
    db, bin_, src_dir = setup
    f = src_dir / "a.txt"
    f.write_text("hello")
    item = bin_.move_to_recycle(f, "条目")

    ok = bin_.restore(item)

    assert ok is True
    assert f.exists()
    assert f.read_text() == "hello"
    assert db.list_recycle_items() == []        # 记录已清除


def test_purge_expired_only_expired(setup):
    """仅清除超保留期的文件。"""
    db, bin_, src_dir = setup

    old_f = src_dir / "old.txt"
    new_f = src_dir / "new.txt"
    old_f.write_text("old")
    new_f.write_text("new")

    old_item = bin_.move_to_recycle(old_f, "条目")
    new_item = bin_.move_to_recycle(new_f, "条目")

    # 将 old_item 的移入时间改为 10 天前
    old_time = (datetime.now() - timedelta(days=10)).isoformat()
    with db._conn() as conn:
        conn.execute(
            "UPDATE recycle_items SET moved_at = ? WHERE id = ?",
            (old_time, old_item.item_id),
        )

    count = bin_.purge_expired(retention_days=7)

    assert count == 1
    assert not Path(old_item.recycle_path).exists()
    assert Path(new_item.recycle_path).exists()


def test_recycle_dir_follows_setting(setup, tmp_path):
    """设置页变更回收站路径后立即生效，无需重启。"""
    db, _, _ = setup
    new_dir = tmp_path / "new_recycle"
    db.set_setting("recycle_dir", str(new_dir))
    b = RecycleBin(db)  # 不传显式路径
    assert b.recycle_dir.resolve() == new_dir.resolve()
    # 改回默认（清空设置）→ 回退默认路径
    db.set_setting("recycle_dir", "")
    assert b.recycle_dir.name == "recycle_bin"


def test_purge_all(setup):
    """立即清空全部。"""
    db, bin_, src_dir = setup
    for name in ("a.txt", "b.txt"):
        f = src_dir / name
        f.write_text(name)
        bin_.move_to_recycle(f, "条目")

    count = bin_.purge_all()

    assert count == 2
    assert db.list_recycle_items() == []
    assert not any(bin_.recycle_dir.iterdir())
