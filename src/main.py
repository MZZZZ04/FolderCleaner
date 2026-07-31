"""
程序入口。

启动流程：
    1. 初始化数据库 / 回收站 / 清理引擎 / 调度器
    2. 启动后台调度器（常驻）
    3. 启动补偿检查 → 有到期条目 → 弹 CompensateDialog
    4. 显示主窗口（最小化到托盘）

运行：python -m src.main
"""

from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .cleaner.engine import CleanEngine
from .cleaner.recycle import RecycleBin
from .config import get_db_path, get_icon_path
from .database import Database
from .scheduler import CleanScheduler
from .ui.dialogs import CompensateDialog
from .ui.main_window import MainWindow
from .ui.pages.clean_runner import run_preview_confirm
from .ui.tray import TrayIcon

try:
    import pyi_splash  # PyInstaller 启动画面（仅打包后存在，开发环境无此模块）
except ImportError:
    pyi_splash = None


def main() -> int:
    """应用主函数。"""
    app = QApplication(sys.argv)
    app.setApplicationName("定时清理指定文件夹")
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口不退出，保留托盘
    # 主窗口 + 弹窗共用应用图标
    icon_path = get_icon_path()
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # 1. 初始化核心组件
    db = Database(get_db_path())
    recycle_bin = RecycleBin(db)  # 回收站路径优先取设置页配置

    # 定时清空过期回收站文件
    retention_days = int(db.get_setting("recycle_retention_days", "7"))
    recycle_bin.purge_expired(retention_days)

    engine = CleanEngine(db, recycle_bin)

    # 2. 主窗口（先创建，供调度回调引用）
    window = MainWindow(db, engine, recycle_bin)

    # 3. 调度器（到点自动清理）
    def on_scheduled_clean(entry):
        # 到点回调在 APScheduler 后台线程执行，不能直接操作 Qt，
        # 通过窗口信号转发到主线程再执行清理
        window.scheduled_clean_requested.emit(entry)

    scheduler = CleanScheduler(db, on_clean=on_scheduled_clean)
    scheduler.start()
    window.scheduler = scheduler

    # 4. 托盘
    tray = TrayIcon(window)
    tray.show()
    window.attach_tray(tray)

    # 5. 启动补偿检查
    check_due = db.get_setting("check_due_on_start", "1") == "1"
    if check_due:
        due = scheduler.check_due_entries()
        if due:
            dialog = CompensateDialog(due, window)
            if dialog.exec_() == CompensateDialog.Accepted:
                if dialog.result_action == CompensateDialog.ACTION_CLEAN_ALL:
                    for d in due:
                        run_preview_confirm(window, engine, d.entry, trigger="compensate")
                elif dialog.result_action == CompensateDialog.ACTION_VIEW_SELECT:
                    for d in due:
                        run_preview_confirm(window, engine, d.entry, trigger="compensate")

    window.show()
    if pyi_splash is not None:
        try:
            pyi_splash.close()
        except Exception:
            pass
    window.refresh_all()

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
