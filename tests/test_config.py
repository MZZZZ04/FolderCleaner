"""
回收站目录解析测试 — src.config.get_recycle_dir（跨电脑可移植性）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from src import config


def test_recycle_dir_app_dir_writable(monkeypatch, tmp_path):
    """exe 目录可写 → 回收站在应用目录（exe 旁）。"""
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    monkeypatch.setattr(config, "get_app_dir", lambda: app_dir)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    d = config.get_recycle_dir()
    assert d == app_dir / "recycle_bin"
    assert d.is_dir()


def test_recycle_dir_fallback_when_app_dir_unwritable(monkeypatch, tmp_path):
    """exe 目录不可写（get_app_dir 指向一个文件）→ 自动回退到数据目录。"""
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x")  # 令 app_dir/recycle_bin 创建失败，模拟只读位置
    monkeypatch.setattr(config, "get_app_dir", lambda: blocker)
    appdata = tmp_path / "appdata"
    monkeypatch.setenv("APPDATA", str(appdata))
    d = config.get_recycle_dir()
    assert d == appdata / "CleanFolderApp" / "recycle_bin"
    assert d.is_dir()
