"""
⚙️ 设置页 — 通用 / 回收站 / 安全 三组配置（3.0UI设计.md 页面5）。
"""

from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from ...config import get_recycle_dir
from ...database import Database

KEY_AUTO_START = "auto_start"
KEY_NOTIFY = "notify_on_clean"
KEY_CHECK_DUE = "check_due_on_start"
KEY_RETENTION = "recycle_retention_days"
KEY_RECYCLE_DIR = "recycle_dir"
KEY_PREVIEW = "preview_before_clean"
KEY_PROTECT = "protect_system_paths"
KEY_SKIP_IN_USE = "skip_in_use_files"


class SettingsPage(QWidget):
    """设置页。"""

    def __init__(self, db: Database):
        super().__init__()
        self.db = db

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("⚙️ 设置"))

        # ── 通用 ──
        general = QGroupBox("通用")
        general_layout = QVBoxLayout(general)
        self.auto_start = QCheckBox("开机自启（常驻后台）")
        self.notify = QCheckBox("清理完成后通知")
        self.check_due = QCheckBox("启动时检查到期条目（兜底提示）")
        general_layout.addWidget(self.auto_start)
        general_layout.addWidget(self.notify)
        general_layout.addWidget(self.check_due)
        layout.addWidget(general)

        # ── 回收站 ──
        recycle = QGroupBox("回收站")
        recycle_layout = QVBoxLayout(recycle)
        retention_row = QHBoxLayout()
        retention_row.addWidget(QLabel("保留时间:"))
        self.retention_spin = QSpinBox()
        self.retention_spin.setRange(1, 365)
        self.retention_spin.setSuffix(" 天")
        retention_row.addWidget(self.retention_spin)
        retention_row.addStretch()
        recycle_layout.addLayout(retention_row)
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("回收站路径:"))
        self.recycle_dir_edit = QLineEdit()
        browse_btn = QPushButton("📂 更改")
        browse_btn.clicked.connect(self._browse_recycle_dir)
        path_row.addWidget(self.recycle_dir_edit, 1)
        path_row.addWidget(browse_btn)
        recycle_layout.addLayout(path_row)
        layout.addWidget(recycle)

        # ── 安全 ──
        safety = QGroupBox("安全")
        safety_layout = QVBoxLayout(safety)
        self.preview_check = QCheckBox("删除前预览确认（自动清理时也确认）")
        self.protect_check = QCheckBox("系统路径保护（禁止清理系统盘根目录）")
        self.skip_in_use = QCheckBox("跳过正在使用的文件")
        safety_layout.addWidget(self.preview_check)
        safety_layout.addWidget(self.protect_check)
        safety_layout.addWidget(self.skip_in_use)
        layout.addWidget(safety)

        layout.addStretch()

        # ── 按钮 ──
        btn_row = QHBoxLayout()
        reset_btn = QPushButton("恢复默认")
        reset_btn.clicked.connect(self._on_reset_defaults)
        save_btn = QPushButton("💾 保存设置")
        save_btn.setStyleSheet("background:#27ae60;color:white;padding:8px 24px;")
        save_btn.clicked.connect(self.save_settings)
        btn_row.addStretch()
        btn_row.addWidget(reset_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        self.load_settings()

    def _browse_recycle_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择回收站文件夹")
        if folder:
            self.recycle_dir_edit.setText(folder)

    def load_settings(self) -> None:
        """从数据库加载设置到界面。"""
        self.auto_start.setChecked(self.db.get_setting(KEY_AUTO_START, "1") == "1")
        self.notify.setChecked(self.db.get_setting(KEY_NOTIFY, "1") == "1")
        self.check_due.setChecked(self.db.get_setting(KEY_CHECK_DUE, "1") == "1")
        self.retention_spin.setValue(int(self.db.get_setting(KEY_RETENTION, "7")))
        custom = self.db.get_setting(KEY_RECYCLE_DIR, "").strip()
        self.recycle_dir_edit.setText(custom or str(get_recycle_dir()))
        self.preview_check.setChecked(self.db.get_setting(KEY_PREVIEW, "1") == "1")
        self.protect_check.setChecked(self.db.get_setting(KEY_PROTECT, "1") == "1")
        self.skip_in_use.setChecked(self.db.get_setting(KEY_SKIP_IN_USE, "1") == "1")

    def save_settings(self) -> None:
        """保存界面设置到数据库。"""
        self.db.set_setting(KEY_AUTO_START, "1" if self.auto_start.isChecked() else "0")
        self.db.set_setting(KEY_NOTIFY, "1" if self.notify.isChecked() else "0")
        self.db.set_setting(KEY_CHECK_DUE, "1" if self.check_due.isChecked() else "0")
        self.db.set_setting(KEY_RETENTION, str(self.retention_spin.value()))
        # 路径等于默认值时存空串（保持"空=默认目录"语义，避免打包后移动 exe 失效）
        recycle_dir = self.recycle_dir_edit.text().strip()
        default_dir = str(get_recycle_dir())
        if not recycle_dir or os.path.normcase(recycle_dir.rstrip("\\/")) == os.path.normcase(default_dir.rstrip("\\/")):
            recycle_dir = ""
        self.db.set_setting(KEY_RECYCLE_DIR, recycle_dir)
        self.db.set_setting(KEY_PREVIEW, "1" if self.preview_check.isChecked() else "0")
        self.db.set_setting(KEY_PROTECT, "1" if self.protect_check.isChecked() else "0")
        self.db.set_setting(KEY_SKIP_IN_USE, "1" if self.skip_in_use.isChecked() else "0")
        QMessageBox.information(self, "已保存", "设置已保存")

    def _on_reset_defaults(self) -> None:
        """恢复默认设置。"""
        ret = QMessageBox.question(self, "恢复默认", "确定恢复所有设置为默认值？")
        if ret != QMessageBox.Yes:
            return
        self.db.set_setting(KEY_AUTO_START, "1")
        self.db.set_setting(KEY_NOTIFY, "1")
        self.db.set_setting(KEY_CHECK_DUE, "1")
        self.db.set_setting(KEY_RETENTION, "7")
        self.db.set_setting(KEY_RECYCLE_DIR, "")
        self.db.set_setting(KEY_PREVIEW, "1")
        self.db.set_setting(KEY_PROTECT, "1")
        self.db.set_setting(KEY_SKIP_IN_USE, "1")
        self.load_settings()
        QMessageBox.information(self, "已恢复", "设置已恢复默认")
