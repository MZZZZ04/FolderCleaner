"""
全局配置 — 应用数据目录、数据库路径、回收站保留时间等。

TODO(Claude Code): 实现 get_data_dir()，建议：
    Windows: %APPDATA%/CleanFolderApp 或程序目录下 data/
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 应用名
APP_NAME = "定时清理指定文件夹"

# 默认回收站保留时间（天）
DEFAULT_RECYCLE_RETENTION_DAYS = 7

# 系统保护路径（禁止设为清理目标）——按需补充
PROTECTED_PATHS = [
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
]


def get_data_dir() -> Path:
    """获取应用数据目录（存放数据库、回收站文件夹）。"""
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData/Roaming")
    data_dir = Path(base) / "CleanFolderApp"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_db_path() -> Path:
    """获取 SQLite 数据库路径。"""
    return get_data_dir() / "clean_app.db"


def get_app_dir() -> Path:
    """应用所在目录：PyInstaller 打包后 = exe 目录；开发时 = 项目根目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def get_recycle_dir() -> Path:
    """获取程序回收站文件夹路径（延时删除暂存区）。

    优先位于应用目录（exe 旁，随 exe 一起移动）；应用目录不可写
    （如 exe 被放到 Program Files 等只读位置）时，自动回退到数据目录，
    保证放在任意位置的 exe 都能正常清理。
    """
    primary = get_app_dir() / "recycle_bin"
    try:
        primary.mkdir(parents=True, exist_ok=True)
        if primary.is_dir():
            return primary
    except OSError:
        pass
    fallback = get_data_dir() / "recycle_bin"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def get_icon_path() -> Path:
    """程序图标文件路径（resources/icons/app.png，Qt 用）。

    PyInstaller 打包后资源随 --add-data 打进 _MEIPASS；开发时位于项目资源目录。
    """
    meipass = getattr(sys, "_MEIPASS", "")
    base = Path(meipass) if meipass else get_app_dir()
    return base / "resources" / "icons" / "app.png"


def is_protected_path(path: str) -> bool:
    """判断路径是否为系统保护路径（禁止清理）。"""
    p = Path(path).resolve()
    for protected in PROTECTED_PATHS:
        try:
            if p == Path(protected).resolve() or protected in str(p):
                return True
        except OSError:
            continue
    return False
