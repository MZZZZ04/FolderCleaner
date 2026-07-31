"""
📋 概览页 — 统计卡片 + 最近清理记录 + 待处理提醒（3.0UI设计.md 页面1）。
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
    QFrame, QScrollArea,
)

from ...database import Database
from ...scheduler import CleanScheduler
from ...utils.paths import format_size


class _StatCard(QFrame):
    """统计卡片。"""

    def __init__(self, title: str, value: str, sub: str = ""):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "QFrame{background:#f5f7fa;border:1px solid #e0e4ea;border-radius:8px;}"
            "QLabel{color:#333;}"
        )
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(title))
        value_label = QLabel(value)
        value_label.setStyleSheet("font-size:22px;font-weight:bold;color:#2c3e50;")
        layout.addWidget(value_label)
        sub_label = QLabel(sub)
        sub_label.setStyleSheet("font-size:11px;color:#888;")
        layout.addWidget(sub_label)


class OverviewPage(QWidget):
    """概览仪表盘。"""

    def __init__(self, db: Database):
        super().__init__()
        self.db = db

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel("📋 概览")
        title.setStyleSheet("font-size:18px;font-weight:bold;")
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self.refresh)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)

        # 统计卡片
        cards = QHBoxLayout()
        self.card_entries = _StatCard("虚拟条目", "0")
        self.card_today = _StatCard("今日清理", "0 文件", "释放 0")
        self.card_recycle = _StatCard("回收站占用", "0", "保留中")
        cards.addWidget(self.card_entries)
        cards.addWidget(self.card_today)
        cards.addWidget(self.card_recycle)
        layout.addLayout(cards)

        # 待处理到期条目
        self.due_widget = QLabel()
        self.due_widget.setWordWrap(True)
        self.due_widget.setStyleSheet(
            "background:#fff3cd;color:#856404;padding:8px;border-radius:4px;"
        )
        layout.addWidget(self.due_widget)

        # 最近清理记录
        layout.addWidget(QLabel("\n📋 最近清理记录"))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.logs_container = QWidget()
        self.logs_layout = QVBoxLayout(self.logs_container)
        self.logs_layout.addStretch()
        self.scroll.setWidget(self.logs_container)
        layout.addWidget(self.scroll, 1)

        self.refresh()

    def refresh(self) -> None:
        """刷新页面数据。"""
        entries = self.db.list_entries()
        self._set_card_value(self.card_entries, "虚拟条目", str(len(entries)))

        recycle = self.db.list_recycle_items()
        recycle_bytes = sum(i.size_bytes for i in recycle)
        self._set_card_value(self.card_recycle, "回收站占用", format_size(recycle_bytes))

        # 今日清理
        from datetime import datetime
        today = datetime.now().date()
        today_logs = [l for l in self.db.list_logs(500)
                      if l.time.date() == today]
        today_count = sum(l.file_count for l in today_logs)
        today_bytes = sum(l.total_bytes for l in today_logs)
        self._set_card_value(
            self.card_today, "今日清理",
            f"{today_count} 文件", f"释放 {format_size(today_bytes)}"
        )

        # 到期提醒
        due = CleanScheduler(self.db).check_due_entries()
        if due:
            names = ", ".join(d.entry.name for d in due)
            self.due_widget.setText(f"⚠️ 待处理：{len(due)} 个条目已到期（{names}），可去『条目』页立即清理")
            self.due_widget.show()
        else:
            self.due_widget.hide()

        # 最近日志
        while self.logs_layout.count() > 1:
            item = self.logs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for log in self.db.list_logs(3):
            self.logs_layout.insertWidget(
                0,
                QLabel(
                    f"├─ {log.time.strftime('%m-%d %H:%M')}  {log.entry_name}"
                    f"  清理 {log.file_count} 文件  释放 {format_size(log.total_bytes)}"
                ),
            )

    @staticmethod
    def _set_card_value(card: _StatCard, title: str, value: str, sub: str = ""):
        card.layout().itemAt(0).widget().setText(title)
        card.layout().itemAt(1).widget().setText(value)
        if sub:
            card.layout().itemAt(2).widget().setText(sub)
