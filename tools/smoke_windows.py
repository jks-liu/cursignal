"""Windows desktop integration test.

Usage: uv run python tools/smoke_windows.py
Temporarily enlarges system cursors and moves the pointer by a few pixels.
Restores the pointer position and stops the test daemon in finally.
Refuses to run if an existing cursignal daemon is active.
"""

import ctypes as C
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes as W
from pathlib import Path

from cursignal.backends.win_worker import CURSOR_IDS, NativeCursors
from cursignal.ipc import request, runtime_dir


def cli(*args):
    result = subprocess.run(
        [sys.executable, "-m", "cursignal", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=35,
        env=os.environ | {"PYTHONIOENCODING": "utf-8"},
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def main():
    if sys.platform != "win32":
        raise SystemExit("This smoke test requires a Windows desktop.")
    if json.loads(cli("--status"))["running"]:
        raise SystemExit("Existing cursignal daemon detected; stop it before running this test.")
    directory = runtime_dir()
    native = NativeCursors()
    native.user.GetCursorPos.argtypes = [C.POINTER(W.POINT)]
    native.user.SetCursorPos.argtypes = [C.c_int, C.c_int]
    point = W.POINT()
    assert native.user.GetCursorPos(C.byref(point))

    def sizes():
        return {i: native.dimensions(native.user.LoadCursorW(None, i)) for i in CURSOR_IDS}

    original = sizes()
    report = {"original_sizes": original}
    try:
        # Concurrent cold starts must converge on the same daemon without lost messages.
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda m: cli(m), ["构建完成", "测试通过", "部署完成"]))
        status = request(directory, "status")
        assert status["messages"] == 3, status
        assert status["phase"] == "waiting", status
        enlarged = sizes()
        assert enlarged == {i: (w * 5, h * 5) for i, (w, h) in original.items()}, enlarged
        report["enlarged_sizes"] = enlarged
        assert native.user.SetCursorPos(point.x + 4, point.y + 4)
        time.sleep(1.4)
        status = request(directory, "status")
        assert status["phase"] == "fading", status
        intermediate = sizes()[32512]
        assert original[32512][0] < intermediate[0] < enlarged[32512][0], intermediate
        report["intermediate_size"] = intermediate
        # A new message during animation restores 5x and starts waiting again.
        cli("动画期间追加")
        assert request(directory, "status")["messages"] == 4
        assert sizes() == enlarged
        assert native.user.SetCursorPos(point.x + 8, point.y + 8)
        time.sleep(3.4)
        assert request(directory, "status")["phase"] == "idle"
        assert sizes() == original, sizes()
        report["animation_restore"] = True
        cli("强制退出恢复验证")
        status = request(directory, "status")
        subprocess.run(
            ["taskkill", "/PID", str(status["pid"]), "/F"], check=True, capture_output=True
        )
        deadline = time.monotonic() + 8
        while sizes() != original and time.monotonic() < deadline:
            time.sleep(0.05)
        assert sizes() == original, sizes()
        report["crash_restore"] = True
        cli("崩溃后重新启动")
        assert request(directory, "status")["pid"] != status["pid"]
        cli("--stop")
        assert sizes() == original
        report["restart_and_stop_restore"] = True
        path = Path("artifacts/windows-smoke.json")
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"PASS: {path}")
    finally:
        cli("--stop")
        native.user.SetCursorPos(point.x, point.y)


if __name__ == "__main__":
    main()
