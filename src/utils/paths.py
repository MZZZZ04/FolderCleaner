"""
路径工具 — 安全校验与格式化。

安全红线（技术规范）：
    - 禁止无条件递归删除用户指定目录
    - 删除前校验目标存在、非系统保护路径
    - 正在使用的文件自动跳过
"""

from __future__ import annotations

import os
from pathlib import Path


def validate_target_path(path: str) -> Path:
    """校验目标路径：必须存在、必须是目录、非保护路径。非法抛 ValueError。"""
    p = Path(path).resolve()
    if not p.is_dir():
        raise ValueError(f"路径不存在或不是文件夹: {path}")
    from ..config import is_protected_path
    if is_protected_path(str(p)):
        raise ValueError(f"系统保护路径，禁止清理: {path}")
    return p


def is_file_in_use(path: Path) -> bool:
    """判断文件是否被占用。

    Windows 下优先用 Restart Manager API：它能检测出被以"共享"方式打开的
    占用文件（如正在编辑的文档、播放中的视频等），这是普通独占打开检测
    会漏掉的。非 Windows 或 API 调用失败时回退到独占打开检测。
    """
    if not path.is_file():
        return False
    if os.name == "nt":
        try:
            return _restart_manager_in_use(str(path))
        except Exception:
            pass
    try:
        with open(str(path), "r+b"):
            return False
    except PermissionError:
        return True
    except OSError:
        return True


def _restart_manager_in_use(path: str) -> bool:
    """用 Restart Manager API 判断文件是否被任何进程占用。"""
    import ctypes
    from ctypes import wintypes

    session_key = ctypes.create_unicode_buffer(256)
    session_handle = wintypes.DWORD(0)

    rstrtmgr = ctypes.windll.rstrtmgr
    RmStartSession = rstrtmgr.RmStartSession
    RmStartSession.restype = wintypes.DWORD
    RmStartSession.argtypes = [
        ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, ctypes.c_wchar_p,
    ]
    res = RmStartSession(ctypes.byref(session_handle), 0, session_key)
    if res != 0:
        raise OSError(f"RmStartSession 失败: {res}")
    try:
        RmRegisterResources = rstrtmgr.RmRegisterResources
        RmRegisterResources.restype = wintypes.DWORD
        RmRegisterResources.argtypes = [
            wintypes.DWORD, wintypes.UINT, ctypes.c_void_p,
            wintypes.UINT, ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p,
        ]
        files = (ctypes.c_wchar_p * 1)(path)
        res = RmRegisterResources(session_handle, 1, files, 0, None, 0, None)
        if res != 0:
            raise OSError(f"RmRegisterResources 失败: {res}")

        ERROR_SUCCESS, ERROR_MORE_DATA, ERROR_ACCESS_DENIED = 0, 234, 5
        needed = wintypes.DWORD(0)
        count = wintypes.DWORD(0)
        reboot = wintypes.DWORD(0)

        RmGetList = rstrtmgr.RmGetList
        RmGetList.restype = wintypes.DWORD
        RmGetList.argtypes = [
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD),
        ]
        res = RmGetList(session_handle, ctypes.byref(needed),
                        ctypes.byref(count), None, ctypes.byref(reboot))
        if res == ERROR_SUCCESS:
            return needed.value > 0
        if res in (ERROR_MORE_DATA, ERROR_ACCESS_DENIED):
            return True  # 有占用进程 / 无权限枚举 —— 保守视为占用
        raise OSError(f"RmGetList 失败: {res}")
    finally:
        RmEndSession = rstrtmgr.RmEndSession
        RmEndSession.restype = wintypes.DWORD
        RmEndSession.argtypes = [wintypes.DWORD]
        RmEndSession(session_handle)


def safe_join(base: Path, name: str) -> Path:
    """安全拼接路径（防止路径穿越：拒绝 ../ 或绝对路径片段）。"""
    base = base.resolve()
    joined = base / name
    resolved = joined.resolve()
    if not resolved.is_relative_to(base):
        raise ValueError(f"非法路径片段: {name}")
    return resolved


def format_size(size_bytes: int) -> str:
    """格式化文件大小（B/KB/MB/GB）。"""
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"


def format_duration(seconds: int) -> str:
    """格式化时长（如 "14 小时" / "3 天"）— 用于过期提示框。"""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "不足 1 分钟"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} 分钟"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} 小时"
    days = hours // 24
    return f"{days} 天"
