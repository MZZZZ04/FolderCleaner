"""
系统托盘（常驻后台）— 3.0UI设计.md 🗔 托盘菜单。

菜单：打开主界面 / 立即清理所有到期条目 / 上次清理 / 下次清理 / 退出
"""

from __future__ import annotations

from PySide6.QtWidgets import QMenu, QSystemTrayIcon
from PySide6.QtGui import QIcon
from PySide6.QtCore import QObject, Qt, Signal


class TrayIcon(QSystemTrayIcon):
    """托盘图标。"""

    show_requested = Signal()
    clean_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.setIcon(self._make_icon())
        self.setToolTip("定时清理指定文件夹")

        self._menu = QMenu()
        self.show_action = self._menu.addAction("🗔 打开主界面")
        self.clean_action = self._menu.addAction("🧹 立即清理所有到期条目")
        self._menu.addSeparator()
        self.last_label = self._menu.addAction("上次清理: -")
        self.next_label = self._menu.addAction("下次清理: -")
        self.last_label.setEnabled(False)
        self.next_label.setEnabled(False)
        self._menu.addSeparator()
        self.quit_action = self._menu.addAction("退出")

        self.setContextMenu(self._menu)

        self.activated.connect(self._on_activated)
        self.show_action.triggered.connect(self.show_requested)
        self.clean_action.triggered.connect(self.clean_requested)
        self.quit_action.triggered.connect(self.quit_requested)

    def _make_icon(self) -> QIcon:
        """托盘图标：优先用程序图标文件，资源缺失时绘制简单时钟兜底。"""
        from ..config import get_icon_path
        p = get_icon_path()
        if p.exists():
            return QIcon(str(p))
        from PySide6.QtGui import QColor, QPainter, QPixmap
        pm = QPixmap(64, 64)
        pm.fill(QColor("transparent"))
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#2c3e50"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(6, 6, 52, 52)
        painter.setPen(QColor("white"))
        painter.drawEllipse(16, 16, 32, 32)
        painter.end()
        return QIcon(pm)

    def update_menu(self, last_clean: str = "", next_clean: str = "") -> None:
        """更新托盘菜单中的清理时间信息。"""
        self.last_label.setText(f"上次清理: {last_clean or '-'}")
        self.next_label.setText(f"下次清理: {next_clean or '-'}")

    def _on_activated(self, reason) -> None:
        """单击托盘图标恢复窗口。"""
        if reason == QSystemTrayIcon.Trigger:
            self.show_requested.emit()
