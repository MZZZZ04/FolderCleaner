"""
弹窗集合：
    - EntryDialog：添加/编辑虚拟条目（3.0UI设计.md 页面2a）
    - CleanConfirmDialog：删除前预览确认（3.0UI设计.md 文件选择预览界面）
    - CompensateDialog：启动补偿提示框（3.0UI设计.md 🚨 提示框 v2）
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QRadioButton, QScrollArea, QSpinBox, QTimeEdit, QVBoxLayout, QWidget,
    QDateEdit, QAbstractItemView, QGroupBox, QGridLayout,
)
from PySide6.QtCore import QDate, QTime

from ..models import CleanRule, Schedule, VirtualEntry
from ..utils.paths import format_duration, format_size, validate_target_path


class EntryDialog(QDialog):
    """添加/编辑虚拟条目弹窗。"""

    def __init__(self, entry: VirtualEntry | None = None, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setWindowTitle("编辑虚拟条目" if entry else "添加虚拟条目")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)

        # ── 基本信息 ──
        layout.addWidget(QLabel("虚拟名称:"))
        self.name_edit = QLineEdit(entry.name if entry else "")
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("物理路径:"))
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(entry.physical_path if entry else "")
        browse_btn = QPushButton("浏览…")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        # ── 清理规则 ──
        rule_box = QGroupBox("清理规则（可多选组合）")
        rule_layout = QVBoxLayout(rule_box)

        self.age_check = QCheckBox("按天数（N 天前未修改）")
        self.age_spin = QSpinBox()
        self.age_spin.setRange(1, 3650)
        self.age_spin.setValue(30)
        age_row = QHBoxLayout()
        age_row.addWidget(self.age_check)
        age_row.addWidget(self.age_spin)
        age_row.addStretch()
        rule_layout.addLayout(age_row)

        self.size_check = QCheckBox("按目录大小（超过 MB 删最旧）")
        self.size_spin = QSpinBox()
        self.size_spin.setRange(1, 102400)
        self.size_spin.setValue(500)
        size_row = QHBoxLayout()
        size_row.addWidget(self.size_check)
        size_row.addWidget(self.size_spin)
        size_row.addStretch()
        rule_layout.addLayout(size_row)

        rule_layout.addWidget(QLabel("按文件类型（后缀，逗号分隔）:"))
        self.ext_edit = QLineEdit()
        self.ext_edit.setPlaceholderText(".tmp, .log, .bak")
        rule_layout.addWidget(self.ext_edit)

        rule_layout.addWidget(QLabel("按文件名关键词:"))
        self.keyword_edit = QLineEdit()
        self.keyword_edit.setPlaceholderText("temp, cache")
        rule_layout.addWidget(self.keyword_edit)

        self.clear_all_check = QCheckBox("清空整个文件夹（⚠️ 需二次确认）")
        rule_layout.addWidget(self.clear_all_check)

        rule_layout.addWidget(QLabel("白名单例外（永不删除）:"))
        self.whitelist_edit = QLineEdit()
        self.whitelist_edit.setPlaceholderText(".git, readme.md")
        rule_layout.addWidget(self.whitelist_edit)

        layout.addWidget(rule_box)

        # ── 定时调度 ──
        sched_box = QGroupBox("定时调度")
        sched_layout = QGridLayout(sched_box)

        self.daily_radio = QRadioButton("每天")
        self.daily_time = QTimeEdit(QTime(20, 0))
        self.interval_radio = QRadioButton("每")
        self.interval_days = QSpinBox()
        self.interval_days.setRange(1, 365)
        self.interval_days.setValue(3)
        self.weekly_radio = QRadioButton("每周")
        self.weekly_weekday = QComboBox()
        self.weekly_weekday.addItems(["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
        self.weekly_time = QTimeEdit(QTime(9, 0))
        self.once_radio = QRadioButton("指定日期")
        self.once_date = QDateEdit(QDate.currentDate().addDays(1))
        self.once_date.setCalendarPopup(True)
        self.once_date.setMinimumDate(QDate.currentDate())  # 不允许选今天之前
        self.once_time = QTimeEdit(QTime(20, 0))

        sched_layout.addWidget(self.daily_radio, 0, 0)
        sched_layout.addWidget(self.daily_time, 0, 1)
        sched_layout.addWidget(self.interval_radio, 1, 0)
        sched_layout.addWidget(self.interval_days, 1, 1)
        sched_layout.addWidget(QLabel("天"), 1, 2)
        sched_layout.addWidget(self.weekly_radio, 2, 0)
        sched_layout.addWidget(self.weekly_weekday, 2, 1)
        sched_layout.addWidget(self.weekly_time, 2, 2)
        sched_layout.addWidget(self.once_radio, 3, 0)
        sched_layout.addWidget(self.once_date, 3, 1)
        sched_layout.addWidget(self.once_time, 3, 2)

        layout.addWidget(sched_box)

        # ── 按钮 ──
        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("💾 保存")
        save_btn.setStyleSheet("background:#27ae60;color:white;padding:6px 20px;")
        save_btn.clicked.connect(self._on_save)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        self._load_from_entry()

    def _browse(self) -> None:
        """选择物理路径文件夹。"""
        start = self.path_edit.text() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹", start)
        if folder:
            self.path_edit.setText(folder)

    def _load_from_entry(self) -> None:
        """编辑时回填已有配置。"""
        if not self.entry:
            self.daily_radio.setChecked(True)
            return
        rule = self.entry.rule
        if rule.by_age_days is not None:
            self.age_check.setChecked(True)
            self.age_spin.setValue(rule.by_age_days)
        if rule.by_size_mb is not None:
            self.size_check.setChecked(True)
            self.size_spin.setValue(rule.by_size_mb)
        if rule.by_extensions:
            self.ext_edit.setText(", ".join(rule.by_extensions))
        if rule.by_keywords:
            self.keyword_edit.setText(", ".join(rule.by_keywords))
        if rule.clear_all:
            self.clear_all_check.setChecked(True)
        if rule.whitelist:
            self.whitelist_edit.setText(", ".join(rule.whitelist))

        sched = self.entry.schedule
        if sched.kind == "daily":
            self.daily_radio.setChecked(True)
            self.daily_time.setTime(QTime(*_parse_hhmm(sched.time)))
        elif sched.kind == "interval":
            self.interval_radio.setChecked(True)
            self.interval_days.setValue(sched.interval_days)
        elif sched.kind == "weekly":
            self.weekly_radio.setChecked(True)
            self.weekly_weekday.setCurrentIndex(max(0, min(6, sched.weekday)))
            self.weekly_time.setTime(QTime(*_parse_hhmm(sched.time)))
        elif sched.kind == "once" and sched.once_date:
            self.once_radio.setChecked(True)
            try:
                loaded = QDate.fromString(sched.once_date, "yyyy-MM-dd")
                if loaded.isValid() and loaded < QDate.currentDate():
                    # 遗留的过去日期：放开最小日期忠实显示（保存时仍会校验拒绝）
                    self.once_date.setMinimumDate(QDate(1900, 1, 1))
                    self.once_date.setDate(loaded)
                else:
                    self.once_date.setDate(loaded)
            except Exception:
                pass
            # 时间优先取实际调度时间（兼容旧版本 once：无时间字段、实际按 00:00 触发）
            due = self.entry.next_due_time
            if due and due.date().isoformat() == sched.once_date:
                self.once_time.setTime(QTime(due.hour, due.minute))
            else:
                self.once_time.setTime(QTime(*_parse_hhmm(sched.time)))
        else:
            self.daily_radio.setChecked(True)

    def get_entry(self) -> VirtualEntry:
        """返回填写完成的条目对象。"""
        # 规则
        rule = CleanRule()
        if self.age_check.isChecked():
            rule.by_age_days = self.age_spin.value()
        if self.size_check.isChecked():
            rule.by_size_mb = self.size_spin.value()
        ext_text = self.ext_edit.text().strip()
        if ext_text:
            rule.by_extensions = [e.strip() for e in ext_text.split(",") if e.strip()]
        kw_text = self.keyword_edit.text().strip()
        if kw_text:
            rule.by_keywords = [k.strip() for k in kw_text.split(",") if k.strip()]
        rule.clear_all = self.clear_all_check.isChecked()
        wl_text = self.whitelist_edit.text().strip()
        if wl_text:
            rule.whitelist = [w.strip() for w in wl_text.split(",") if w.strip()]

        # 调度
        sched = Schedule()
        if self.daily_radio.isChecked():
            sched.kind = "daily"
            sched.time = self.daily_time.time().toString("HH:mm")
        elif self.interval_radio.isChecked():
            sched.kind = "interval"
            sched.interval_days = self.interval_days.value()
        elif self.weekly_radio.isChecked():
            sched.kind = "weekly"
            sched.weekday = self.weekly_weekday.currentIndex()
            sched.time = self.weekly_time.time().toString("HH:mm")
        else:
            sched.kind = "once"
            sched.once_date = self.once_date.date().toString("yyyy-MM-dd")
            sched.time = self.once_time.time().toString("HH:mm")

        # 条目
        entry = self.entry or VirtualEntry()
        entry.entry_id = entry.entry_id or uuid.uuid4().hex
        entry.name = self.name_edit.text().strip() or "未命名条目"
        entry.physical_path = self.path_edit.text().strip()
        entry.rule = rule
        entry.schedule = sched
        if not entry.last_clean_time:
            entry.last_clean_time = None
        return entry

    def _on_save(self) -> None:
        """校验并保存。"""
        path = self.path_edit.text().strip()
        try:
            validate_target_path(path)
        except ValueError as e:
            QMessageBox.warning(self, "路径无效", str(e))
            return
        if not self.age_check.isChecked() and not self.size_check.isChecked() \
                and not self.ext_edit.text().strip() and not self.keyword_edit.text().strip() \
                and not self.clear_all_check.isChecked():
            QMessageBox.warning(self, "缺少规则", "请至少启用一条清理规则")
            return
        if self.once_radio.isChecked():
            once_dt = datetime.strptime(
                f"{self.once_date.date().toString('yyyy-MM-dd')} "
                f"{self.once_time.time().toString('HH:mm')}",
                "%Y-%m-%d %H:%M",
            )
            if once_dt <= datetime.now():
                QMessageBox.warning(self, "时间无效", "指定日期时间必须晚于当前时间")
                return
        self.accept()

    def get_selected_files(self) -> list:
        """兼容接口。"""
        return []


class CleanConfirmDialog(QDialog):
    """删除前预览确认弹窗（文件可勾选）。"""

    def __init__(self, grouped_files: dict, parent=None):
        """Args:
            grouped_files: {条目名: [Path, ...]} — 按条目分组的待清理文件
        """
        super().__init__(parent)
        self.setWindowTitle("待清理文件确认")
        self.setMinimumSize(640, 480)
        self._selected: list[Path] = []

        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.NoSelection)

        # 分组标题 ↔ 文件勾选联动（QListWidgetItem 不可哈希，用 id 作键）
        self._groups: list = []              # 分组标题项
        self._children_by_group: dict = {}   # id(分组标题) → 其下文件项
        self._updating = False

        for entry_name, files in grouped_files.items():
            group_item = QListWidgetItem(f"📁 {entry_name}（{len(files)} 个文件）")
            group_item.setFlags(group_item.flags() | Qt.ItemIsUserCheckable)
            group_item.setCheckState(Qt.Checked)
            self.list_widget.addItem(group_item)
            self._groups.append(group_item)
            children = []
            for f in sorted(files, key=_safe_size, reverse=True):
                if not f.exists():
                    continue
                item = QListWidgetItem(f"    ☑ {f.name}  ·  {format_size(_safe_size(f))}")
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                item.setData(Qt.UserRole, str(f))
                self.list_widget.addItem(item)
                children.append(item)
            self._children_by_group[id(group_item)] = children

        self.list_widget.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.list_widget)

        # 底部统计 + 全选/全不选
        bottom = QHBoxLayout()
        self.stats_label = QLabel("已选 0 个文件")
        bottom.addWidget(self.stats_label)
        bottom.addStretch()
        sel_all = QPushButton("全选")
        sel_all.clicked.connect(lambda: self._set_all(True))
        sel_none = QPushButton("全不选")
        sel_none.clicked.connect(lambda: self._set_all(False))
        bottom.addWidget(sel_all)
        bottom.addWidget(sel_none)
        layout.addLayout(bottom)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("🚚 移入回收站")
        ok_btn.setStyleSheet("background:#e67e22;color:white;padding:6px 20px;")
        ok_btn.clicked.connect(self._on_ok)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        self._update_stats()

    def _on_item_changed(self, item) -> None:
        """勾选状态变化：分组标题↔文件双向同步。"""
        if self._updating:
            return
        if id(item) in self._children_by_group:
            # 分组标题切换 → 级联其下所有文件
            self._set_children_state(item, item.checkState())
        else:
            # 文件切换 → 同步所属分组标题状态
            self._sync_group_states()
        self._update_stats()

    def _set_children_state(self, group_item, state) -> None:
        """将分组下所有文件的勾选状态设为 state。"""
        self._updating = True
        try:
            for child in self._children_by_group.get(id(group_item), []):
                child.setCheckState(state)
        finally:
            self._updating = False

    def _sync_group_states(self) -> None:
        """按各分组下文件的勾选情况同步分组标题（全选/部分/全不选）。"""
        self._updating = True
        try:
            for group_item in self._groups:
                children = self._children_by_group.get(id(group_item), [])
                if not children:
                    continue
                checked = sum(1 for c in children if c.checkState() == Qt.Checked)
                if checked == len(children):
                    state = Qt.Checked
                elif checked == 0:
                    state = Qt.Unchecked
                else:
                    state = Qt.PartiallyChecked
                group_item.setCheckState(state)
        finally:
            self._updating = False

    def _set_all(self, checked: bool) -> None:
        """全选/全不选：文件与分组标题同步更新。"""
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.UserRole) is not None:
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        for group_item in self._groups:
            group_item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.list_widget.blockSignals(False)
        self._update_stats()

    def _update_stats(self) -> None:
        self._selected = self.get_selected_files()
        total = sum(_safe_size(p) for p in self._selected)
        self.stats_label.setText(
            f"已选 {len(self._selected)} 个文件 | 共 {format_size(total)}"
        )

    def _on_ok(self) -> None:
        if not self._selected:
            QMessageBox.warning(self, "未选择", "请至少勾选一个文件")
            return
        self.accept()

    def get_selected_files(self) -> list:
        files = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            path = item.data(Qt.UserRole)
            if path and item.checkState() == Qt.Checked:
                files.append(Path(path))
        return files


class CompensateDialog(QDialog):
    """启动补偿提示框（兜底模式）。"""

    # 返回码
    ACTION_VIEW_SELECT = 1   # 查看并选择
    ACTION_CLEAN_ALL = 2     # 立即清理全部
    ACTION_SKIP = 3          # 暂不清理

    def __init__(self, due_entries: list, parent=None):
        """Args:
            due_entries: scheduler.DueEntry 列表（含条目 + 过期时长）
        """
        super().__init__(parent)
        self.setWindowTitle("启动补偿 — 到期条目")
        self.setMinimumWidth(420)
        self.result_action = CompensateDialog.ACTION_SKIP

        layout = QVBoxLayout(self)
        title = QLabel(f"⚠️ 检测到 {len(due_entries)} 个条目已到期")
        title.setStyleSheet("font-size:14px;font-weight:bold;")
        layout.addWidget(title)

        for due in due_entries:
            line = QLabel(
                f"📁 {due.entry.name}\n    {due.entry.physical_path}"
                f"\n    已过期 {format_duration(due.overdue_seconds)}"
            )
            line.setStyleSheet("color:#555;padding:4px 0;")
            layout.addWidget(line)

        layout.addWidget(QLabel("\n到期期间程序未运行，请选择处理方式:"))

        btn_row = QHBoxLayout()
        view_btn = QPushButton("🔍 查看并选择要清理的文件")
        view_btn.setStyleSheet("background:#8e44ad;color:white;")
        view_btn.clicked.connect(lambda: self._finish(CompensateDialog.ACTION_VIEW_SELECT))
        clean_btn = QPushButton("🕐 立即清理全部")
        clean_btn.setStyleSheet("background:#27ae60;color:white;")
        clean_btn.clicked.connect(lambda: self._finish(CompensateDialog.ACTION_CLEAN_ALL))
        skip_btn = QPushButton("⏰ 暂不清理")
        skip_btn.clicked.connect(lambda: self._finish(CompensateDialog.ACTION_SKIP))
        btn_row.addWidget(view_btn)
        btn_row.addWidget(clean_btn)
        btn_row.addWidget(skip_btn)
        layout.addLayout(btn_row)

    def _finish(self, action: int) -> None:
        self.result_action = action
        self.accept()


def _safe_size(p: Path) -> int:
    """安全取文件大小，文件被删/不可访问时返回 0。"""
    try:
        return p.stat().st_size
    except OSError:
        return 0


def _parse_hhmm(time_str: str) -> tuple[int, int]:
    """解析 "HH:MM" → (hour, minute)。"""
    try:
        hh, mm = time_str.split(":")
        return max(0, min(23, int(hh))), max(0, min(59, int(mm)))
    except Exception:
        return 20, 0
