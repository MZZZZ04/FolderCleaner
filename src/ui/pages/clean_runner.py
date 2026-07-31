"""
清理执行流程（复用）：预览 → 确认 → 移入回收站。

被条目页的手动清理 / 启动补偿 / 托盘"立即清理"共用。
"""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

from ...cleaner.engine import CleanEngine
from ...models import VirtualEntry
from ...utils.paths import format_size
from ..dialogs import CleanConfirmDialog


def run_preview_confirm(parent: QWidget, engine: CleanEngine, entry: VirtualEntry,
                        trigger: str = "manual") -> bool:
    """预览并确认后执行清理，返回是否执行了。"""
    try:
        files = engine.preview(entry)
    except ValueError as e:
        QMessageBox.warning(parent, "无法清理", str(e))
        return False

    if not files:
        QMessageBox.information(parent, "无需清理", f"『{entry.name}』没有匹配到待清理文件")
        return False

    result = CleanConfirmDialog({entry.name: files}, parent)
    if result.exec_() != CleanConfirmDialog.Accepted:
        return False

    selected = result.get_selected_files()
    if not selected:
        return False

    clean_result = engine.clean(entry, selected, trigger=trigger)
    QMessageBox.information(
        parent, "清理完成",
        f"『{entry.name}』\n"
        f"移入回收站: {clean_result.moved} 个文件\n"
        f"释放空间: {format_size(clean_result.total_bytes)}",
    )
    return True
