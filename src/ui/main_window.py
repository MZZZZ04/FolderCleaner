"""
主窗口 — 侧边导航 + 内容区 + 状态栏（3.0UI设计.md 整体架构）。

页面（侧边导航 5 项）：
    📋 概览    → pages.OverviewPage
    📁 条目    → pages.EntriesPage
    🗑️ 回收站  → pages.RecyclePage
    📜 日志    → pages.LogsPage
    ⚙️ 设置    → pages.SettingsPage
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QStackedWidget, QVBoxLayout, QWidget,
)

from ..cleaner.engine import CleanEngine
from ..cleaner.recycle import RecycleBin
from ..database import Database
from ..scheduler import CleanScheduler
from .pages.clean_runner import run_preview_confirm
from .pages.entries import EntriesPage
from .pages.logs import LogsPage
from .pages.overview import OverviewPage
from .pages.recycle import RecyclePage
from .pages.settings import SettingsPage
from .tray import TrayIcon


class MainWindow(QMainWindow):
    """应用主窗口。"""

    scheduled_clean_requested = Signal(object)  # 后台线程 → 主线程的清理请求

    def __init__(self, db: Database, engine: CleanEngine,
                 recycle_bin: RecycleBin, scheduler: CleanScheduler | None = None):
        super().__init__()
        self.db = db
        self.engine = engine
        self.recycle_bin = recycle_bin
        self.scheduler = scheduler

        self.setWindowTitle("定时清理指定文件夹")
        self.resize(920, 620)
        self.setMinimumSize(760, 480)

        # 组件
        self.tray: TrayIcon | None = None
        self._pages: dict = {}

        self.scheduled_clean_requested.connect(self._run_scheduled_clean)

        self._build_nav()
        self._build_status_bar()

        # 界面字体
        self.setStyleSheet(
            "QMainWindow, QWidget{font-family:'Microsoft YaHei UI';font-size:13px;}"
        )

    # ---------- 导航 ----------

    def _build_nav(self) -> None:
        """构建侧边导航 + 内容区。"""
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 侧边导航
        self.nav = QListWidget()
        self.nav.setFixedWidth(140)
        self.nav.setStyleSheet(
            "QListWidget{background:#2c3e50;color:white;border:none;font-size:14px;}"
            "QListWidget::item{padding:14px 16px;}"
            "QListWidget::item:selected{background:#1abc9c;}"
            "QListWidget::item:hover{background:#34495e;}"
        )
        nav_items = ["📋 概览", "📁 条目", "🗑️ 回收站", "📜 日志", "⚙️ 设置"]
        self.pages_stack = QStackedWidget()

        for i, label in enumerate(nav_items):
            item = QListWidgetItem(label)
            self.nav.addItem(item)
            self._pages[i] = self._create_page(i)

        self.nav.currentRowChanged.connect(self._on_nav_changed)
        self.nav.setCurrentRow(0)

        layout.addWidget(self.nav)
        layout.addWidget(self.pages_stack, 1)
        self.setCentralWidget(central)

    def _on_nav_changed(self, index: int) -> None:
        """切换页面时刷新目标页，避免展示清理后的陈旧数据。"""
        self.pages_stack.setCurrentIndex(index)
        page = self._pages.get(index)
        if page is not None and hasattr(page, "refresh"):
            page.refresh()

    def _create_page(self, index: int) -> QWidget:
        """创建对应导航项的页面。"""
        if index == 0:
            page = OverviewPage(self.db)
        elif index == 1:
            page = EntriesPage(self.db, self.engine)
            page.entries_changed.connect(self._on_entries_changed)
        elif index == 2:
            page = RecyclePage(self.db, self.recycle_bin)
        elif index == 3:
            page = LogsPage(self.db)
        else:
            page = SettingsPage(self.db)
        self.pages_stack.addWidget(page)
        return page

    # ---------- 状态栏 ----------

    def _build_status_bar(self) -> None:
        """构建底部状态栏。"""
        sb = self.statusBar()
        sb.setStyleSheet("background:#f0f2f5;")

        self.status_running = QLabel("● 后台运行中")
        self.status_running.setStyleSheet("color:#27ae60;padding:0 12px;")
        self.status_next = QLabel("下次清理: -")
        self.status_count = QLabel("共 0 条目")
        sb.addWidget(self.status_running)
        sb.addPermanentWidget(self.status_next)
        sb.addPermanentWidget(self.status_count)

    def set_status_info(self, next_clean: str = "", entry_count: int = 0) -> None:
        """更新状态栏信息。"""
        self.status_next.setText(f"下次清理: {next_clean or '-'}")
        self.status_count.setText(f"共 {entry_count} 条目")

    # ---------- 调度触发 ----------

    def _run_scheduled_clean(self, entry) -> None:
        """调度到点执行清理（主线程，信号转发保证线程安全）。"""
        preview_enabled = self.db.get_setting("preview_before_clean", "1") == "1"
        if preview_enabled:
            run_preview_confirm(self, self.engine, entry, trigger="auto")
        else:
            self.engine.clean(entry, None, trigger="auto")
        self.refresh_all()

    def _on_entries_changed(self) -> None:
        """条目增删改后：重新注册调度任务 + 全界面即时刷新。"""
        if self.scheduler:
            self.scheduler.refresh_jobs()
        self.refresh_all()

    # ---------- 托盘联动 ----------

    def attach_tray(self, tray: TrayIcon) -> None:
        """绑定托盘图标。"""
        self.tray = tray
        tray.show_requested.connect(self.show_from_tray)
        tray.clean_requested.connect(self._on_tray_clean)
        tray.quit_requested.connect(self.quit_app)

    def show_from_tray(self) -> None:
        """从托盘恢复窗口。"""
        self.show()
        self.raise_()
        self.activateWindow()
        self.refresh_all()

    def close_to_tray(self) -> None:
        """关闭时最小化到托盘。"""
        if self.tray and self.tray.isVisible():
            self.hide()
        else:
            self.close()

    def quit_app(self) -> None:
        """真正退出。"""
        if self.scheduler:
            self.scheduler.stop()
        self.close()
        if self.tray:
            self.tray.hide()

    def refresh_all(self) -> None:
        """刷新所有页面 + 状态栏/托盘时间。"""
        for page in self._pages.values():
            if hasattr(page, "refresh"):
                page.refresh()
        entries = self.db.list_entries()
        enabled = [e for e in entries if e.enabled and e.next_due_time]
        next_clean = min((e.next_due_time for e in enabled), default=None)
        next_str = next_clean.strftime("%m-%d %H:%M") if next_clean else "-"
        self.set_status_info(next_clean=next_str, entry_count=len(entries))
        self._update_tray_times()

    def _update_tray_times(self) -> None:
        """更新托盘菜单的时间信息。"""
        if not self.tray:
            return
        entries = self.db.list_entries()
        enabled = [e for e in entries if e.enabled and e.next_due_time]
        next_clean = min((e.next_due_time for e in enabled), default=None)
        next_str = next_clean.strftime("%m-%d %H:%M") if next_clean else "-"
        self.tray.update_menu(next_clean=next_str)

    def _on_tray_clean(self) -> None:
        """托盘"立即清理所有到期条目"。"""
        self.refresh_all()
        if self.scheduler:
            due = self.scheduler.check_due_entries()
        else:
            due = CleanScheduler(self.db).check_due_entries()
        if not due:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", "当前没有到期的条目")
            return
        from .dialogs import CompensateDialog
        dialog = CompensateDialog(due, self)
        if dialog.exec_() != CompensateDialog.Accepted:
            return
        if dialog.result_action == CompensateDialog.ACTION_CLEAN_ALL:
            for d in due:
                run_preview_confirm(self, self.engine, d.entry, trigger="compensate")
        elif dialog.result_action == CompensateDialog.ACTION_VIEW_SELECT:
            for d in due:
                run_preview_confirm(self, self.engine, d.entry, trigger="compensate")
        self.refresh_all()

    # ---------- 关闭事件 ----------

    def closeEvent(self, event) -> None:
        """拦截关闭事件：最小化到托盘而非退出。"""
        if self.tray and self.tray.isVisible():
            event.ignore()
            self.hide()
        else:
            event.accept()
