"""Render a text overlay preview without modifying the system cursor.

Usage: uv run python tools/preview.py [output.png]
Uses Qt's offscreen backend; default output is artifacts/overlay-preview.png.
"""

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QPoint, QRect  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from cursignal.model import COLORS  # noqa: E402
from cursignal.overlay import MessageOverlay  # noqa: E402


def main():
    app = QApplication([])
    # Qt's Windows offscreen plugin does not enumerate installed fonts.
    if sys.platform == "win32" and not QFontDatabase.families():
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc"
        if QFontDatabase.addApplicationFont(str(font)) < 0:
            raise RuntimeError(f"Could not load preview font: {font}")
        app.setFont(QFont("Microsoft YaHei"))
    overlay = MessageOverlay()
    overlay.prepare(
        [
            ("构建完成 · Build completed", COLORS[0]),
            ("测试通过：中文、English 和多行消息\n移动鼠标后，提示将在 3 秒内淡出。", COLORS[1]),
            ("另一个任务完成 · 新消息使用不同颜色", COLORS[2]),
        ],
        QRect(0, 0, 1920, 1080),
    )
    overlay.display(QPoint(100, 100), 32, 1, QRect(0, 0, 1920, 1080))
    app.processEvents()
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/overlay-preview.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    if not overlay.grab().save(str(output)):
        raise RuntimeError(f"Could not save {output}")
    print(output)


if __name__ == "__main__":
    main()
