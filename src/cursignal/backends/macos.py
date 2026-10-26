"""Public Cocoa/Quartz APIs: capture system cursor, hide it, draw its image in Qt."""

from PySide6.QtGui import QImage


class MacBackend:
    image = None
    hotspot = (0, 0)
    size = (32, 32)

    def __init__(self):
        import AppKit
        import Quartz

        self.appkit = AppKit
        self.quartz = Quartz
        self.hidden = False
        # Keep the background notifier out of the Dock and application switcher.
        AppKit.NSApplication.sharedApplication().setActivationPolicy_(
            AppKit.NSApplicationActivationPolicyAccessory
        )

    def begin(self):
        if self.hidden:
            return
        cursor = self.appkit.NSCursor.currentSystemCursor()
        if cursor is None:
            raise RuntimeError("macOS 无法读取当前系统光标。")
        native_image = cursor.image()
        representation = self.appkit.NSBitmapImageRep.imageRepWithData_(
            native_image.TIFFRepresentation()
        )
        data = representation.representationUsingType_properties_(
            self.appkit.NSBitmapImageFileTypePNG, {}
        )
        self.image = QImage.fromData(bytes(data), "PNG")
        if self.image.isNull():
            raise RuntimeError("macOS 当前光标图像为空。")
        logical_size = native_image.size()
        self.image.setDevicePixelRatio(self.image.width() / logical_size.width)
        self.size = logical_size.width, logical_size.height
        point = cursor.hotSpot()
        self.hotspot = point.x, point.y
        error = self.quartz.CGDisplayHideCursor(self.quartz.CGMainDisplayID())
        if error:
            self.image = None
            raise RuntimeError(f"macOS 隐藏光标失败（错误 {error}）。")
        self.hidden = True

    def scale(self, factor):
        pass

    def end(self):
        if self.hidden:
            error = self.quartz.CGDisplayShowCursor(self.quartz.CGMainDisplayID())
            if error:
                raise RuntimeError(f"macOS 恢复光标失败（错误 {error}）。")
            self.hidden = False
        self.image = None

    def close(self):
        self.end()
