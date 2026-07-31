"""
清理规则匹配测试 — src.cleaner.rules
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from src.cleaner.rules import compute_dir_size, match_file, scan_directory
from src.models import CleanRule


def _touch(path: Path, days_ago: int = 0):
    """创建文件并可设定修改时间（days_ago 天前）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("test")
    if days_ago:
        t = datetime.now() - timedelta(days=days_ago)
        from os import utime
        utime(path, (t.timestamp(), t.timestamp()))


def test_whitelist_never_matches(tmp_path):
    """白名单文件永不匹配。"""
    f = tmp_path / "important.log"
    _touch(f)
    rule = CleanRule(by_extensions=[".log"], whitelist=["important.log"])
    result = match_file(f, rule)
    assert result.matched is False
    assert result.reason == "whitelist"


def test_by_age_days(tmp_path):
    """修改时间 > N 天匹配，< N 天不匹配。"""
    old = tmp_path / "old.txt"
    new = tmp_path / "new.txt"
    _touch(old, days_ago=10)
    _touch(new, days_ago=1)

    rule = CleanRule(by_age_days=5)
    assert match_file(old, rule).matched is True
    assert match_file(new, rule).matched is False


def test_by_extensions(tmp_path):
    """后缀命中/未命中。"""
    log = tmp_path / "a.log"
    txt = tmp_path / "b.txt"
    _touch(log)
    _touch(txt)

    rule = CleanRule(by_extensions=[".log"])
    assert match_file(log, rule).matched is True
    assert match_file(txt, rule).matched is False


def test_by_keywords(tmp_path):
    """文件名包含关键词。"""
    f1 = tmp_path / "temp_file.txt"
    f2 = tmp_path / "keep.txt"
    _touch(f1)
    _touch(f2)

    rule = CleanRule(by_keywords=["temp"])
    assert match_file(f1, rule).matched is True
    assert match_file(f2, rule).matched is False


def test_clear_all_matches_everything(tmp_path):
    """clear_all 全匹配。"""
    f = tmp_path / "anything.dat"
    _touch(f)
    rule = CleanRule(clear_all=True)
    assert match_file(f, rule).matched is True


def test_combined_or_semantics(tmp_path):
    """组合规则 OR 语义：任一命中即匹配。"""
    old_log = tmp_path / "old.log"      # 后缀命中
    old_txt = tmp_path / "old.txt"      # 年龄命中
    fresh_txt = tmp_path / "new.txt"    # 都不命中
    _touch(old_log, days_ago=10)
    _touch(old_txt, days_ago=10)
    _touch(fresh_txt, days_ago=1)

    rule = CleanRule(by_age_days=5, by_extensions=[".log"])
    assert match_file(old_log, rule).matched is True
    assert match_file(old_txt, rule).matched is True
    assert match_file(fresh_txt, rule).matched is False


def test_scan_directory_skips_ignored_dirs(tmp_path):
    """scan_directory 跳过默认忽略子目录。"""
    (tmp_path / ".git" / "config").mkdir(parents=True)
    (tmp_path / ".git" / "HEAD").write_text("x")
    (tmp_path / "normal.log").write_text("x")
    _touch(tmp_path / "normal.log")

    rule = CleanRule(by_extensions=[".log"])
    results = scan_directory(tmp_path, rule)
    matched = [r.file_path.name for r in results if r.matched]
    assert "normal.log" in matched
    assert "HEAD" not in matched


def test_scan_directory_skips_extra_ignore_dirs(tmp_path):
    """scan_directory 跳过额外忽略目录（回收站路径在清理目标内部）。"""
    target = tmp_path / "target"
    recycle = target / "recycle_bin"
    recycle.mkdir(parents=True)
    (recycle / "old.log").write_text("old")
    (target / "normal.log").write_text("normal")

    rule = CleanRule(by_extensions=[".log"])
    results = scan_directory(target, rule, ignore_dirs=[recycle])
    matched = [r.file_path.name for r in results if r.matched]
    assert "normal.log" in matched
    assert "old.log" not in matched


def test_compute_dir_size_skips_extra_ignore_dirs(tmp_path):
    """compute_dir_size 忽略回收站目录的大小。"""
    target = tmp_path / "target"
    recycle = target / "recycle_bin"
    recycle.mkdir(parents=True)
    (recycle / "big.bin").write_bytes(b"x" * 1000)
    (target / "small.txt").write_bytes(b"x")

    total = compute_dir_size(target, ignore_dirs=[recycle])
    assert total == 1
