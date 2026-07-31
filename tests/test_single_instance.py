"""
单实例锁测试 — QSharedMemory 唯一性（第二个实例能检测到已运行实例）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from PySide6.QtCore import QSharedMemory
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def test_second_instance_detected(qapp):
    """第一个实例持有锁成功；第二个实例 acquire 返回 False。"""
    from src.main import _acquire_single_instance

    key = "TestFolderCleanerSingle_{}".format(id(qapp))
    first = QSharedMemory(key)
    second = QSharedMemory(key)
    try:
        assert _acquire_single_instance(first) is True   # 第一个实例成功
        assert _acquire_single_instance(second) is False  # 第二个实例被拒
    finally:
        second.detach()
        first.detach()
