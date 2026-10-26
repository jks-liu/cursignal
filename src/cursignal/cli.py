"""Fast CLI: Qt is imported only in the detached desktop process."""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import __version__
from .ipc import MAX_MESSAGE, request, runtime_dir, startup_lock

# A timeout or permission failure is not evidence that the daemon is absent.
CONNECTION_ERRORS = (FileNotFoundError, ConnectionError, ValueError, KeyError)


def launch(directory: Path) -> subprocess.Popen:
    executable = Path(sys.executable)
    if sys.platform == "win32" and executable.with_name("pythonw.exe").exists():
        executable = executable.with_name("pythonw.exe")
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    with open(directory / "server.log", "w", encoding="utf-8") as log:
        return subprocess.Popen(
            [str(executable), "-m", "cursignal.server"],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            close_fds=True,
            **kwargs,
        )


def send(directory: Path, command: str, message: str) -> dict:
    # All clients share this lock, including stop/status: startup cannot race a stop.
    with startup_lock(directory):
        try:
            reply = request(directory, command, message)
            if command == "stop":
                deadline = time.monotonic() + 8
                while (directory / "server.json").exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                if (directory / "server.json").exists():
                    raise RuntimeError("后台进程尚未完成退出，请检查 server.log")
            return reply
        except CONNECTION_ERRORS:
            if command != "notify":
                return {"ok": True, "running": False}
        process = launch(directory)
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if process.poll() is not None:
                detail = (directory / "server.log").read_text(encoding="utf-8", errors="replace")
                raise RuntimeError(f"桌面进程启动失败：\n{detail[-4000:]}")
            try:
                return request(directory, command, message)
            except CONNECTION_ERRORS:
                time.sleep(0.1)
        process.terminate()
        process.wait(timeout=5)
        raise TimeoutError(f"桌面进程启动超时，请查看 {directory / 'server.log'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="放大光标并显示消息；移动鼠标后在 3 秒内淡出。")
    parser.add_argument("message", nargs="?", help="要显示的消息（用引号包含空格）")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true", help="显示后台状态")
    group.add_argument("--stop", action="store_true", help="停止后台进程并恢复光标")
    parser.add_argument("--version", action="version", version=f"cursignal {__version__}")
    args = parser.parse_args(argv)
    if args.message is not None and (args.status or args.stop):
        parser.error("消息不能与 --status/--stop 同时使用")
    if not (args.status or args.stop):
        if args.message is None or not args.message.strip():
            parser.error("请提供非空消息")
        if len(args.message) > MAX_MESSAGE:
            parser.error(f"消息不能超过 {MAX_MESSAGE} 个字符")
    command = "status" if args.status else "stop" if args.stop else "notify"
    try:
        if command == "notify" and sys.platform.startswith("linux"):
            if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
                raise RuntimeError("当前 Wayland 会话不支持全局光标操作，请在 X11 桌面会话运行。")
            if not os.environ.get("DISPLAY"):
                raise RuntimeError("未找到图形桌面 DISPLAY；请在本地 X11 桌面会话运行。")
        result = send(runtime_dir(), command, args.message or "")
        if not result.get("ok"):
            raise RuntimeError(result.get("error", "请求失败"))
        if args.status:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"cursignal: {exc}", file=sys.stderr)
        return 1
