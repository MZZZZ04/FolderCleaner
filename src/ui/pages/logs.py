"""
📜 日志页 — 清理记录列表 + 搜索 + 导出（3.0UI设计.md 页面4）。
"""

from __future__ import annotations

import csv
from datetime import datetime

from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from ...database import Database
from ...utils.paths import format_size

TRIGGER_LABELS = {
    "auto": "自动清理",
    "manual": "手动清理",
    "compensate": "启动补偿",
    "recycle_purge": "回收站清空",
}


class LogsPage(QWidget):
    """清理日志页。"""

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self._all_logs = []

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("📜 日志"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 搜索关键词…")
        self.search_edit.setMaximumWidth(220)
        self.search_edit.textChanged.connect(self._on_search)
        export_btn = QPushButton("📤 导出")
        export_btn.clicked.connect(self._on_export)
        header.addStretch()
        header.addWidget(self.search_edit)
        header.addWidget(export_btn)
        layout.addLayout(header)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["时间", "触发方式", "条目名", "文件数", "释放空间", "结果"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        self.refresh()

    def refresh(self) -> None:
        """刷新日志列表。"""
        self._all_logs = self.db.list_logs(500)
        self._render(self._all_logs)

    def _render(self, logs) -> None:
        self.table.setRowCount(len(logs))
        for row, log in enumerate(logs):
            self.table.setItem(row, 0, QTableWidgetItem(log.time.strftime("%Y-%m-%d %H:%M")))
            self.table.setItem(row, 1, QTableWidgetItem(TRIGGER_LABELS.get(log.trigger, log.trigger)))
            self.table.setItem(row, 2, QTableWidgetItem(log.entry_name))
            self.table.setItem(row, 3, QTableWidgetItem(str(log.file_count)))
            self.table.setItem(row, 4, QTableWidgetItem(format_size(log.total_bytes)))
            self.table.setItem(row, 5, QTableWidgetItem(log.result))

    def _on_search(self, keyword: str) -> None:
        """按关键词过滤日志。"""
        kw = keyword.strip().lower()
        if not kw:
            self._render(self._all_logs)
            return
        filtered = [
            l for l in self._all_logs
            if kw in l.entry_name.lower() or kw in l.trigger.lower()
        ]
        self._render(filtered)

    def _on_export(self) -> None:
        """导出日志为 CSV。"""
        path, _ = QFileDialog.getSaveFileName(self, "导出日志", "clean_logs.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["时间", "触发方式", "条目名", "文件数", "释放空间(字节)", "结果"])
                for log in self._all_logs:
                    writer.writerow([
                        log.time.strftime("%Y-%m-%d %H:%M"),
                        TRIGGER_LABELS.get(log.trigger, log.trigger),
                        log.entry_name,
                        log.file_count,
                        log.total_bytes,
                        log.result,
                    ])
            QMessageBox.information(self, "导出成功", f"已导出到:\n{path}")
        except OSError as e:
            QMessageBox.warning(self, "导出失败", str(e))
