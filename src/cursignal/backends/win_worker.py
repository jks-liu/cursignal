"""Own all cursor mutations; stdin EOF restores originals without Qt dependencies."""

import ctypes as C
import json
import sys
from ctypes import wintypes as W

from cursignal.ipc import runtime_dir, startup_lock

CURSOR_IDS = (
    32512,
    32513,
    32514,
    32515,
    32516,
    32642,
    32643,
    32644,
    32645,
    32646,
    32648,
    32649,
    32650,
)


class ICONINFO(C.Structure):
    _fields_ = [
        ("fIcon", W.BOOL),
        ("xHotspot", W.DWORD),
        ("yHotspot", W.DWORD),
        ("hbmMask", W.HBITMAP),
        ("hbmColor", W.HBITMAP),
    ]


class BITMAP(C.Structure):
    _fields_ = [
        ("bmType", W.LONG),
        ("bmWidth", W.LONG),
        ("bmHeight", W.LONG),
        ("bmWidthBytes", W.LONG),
        ("bmPlanes", W.WORD),
        ("bmBitsPixel", W.WORD),
        ("bmBits", C.c_void_p),
    ]


class NativeCursors:
    def __init__(self):
        self.user = C.WinDLL("user32", use_last_error=True)
        self.gdi = C.WinDLL("gdi32", use_last_error=True)
        self.user.LoadCursorW.argtypes = [W.HINSTANCE, C.c_void_p]
        self.user.LoadCursorW.restype = W.HANDLE
        self.user.CopyImage.argtypes = [W.HANDLE, W.UINT, C.c_int, C.c_int, W.UINT]
        self.user.CopyImage.restype = W.HANDLE
        self.user.GetIconInfo.argtypes = [W.HANDLE, C.POINTER(ICONINFO)]
        self.user.GetIconInfo.restype = W.BOOL
        self.user.SetSystemCursor.argtypes = [W.HANDLE, W.DWORD]
        self.user.SetSystemCursor.restype = W.BOOL
        self.user.DestroyCursor.argtypes = [W.HANDLE]
        self.user.DestroyCursor.restype = W.BOOL
        self.user.SystemParametersInfoW.argtypes = [W.UINT, W.UINT, C.c_void_p, W.UINT]
        self.user.SystemParametersInfoW.restype = W.BOOL
        self.gdi.GetObjectW.argtypes = [W.HANDLE, C.c_int, C.c_void_p]
        self.gdi.GetObjectW.restype = C.c_int
        self.gdi.DeleteObject.argtypes = [W.HANDLE]
        self.gdi.DeleteObject.restype = W.BOOL
        self.originals = {}

    def dimensions(self, handle):
        info, bitmap = ICONINFO(), BITMAP()
        if not self.user.GetIconInfo(handle, C.byref(info)):
            raise C.WinError(C.get_last_error())
        try:
            if not self.gdi.GetObjectW(
                info.hbmColor or info.hbmMask, C.sizeof(bitmap), C.byref(bitmap)
            ):
                raise C.WinError(C.get_last_error())
            return bitmap.bmWidth, bitmap.bmHeight // (1 if info.hbmColor else 2)
        finally:
            for value in (info.hbmMask, info.hbmColor):
                if value:
                    self.gdi.DeleteObject(value)

    def copy(self, handle, width=0, height=0):
        result = self.user.CopyImage(handle, 2, width, height, 0)
        if not result:
            raise C.WinError(C.get_last_error())
        return result

    def begin(self):
        if self.originals:
            self.scale(5.0)
            return self.originals[32512][1:]
        try:
            # Snapshot every shape before modifying any global state.
            for identifier in CURSOR_IDS:
                shared = self.user.LoadCursorW(None, identifier)
                if not shared:
                    raise C.WinError(C.get_last_error())
                width, height = self.dimensions(shared)
                self.originals[identifier] = (self.copy(shared), width, height)
            self.scale(5.0)
            return self.originals[32512][1:]
        except Exception:
            self.restore()
            raise

    def scale(self, factor):
        for identifier, (handle, width, height) in self.originals.items():
            resized = self.copy(
                handle, max(1, round(width * factor)), max(1, round(height * factor))
            )
            if not self.user.SetSystemCursor(resized, identifier):
                self.user.DestroyCursor(resized)
                raise C.WinError(C.get_last_error())

    def restore(self):
        failed = False
        for identifier, (handle, _, _) in self.originals.items():
            try:
                duplicate = self.copy(handle)
                if not self.user.SetSystemCursor(duplicate, identifier):
                    self.user.DestroyCursor(duplicate)
                    failed = True
            except OSError:
                failed = True
            finally:
                self.user.DestroyCursor(handle)
        self.originals.clear()
        if failed and not self.user.SystemParametersInfoW(0x0057, 0, None, 0):
            raise C.WinError(C.get_last_error())


def main():
    native = NativeCursors()
    try:
        for line in sys.stdin:
            try:
                packet = json.loads(line)
                command = packet["command"]
                result = {"ok": True}
                if command == "begin":
                    result["size"] = native.begin()
                elif command == "scale":
                    native.scale(max(1.0, min(5.0, float(packet["factor"]))))
                elif command == "end":
                    native.restore()
                elif command != "ping":
                    raise ValueError("未知光标命令")
            except Exception as exc:
                native.restore()
                result = {"ok": False, "error": str(exc)}
            print(json.dumps(result), flush=True)
    finally:
        native.restore()


if __name__ == "__main__":
    # After a GUI crash, a replacement helper waits for the old one to restore.
    with startup_lock(runtime_dir(), timeout=10, name="cursor.lock"):
        main()
