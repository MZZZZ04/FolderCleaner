"""
开机自启 — Windows 注册表 HKCU\\...\\Run 键读写（无需管理员权限）。

只在 Windows 下有效；打包后的 exe 直接写 exe 路径，
开发模式用 pythonw 静默运行 launcher.py。
"""

from __future__ import annotations

import os
import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "FolderCleaner"


def build_autostart_command() -> str:
    """构造开机自启命令（含引号）。"""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe_dir = Path(sys.executable).resolve().parent
    pythonw = exe_dir / "pythonw.exe"
    launcher = Path(__file__).resolve().parents[2] / "launcher.py"
    interp = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{interp}" "{launcher}"'


def set_autostart(enabled: bool) -> bool:
    """写入（enabled=True）或移除（enabled=False）开机自启项。返回是否成功。"""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(
                    key, RUN_VALUE_NAME, 0, winreg.REG_SZ, build_autostart_command()
                )
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def is_autostart_enabled() -> bool:
    """检查注册表自启项当前是否存在。"""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ
        ) as key:
            winreg.QueryValueEx(key, RUN_VALUE_NAME)
            return True
    except (FileNotFoundError, OSError):
        return False
