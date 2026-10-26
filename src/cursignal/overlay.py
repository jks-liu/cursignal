"""Non-activating, click-through windows for text and software cursors."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QTextLayout, QTextOption
from PySide6.QtWidgets import QWidget


class TransparentWindow(QWidget):
    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)


class CursorOverlay(TransparentWindow):
    def __init__(self):
        super().__init__()
        self.image = None

    def display(self, backend, position, factor, dpr):
        self.image = backend.image
        if self.image is None:
            self.hide()
            return
        # macOS backend sizes are points; X11 reports native pixels.
        import sys

        divisor = dpr if sys.platform.startswith("linux") else 1.0
        width, height = (max(1, round(v * factor / divisor)) for v in backend.size)
        hot_x, hot_y = (round(v * factor / divisor) for v in backend.hotspot)
        self.setGeometry(position.x() - hot_x, position.y() - hot_y, width, height)
        self.show()
        self.update()

    def paintEvent(self, event):
        if self.image is not None:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(QRectF(self.rect()), self.image)


class MessageOverlay(TransparentWindow):
    def __init__(self):
        super().__init__()
        self.font = QFont()
        self.font.setPointSize(12)
        self.layouts = []
        self.opacity = 1.0

    def prepare(self, messages, screen):
        self.layouts = []
        width = max(40, min(460, screen.width() - 24))
        limit = max(30, screen.height() - 32)
        entries = []
        for message, color in messages:
            layout = QTextLayout(message.replace("\n", "\u2028"), self.font)
            option = QTextOption()
            option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
            layout.setTextOption(option)
            layout.beginLayout()
            height = 0
            while True:
                line = layout.createLine()
                if not line.isValid():
                    break
                line.setLineWidth(width - 28)
                from PySide6.QtCore import QPointF

                line.setPosition(QPointF(0, height))
                height += line.height()
            layout.endLayout()
            entries.append((layout, color, min(height + 20, limit)))
        # A finite screen cannot contain unbounded messages. Keep latest cards visible.
        height = 0
        for entry in reversed(entries):
            if height and height + entry[2] > limit:
                break
            self.layouts.insert(0, entry)
            height += entry[2]
        self.resize(width, max(1, round(height)))

    def display(self, position, cursor_height, opacity, screen):
        self.opacity = opacity
        x = max(screen.left(), min(position.x(), screen.right() - self.width() + 1))
        y = position.y() + round(cursor_height) + 10
        if y + self.height() > screen.bottom() + 1:
            y = max(screen.top(), position.y() - self.height() - 10)
        self.move(x, y)
        self.show()
        self.update()

    def paintEvent(self, event):
        from PySide6.QtCore import QPointF

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self.opacity)
        top = 0
        for layout, color, height in self.layouts:
            painter.save()
            rect = QRectF(0, top, self.width(), height - 3)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(25, 28, 35, 235))
            painter.drawRoundedRect(rect, 8, 8)
            painter.setClipRect(rect.adjusted(10, 5, -10, -5))
            painter.setPen(QColor(color))
            layout.draw(painter, QPointF(14, top + 8))
            painter.restore()
            top += height
