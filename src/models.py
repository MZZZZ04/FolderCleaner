"""
数据模型定义。

虚拟条目（VirtualEntry）是本应用的核心概念：
物理路径（真实文件夹） + 虚拟别名（界面展示）+ 清理规则 + 调度周期。

TODO(Claude Code): 按 2.0功能表.md 确认字段，必要时调整。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CleanRule:
    """清理规则（可组合，2.0功能表 ② 模块）。

    - by_age_days:     按文件年龄，删除 N 天前未修改的文件（None=不启用）
    - by_size_mb:      按目录大小，超过 X MB 时删最旧（None=不启用）
    - by_extensions:   按文件类型，只清理指定后缀列表（空=不启用）
    - by_keywords:     按文件名关键词（空=不启用）
    - clear_all:       清空整个文件夹（需二次确认）
    - whitelist:       白名单文件名/后缀/目录，永不删除
    """

    by_age_days: Optional[int] = None
    by_size_mb: Optional[int] = None
    by_extensions: list = field(default_factory=list)
    by_keywords: list = field(default_factory=list)
    clear_all: bool = False
    whitelist: list = field(default_factory=list)

    def is_enabled(self) -> bool:
        """是否至少启用了一条规则。"""
        # TODO: 实现 — 任一规则非空即返回 True
        return True


@dataclass
class Schedule:
    """定时调度配置（2.0功能表 ③ 模块）。

    支持：每天 X 点 / 每 N 天 / 每周 X 点 / 指定日期。
    """

    kind: str = "daily"          # daily / interval / weekly / once
    time: str = "20:00"          # HH:MM
    interval_days: int = 1       # kind=interval 时生效
    weekday: int = 0             # kind=weekly 时生效 (0=周一)
    once_date: Optional[str] = None  # kind=once 时生效 (YYYY-MM-DD)


@dataclass
class VirtualEntry:
    """虚拟条目 — 物理路径 + 虚拟别名 + 规则 + 调度。"""

    entry_id: str = ""                # 唯一 ID（UUID）
    name: str = ""                    # 虚拟别名（界面展示）
    physical_path: str = ""           # 真实物理路径（不变）
    rule: CleanRule = field(default_factory=CleanRule)
    schedule: Schedule = field(default_factory=Schedule)
    enabled: bool = True              # 是否启用该条目
    last_clean_time: Optional[datetime] = None   # 上次清理时间
    next_due_time: Optional[datetime] = None     # 下次到期时间


@dataclass
class RecycleItem:
    """程序回收站条目（2.0功能表 ⑦ 模块）。

    清理时文件被移入回收站文件夹（延时删除），保留到期后自动清空。
    """

    item_id: str = ""
    file_name: str = ""               # 原文件名
    original_path: str = ""           # 原物理路径（恢复时用）
    recycle_path: str = ""            # 回收站中的当前路径
    size_bytes: int = 0
    moved_at: datetime = field(default_factory=datetime.now)  # 移入时间


@dataclass
class CleanLog:
    """清理日志（2.0功能表 ⑤ 模块）。"""

    log_id: str = ""
    time: datetime = field(default_factory=datetime.now)
    entry_name: str = ""              # 虚拟条目名
    trigger: str = ""                 # auto(定时) / manual(手动) / compensate(启动补偿)
    file_count: int = 0
    total_bytes: int = 0
    result: str = ""                  # success / partial / skipped
