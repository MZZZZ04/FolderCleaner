"""
开机自启测试 — 命令构造 + 注册表读写（winreg 用内存假实现）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from src.utils import autostart


class _FakeKey:
    """内存版注册表键（支持 with 协议）。"""

    def __init__(self, values):
        self._values = values

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeWinreg:
    """内存版 winreg 模块（函数签名与真实 winreg 一致）。"""

    HKEY_CURRENT_USER = "HKCU"
    KEY_SET_VALUE = 1
    KEY_READ = 2
    REG_SZ = 1

    def __init__(self):
        self.store = {"HKCU": {}}

    def OpenKey(self, root, subkey, reserved=0, access=0):
        if subkey not in self.store[root]:
            raise FileNotFoundError(subkey)
        return _FakeKey(self.store[root][subkey])

    def SetValueEx(self, key, name, reserved, type_, value):
        key._values[name] = value

    def DeleteValue(self, key, name):
        if name not in key._values:
            raise FileNotFoundError
        del key._values[name]

    def QueryValueEx(self, key, name):
        if name not in key._values:
            raise FileNotFoundError
        return key._values[name], 1


@pytest.fixture
def fake_winreg(monkeypatch):
    fake = _FakeWinreg()
    fake.store["HKCU"][autostart.RUN_KEY] = {}
    monkeypatch.setattr(autostart, "winreg", fake)
    return fake


def test_autostart_command_frozen(monkeypatch):
    monkeypatch.setattr(autostart.sys, "frozen", True, raising=False)
    monkeypatch.setattr(autostart.sys, "executable", r"C:\Tools\FolderCleaner.exe")
    assert autostart.build_autostart_command() == r'"C:\Tools\FolderCleaner.exe"'


def test_autostart_command_dev(monkeypatch):
    monkeypatch.setattr(autostart.sys, "frozen", False, raising=False)
    cmd = autostart.build_autostart_command()
    assert "launcher.py" in cmd


def test_set_and_clear_autostart(fake_winreg):
    assert not autostart.is_autostart_enabled()
    assert autostart.set_autostart(True)
    assert autostart.is_autostart_enabled()
    assert autostart.set_autostart(False)
    assert not autostart.is_autostart_enabled()
