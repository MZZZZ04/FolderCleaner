"""
"跳过正在使用的文件" — 占用检测 + 设置项贯穿扫描与大小规则。

回归场景：设置里勾选了"跳过正在使用的文件"（默认），但正在使用的文件仍被清理。
根因：① 大小规则（by_size_mb）路径绕过占用检测；② 独占打开检测漏掉以共享方式
打开的占用文件（编辑器中打开的文档等）。
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from src.cleaner.engine import CleanEngine
from src.cleaner.recycle import RecycleBin
from src.database import Database
from src.models import CleanRule, VirtualEntry
from src.utils.paths import is_file_in_use

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Restart Manager API 仅 Windows")


@pytest.fixture
def env(tmp_path):
    """独立环境：数据库 + 回收站 + 目标目录。"""
    db = Database(tmp_path / "test.db")
    bin_ = RecycleBin(db, recycle_dir=tmp_path / "recycle_bin")
    src = tmp_path / "src"
    src.mkdir()
    engine = CleanEngine(db, bin_)
    return db, engine, src


def _entry(src: Path, rule: CleanRule) -> VirtualEntry:
    return VirtualEntry(name="测试", physical_path=str(src), rule=rule, enabled=True)


def test_is_file_in_use_detects_shared_handle(env):
    """以共享方式打开的占用文件能被检测出来（普通独占打开会漏掉）。"""
    _, _, src = env
    f = src / "a.txt"
    f.write_text("hello")
    handle = open(f, "r+b")  # 持有句柄，模拟正在使用的文件
    try:
        assert is_file_in_use(f) is True
    finally:
        handle.close()


def test_setting_on_skips_in_use_clear_all(env):
    """设置开启：clear_all 也不清理占用文件。"""
    db, engine, src = env
    f = src / "a.txt"
    f.write_text("hello")
    db.set_setting("skip_in_use_files", "1")

    handle = open(f, "r+b")
    try:
        matched = engine.preview(_entry(src, CleanRule(clear_all=True)))
    finally:
        handle.close()

    assert matched == []


def test_setting_off_includes_in_use_clear_all(env):
    """设置关闭：clear_all 会尝试清理占用文件。"""
    db, engine, src = env
    f = src / "a.txt"
    f.write_text("hello")
    db.set_setting("skip_in_use_files", "0")

    handle = open(f, "r+b")
    try:
        matched = engine.preview(_entry(src, CleanRule(clear_all=True)))
    finally:
        handle.close()

    assert matched == [f]


def test_size_rule_skips_in_use_oldest(env):
    """大小规则：目录超限删最旧时，占用文件不被选中。

    old 0.2MB + mid 1.2MB = 1.4MB > 1MB 限额。不跳过占用时本应删到
    old+mid（删除 old 后仍超限）；开启跳过则 mid 被保护，只剩 old 的
    可删除量 0.2MB ≤ 限额，无需删除任何文件。
    """
    db, engine, src = env
    db.set_setting("skip_in_use_files", "1")

    old = src / "old.txt"
    mid = src / "mid.txt"
    old.write_bytes(b"\0" * (200 * 1024))   # 0.2MB
    mid.write_bytes(b"\0" * (1228 * 1024))  # 1.2MB
    os.utime(old, (time.time() - 10 * 86400, time.time() - 10 * 86400))
    os.utime(mid, (time.time() - 5 * 86400, time.time() - 5 * 86400))

    handle = open(mid, "r+b")  # 占用文件（且按最旧优先本应先动 old，再动 mid）
    try:
        matched = engine.preview(_entry(src, CleanRule(by_size_mb=1)))
    finally:
        handle.close()

    assert mid not in matched   # 占用文件绝不选入
    assert old not in matched   # 剩余可删除量已 ≤ 限额，不必删 old 补偿


def test_size_rule_off_includes_in_use(env):
    """大小规则 + 设置关闭：占用文件同样被选中（尝试清理）。"""
    db, engine, src = env
    db.set_setting("skip_in_use_files", "0")

    old = src / "old.txt"
    mid = src / "mid.txt"
    old.write_bytes(b"\0" * (200 * 1024))   # 0.2MB
    mid.write_bytes(b"\0" * (1228 * 1024))  # 1.2MB
    os.utime(old, (time.time() - 10 * 86400, time.time() - 10 * 86400))
    os.utime(mid, (time.time() - 5 * 86400, time.time() - 5 * 86400))

    handle = open(mid, "r+b")
    try:
        matched = engine.preview(_entry(src, CleanRule(by_size_mb=1)))
    finally:
        handle.close()

    assert old in matched        # 先删最旧
    assert mid in matched        # 删完 old 仍超限 → 占用文件也被选入（设置关闭）
