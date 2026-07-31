"""PyInstaller 打包入口 — 以包方式导入 src.main（相对导入需要包上下文）。

打包命令示例（Windows）：
    py -3.9 -m PyInstaller --noconfirm --clean --onefile --windowed \
        --name "FolderCleaner" \
        --icon "resources/icons/app.ico" \
        --add-data "resources/icons/app.png;resources/icons" \
        --splash "resources/splash.png" \
        --paths "." launcher.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.main import main

if __name__ == "__main__":
    sys.exit(main())
