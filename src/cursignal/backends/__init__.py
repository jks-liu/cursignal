"""Platform adapters: begin/scale/end/close and optional software cursor image."""

import sys


def create_backend():
    if sys.platform == "win32":
        from .windows import WindowsBackend

        return WindowsBackend()
    if sys.platform == "darwin":
        from .macos import MacBackend

        return MacBackend()
    if sys.platform.startswith("linux"):
        from .x11 import X11Backend

        return X11Backend()
    raise RuntimeError(f"不支持的平台：{sys.platform}")
