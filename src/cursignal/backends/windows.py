"""A pipe-owned helper restores native cursors even when the GUI is killed."""

import json
import queue
import subprocess
import sys
import threading
from pathlib import Path


class WindowsBackend:
    image = None
    hotspot = (0, 0)
    size = (32, 32)

    def __init__(self):
        executable = Path(sys.executable).with_name("python.exe")
        self.process = subprocess.Popen(
            [str(executable), "-m", "cursignal.backends.win_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            encoding="utf-8",
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.replies = queue.Queue()
        self.last_scale = None
        self.closed = False

        def reader():
            try:
                for line in self.process.stdout:
                    self.replies.put(json.loads(line))
            finally:
                self.replies.put({"ok": False, "error": "光标恢复进程已退出"})

        threading.Thread(target=reader, daemon=True).start()
        try:
            self._request("ping")
        except Exception:
            self.close()
            raise

    def _request(self, command, factor=1.0):
        try:
            self.process.stdin.write(json.dumps({"command": command, "factor": factor}) + "\n")
            self.process.stdin.flush()
            result = self.replies.get(timeout=5)
        except (OSError, queue.Empty) as exc:
            raise RuntimeError("光标恢复进程通信失败") from exc
        if not result["ok"]:
            raise RuntimeError(result["error"])
        return result

    def begin(self):
        result = self._request("begin")
        self.size = tuple(result["size"])
        self.last_scale = 5.0

    def scale(self, factor):
        factor = round(factor, 2)
        if factor != self.last_scale:
            self._request("scale", factor)
            self.last_scale = factor

    def end(self):
        self._request("end")
        self.last_scale = None

    def close(self):
        if self.closed:
            return
        self.closed = True
        # EOF is the cleanup protocol. Never terminate the restoring process.
        try:
            self.process.stdin.close()
        except OSError:
            pass
        try:
            self.process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            print("光标恢复进程仍在清理，请检查桌面光标状态。", file=sys.stderr)
        if self.process.poll() is not None:
            self.process.stdout.close()
