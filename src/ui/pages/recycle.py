"""
🗑️ 回收站页 — 文件表格 + 保留时间设置 + 恢复/删除/清空（3.0UI设计.md 页面3）。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ...cleaner.recycle import RecycleBin
from ...database import Database
from ...utils.paths import format_duration, format_size

RETENTION_OPTIONS = [("7 天", 7), ("14 天", 14), ("30 天", 30), ("60 天", 60)]


class RecyclePage(QWidget):
    """程序回收站页。"""

    def __init__(self, db: Database, recycle_bin: RecycleBin):
        super().__init__()
        self.db = db
        self.recycle_bin = recycle_bin

        layout = QVBoxLayout(self)

        # 顶部：保留时间
        top = QHBoxLayout()
        top.addWidget(QLabel("保留时间:"))
        self.retention_combo = QComboBox()
        for label, _ in RETENTION_OPTIONS:
            self.retention_combo.addItem(label)
        current_days = int(self.db.get_setting("recycle_retention_days", "7"))
        idx = next((i for i, (_, d) in enumerate(RETENTION_OPTIONS) if d == current_days), 0)
        self.retention_combo.setCurrentIndex(idx)
        self.retention_combo.currentIndexChanged.connect(self._on_retention_changed)
        save_btn = QPushButton("💾 保存")
        save_btn.clicked.connect(self._on_retention_changed)
        top.addWidget(self.retention_combo)
        top.addWidget(save_btn)
        warn = QLabel("⚠️ 到期自动清空所有文件")
        warn.setStyleSheet("color:#e67e22;")
        top.addWidget(warn)
        top.addStretch()
        layout.addLayout(top)

        # 全选 / 全不选 + 已选统计
        select_row = QHBoxLayout()
        self.sel_count_label = QLabel("已选 0 / 0")
        self.sel_count_label.setStyleSheet("color:#555;")
        select_row.addWidget(self.sel_count_label)
        select_row.addStretch()
        sel_all_btn = QPushButton("全选")
        sel_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        sel_none_btn = QPushButton("全不选")
        sel_none_btn.clicked.connect(lambda: self._set_all_checked(False))
        select_row.addWidget(sel_all_btn)
        select_row.addWidget(sel_none_btn)
        layout.addLayout(select_row)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["勾选", "文件名", "原路径", "大小", "剩余时间"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.itemChanged.connect(self._update_sel_count)
        layout.addWidget(self.table, 1)

        # 底部按钮
        bottom = QHBoxLayout()
        restore_btn = QPushButton("↩️ 恢复选中")
        restore_btn.setStyleSheet("background:#27ae60;color:white;padding:6px 16px;")
        restore_btn.clicked.connect(self._on_restore)
        del_btn = QPushButton("🗑️ 立即删除选中")
        del_btn.setStyleSheet("background:#e74c3c;color:white;padding:6px 16px;")
        del_btn.clicked.connect(self._on_delete_selected)
        purge_btn = QPushButton("🧹 立即清空全部")
        purge_btn.clicked.connect(self._on_purge_all)
        bottom.addStretch()
        bottom.addWidget(restore_btn)
        bottom.addWidget(del_btn)
        bottom.addWidget(purge_btn)
        layout.addLayout(bottom)

        self.refresh()

    def refresh(self) -> None:
        """刷新回收站列表。"""
        items = self.db.list_recycle_items()
        retention = int(self.db.get_setting("recycle_retention_days", "7"))
        now = datetime.now()

        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check.setCheckState(Qt.Unchecked)
            check.setData(Qt.UserRole, item.item_id)
            self.table.setItem(row, 0, check)
            self.table.setItem(row, 1, QTableWidgetItem(item.file_name))
            self.table.setItem(row, 2, QTableWidgetItem(item.original_path))
            self.table.setItem(row, 3, QTableWidgetItem(format_size(item.size_bytes)))
            if item.moved_at:
                remaining = retention - (now - item.moved_at).days
                self.table.setItem(row, 4, QTableWidgetItem(f"{max(0, remaining)} 天"))
            else:
                self.table.setItem(row, 4, QTableWidgetItem("-"))
        self._update_sel_count()

    def _update_sel_count(self) -> None:
        """实时刷新"已选 N / M"统计。"""
        total = self.table.rowCount()
        checked = sum(
            1 for r in range(total)
            if self.table.item(r, 0) and self.table.item(r, 0).checkState() == Qt.Checked
        )
        self.sel_count_label.setText(f"已选 {checked} / {total}")

    def _set_all_checked(self, checked: bool) -> None:
        """全选 / 全不选所有回收站条目。"""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)

    def _selected_item_ids(self) -> list[str]:
        ids = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                ids.append(item.data(Qt.UserRole))
        return ids

    def _on_restore(self) -> None:
        """恢复选中的文件回原路径。"""
        ids = self._selected_item_ids()
        if not ids:
            QMessageBox.information(self, "提示", "请先勾选要恢复的文件")
            return
        restored = 0
        for item in self.db.list_recycle_items():
            if item.item_id in ids and self.recycle_bin.restore(item):
                restored += 1
        QMessageBox.information(self, "恢复完成", f"已恢复 {restored} 个文件到原路径")
        self.refresh()

    def _on_delete_selected(self) -> None:
        """立即删除选中的文件（确认弹窗）。"""
        ids = self._selected_item_ids()
        if not ids:
            QMessageBox.information(self, "提示", "请先勾选要删除的文件")
            return
        ret = QMessageBox.question(
            self, "确认删除",
            f"立即永久删除选中的 {len(ids)} 个文件？\n（不可恢复）",
        )
        if ret != QMessageBox.Yes:
            return
        for item in self.db.list_recycle_items():
            if item.item_id in ids:
                self.recycle_bin.delete_now(item)
        self.refresh()

    def _on_purge_all(self) -> None:
        """立即清空回收站（确认弹窗）。"""
        count = len(self.db.list_recycle_items())
        if count == 0:
            QMessageBox.information(self, "提示", "回收站为空")
            return
        ret = QMessageBox.question(
            self, "确认清空",
            f"立即永久删除回收站全部 {count} 个文件？\n（不可恢复）",
        )
        if ret != QMessageBox.Yes:
            return
        self.recycle_bin.purge_all()
        self.refresh()

    def _on_retention_changed(self) -> None:
        """保存保留时间设置。"""
        days = RETENTION_OPTIONS[self.retention_combo.currentIndex()][1]
        self.db.set_setting("recycle_retention_days", str(days))
