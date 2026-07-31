"""
📁 虚拟条目页 — 条目卡片列表 + 添加/编辑/删除（3.0UI设计.md 页面2）。
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from ...cleaner.engine import CleanEngine
from ...database import Database
from ...models import VirtualEntry
from ...utils.paths import format_size
from ..dialogs import CleanConfirmDialog, EntryDialog
from .clean_runner import run_preview_confirm

_WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _describe_schedule(sched) -> str:
    """调度概要（卡片展示用）。"""
    if sched.kind == "daily":
        return f"每天 {sched.time}"
    if sched.kind == "interval":
        return f"每 {sched.interval_days} 天"
    if sched.kind == "weekly":
        return f"每周 {_WEEKDAYS[max(0, min(6, sched.weekday))]} {sched.time}"
    if sched.kind == "once" and sched.once_date:
        return f"指定 {sched.once_date} {sched.time}"
    return "未设置调度"


class EntriesPage(QWidget):
    """虚拟条目管理页。"""

    entries_changed = Signal()  # 条目增删改后触发（用于刷新调度任务）

    def __init__(self, db: Database, engine: CleanEngine):
        super().__init__()
        self.db = db
        self.engine = engine

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel("📁 虚拟条目")
        title.setStyleSheet("font-size:18px;font-weight:bold;")
        self.add_btn = QPushButton("＋ 添加")
        self.add_btn.setStyleSheet("background:#27ae60;color:white;padding:6px 16px;")
        self.add_btn.clicked.connect(self._on_add)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.add_btn)
        layout.addLayout(header)

        # 卡片滚动区
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll.setWidget(self.cards_container)
        layout.addWidget(self.scroll, 1)

        # 底部操作
        bottom = QHBoxLayout()
        self.clean_all_btn = QPushButton("🕐 立即清理所有到期条目")
        self.clean_all_btn.setStyleSheet("background:#e67e22;color:white;padding:8px 20px;")
        self.clean_all_btn.clicked.connect(self._on_clean_all_due)
        bottom.addStretch()
        bottom.addWidget(self.clean_all_btn)
        layout.addLayout(bottom)

        self.refresh()

    def refresh(self) -> None:
        """刷新条目列表。"""
        # 清空旧卡片
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        entries = self.db.list_entries()
        if not entries:
            self.cards_layout.addWidget(QLabel("还没有虚拟条目，点击『＋ 添加』创建"))
            return

        for entry in entries:
            self.cards_layout.addWidget(self._build_card(entry))
        self.cards_layout.addStretch()

    def _build_card(self, entry: VirtualEntry) -> QFrame:
        """构建单个条目卡片。"""
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setStyleSheet(
            "QFrame{background:white;border:1px solid #e0e4ea;border-radius:8px;}"
            "QFrame:hover{border:1px solid #3498db;}"
            "QLabel{color:#333;background:transparent;}"
        )

        layout = QVBoxLayout(card)

        # 首行：名称 + 按钮
        top = QHBoxLayout()
        name_label = QLabel(f"📁 {entry.name}")
        name_label.setStyleSheet("font-size:14px;font-weight:bold;color:#2c3e50;")
        top.addWidget(name_label)
        top.addStretch()

        edit_btn = QPushButton("✏️")
        edit_btn.setFixedWidth(32)
        edit_btn.clicked.connect(lambda: self._on_edit(entry.entry_id))
        del_btn = QPushButton("🗑️")
        del_btn.setFixedWidth(32)
        del_btn.clicked.connect(lambda: self._on_delete(entry.entry_id))
        clean_btn = QPushButton("🧹 立即清理")
        clean_btn.setStyleSheet("background:#e67e22;color:white;padding:4px 12px;")
        clean_btn.clicked.connect(lambda: self._on_clean_now(entry.entry_id))
        top.addWidget(clean_btn)
        top.addWidget(edit_btn)
        top.addWidget(del_btn)
        layout.addLayout(top)

        # 第二行：详情摘要
        rule = entry.rule
        parts = []
        if rule.by_age_days:
            parts.append(f"按天数 {rule.by_age_days} 天")
        if rule.by_size_mb:
            parts.append(f"超{rule.by_size_mb}MB删最旧")
        if rule.by_extensions:
            parts.append(" ".join(rule.by_extensions))
        if rule.by_keywords:
            parts.append("关键词:" + "/".join(rule.by_keywords))
        if rule.clear_all:
            parts.append("清空全部")
        rule_desc = "、".join(parts) if parts else "未设置规则"

        last_clean = entry.last_clean_time.strftime("%m-%d %H:%M") if entry.last_clean_time else "从未"
        detail = QLabel(
            f"    {entry.physical_path}\n"
            f"    规则: {rule_desc}  |  调度: {_describe_schedule(entry.schedule)}  |  上次清理: {last_clean}"
        )
        detail.setStyleSheet("font-size:12px;color:#666;")
        layout.addWidget(detail)

        return card

    def _on_add(self) -> None:
        """打开添加条目弹窗。"""
        dialog = EntryDialog(None, self)
        if dialog.exec_() == EntryDialog.Accepted:
            entry = dialog.get_entry()
            try:
                from ...utils.paths import validate_target_path
                validate_target_path(entry.physical_path)
            except ValueError as e:
                QMessageBox.warning(self, "路径无效", str(e))
                return
            entry.next_due_time = self.engine._compute_next_due(entry)
            self.db.add_entry(entry)
            self.refresh()
            self.entries_changed.emit()

    def _on_edit(self, entry_id: str) -> None:
        """打开编辑条目弹窗。"""
        entry = self.db.get_entry(entry_id)
        if not entry:
            return
        dialog = EntryDialog(entry, self)
        if dialog.exec_() == EntryDialog.Accepted:
            updated = dialog.get_entry()
            updated.entry_id = entry_id
            updated.next_due_time = self.engine._compute_next_due(updated)
            self.db.update_entry(updated)
            self.refresh()
            self.entries_changed.emit()

    def _on_delete(self, entry_id: str) -> None:
        """删除条目（确认弹窗，不动物理路径文件）。"""
        entry = self.db.get_entry(entry_id)
        if not entry:
            return
        ret = QMessageBox.question(
            self, "删除条目",
            f"确定删除虚拟条目『{entry.name}』？\n（仅移除配置，不会删除物理路径中的任何文件）",
        )
        if ret == QMessageBox.Yes:
            self.db.delete_entry(entry_id)
            self.refresh()
            self.entries_changed.emit()

    def _on_clean_now(self, entry_id: str) -> None:
        """立即清理指定条目。"""
        entry = self.db.get_entry(entry_id)
        if not entry:
            return
        run_preview_confirm(self, self.engine, entry, trigger="manual")
        self.refresh()

    def _on_clean_all_due(self) -> None:
        """立即清理所有到期条目。"""
        from ...scheduler import CleanScheduler
        due = CleanScheduler(self.db).check_due_entries()
        if not due:
            QMessageBox.information(self, "提示", "当前没有到期的条目")
            return
        for d in due:
            run_preview_confirm(self, self.engine, d.entry, trigger="compensate")
        self.refresh()
