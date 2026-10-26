"""Capture the actual X11 cursor using XFixes; disconnect releases its hide request."""

import ctypes as C
import ctypes.util
import os

from PySide6.QtGui import QImage


class CursorImage(C.Structure):
    _fields_ = [
        ("x", C.c_short),
        ("y", C.c_short),
        ("width", C.c_ushort),
        ("height", C.c_ushort),
        ("xhot", C.c_ushort),
        ("yhot", C.c_ushort),
        ("cursor_serial", C.c_ulong),
        ("pixels", C.POINTER(C.c_ulong)),
        ("atom", C.c_ulong),
        ("name", C.c_char_p),
    ]


class X11Backend:
    image = None
    hotspot = (0, 0)
    size = (32, 32)

    def __init__(self):
        if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
            raise RuntimeError("Wayland 不支持此全局光标实现，请使用 X11 桌面会话。")
        x11, fixes = ctypes.util.find_library("X11"), ctypes.util.find_library("Xfixes")
        if not x11 or not fixes:
            raise RuntimeError("需要系统库 libX11 和 libXfixes（含 XFixes 4+ 扩展）。")
        self.x = C.CDLL(x11)
        self.f = C.CDLL(fixes)
        self.x.XOpenDisplay.argtypes = [C.c_char_p]
        self.x.XOpenDisplay.restype = C.c_void_p
        self.x.XDefaultRootWindow.argtypes = [C.c_void_p]
        self.x.XDefaultRootWindow.restype = C.c_ulong
        self.x.XCloseDisplay.argtypes = [C.c_void_p]
        self.x.XFlush.argtypes = [C.c_void_p]
        self.x.XFree.argtypes = [C.c_void_p]
        self.f.XFixesQueryVersion.argtypes = [C.c_void_p, C.POINTER(C.c_int), C.POINTER(C.c_int)]
        self.f.XFixesGetCursorImage.argtypes = [C.c_void_p]
        self.f.XFixesGetCursorImage.restype = C.POINTER(CursorImage)
        for name in ("XFixesHideCursor", "XFixesShowCursor"):
            getattr(self.f, name).argtypes = [C.c_void_p, C.c_ulong]
        self.display = self.x.XOpenDisplay(None)
        self.hidden = False
        if not self.display:
            raise RuntimeError("无法连接 X11 图形桌面。")
        major, minor = C.c_int(4), C.c_int(0)
        if (
            not self.f.XFixesQueryVersion(self.display, C.byref(major), C.byref(minor))
            or major.value < 4
        ):
            self.close()
            raise RuntimeError("需要 XFixes 4 或更新版本。")
        self.root = self.x.XDefaultRootWindow(self.display)

    def begin(self):
        if self.hidden:
            return
        pointer = self.f.XFixesGetCursorImage(self.display)
        if not pointer:
            raise RuntimeError("无法读取 X11 当前光标。")
        try:
            cursor = pointer.contents
            self.size = cursor.width, cursor.height
            self.hotspot = cursor.xhot, cursor.yhot
            # Xlib represents each 32-bit ARGB pixel as an unsigned long, even on LP64.
            data = b"".join(
                (cursor.pixels[i] & 0xFFFFFFFF).to_bytes(4, "little")
                for i in range(cursor.width * cursor.height)
            )
            self.image = QImage(
                data, cursor.width, cursor.height, QImage.Format.Format_ARGB32_Premultiplied
            ).copy()
        finally:
            self.x.XFree(pointer)
        self.f.XFixesHideCursor(self.display, self.root)
        self.x.XFlush(self.display)
        self.hidden = True

    def scale(self, factor):
        pass  # Qt draws the captured image at the requested size.

    def end(self):
        if self.hidden:
            self.f.XFixesShowCursor(self.display, self.root)
            self.x.XFlush(self.display)
            self.hidden = False
        self.image = None

    def close(self):
        if self.display:
            self.end()
            self.x.XCloseDisplay(self.display)
            self.display = None
