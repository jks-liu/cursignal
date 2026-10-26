"""Authenticated loopback IPC and a per-user startup lock (stdlib only)."""

import json
import os
import socket
import sys
import time
from contextlib import contextmanager
from pathlib import Path

MAX_PACKET = 65536
MAX_MESSAGE = 4096


def runtime_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Caches"
    else:
        base = Path(os.environ.get("XDG_RUNTIME_DIR", Path.home() / ".cache"))
    directory = base / "cursignal"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if sys.platform != "win32":
        directory.chmod(0o700)
    return directory


def read_state(directory: Path) -> dict:
    return json.loads((directory / "server.json").read_text(encoding="utf-8"))


def publish_state(directory: Path, state: dict) -> None:
    path = directory / "server.tmp"
    with open(path, "w", encoding="utf-8") as stream:
        if sys.platform != "win32":
            os.chmod(path, 0o600)
        json.dump(state, stream)
    path.replace(directory / "server.json")


def request(directory: Path, command: str, message: str = "", timeout: float = 2.0) -> dict:
    state = read_state(directory)
    packet = (
        json.dumps(
            {"token": state["token"], "command": command, "message": message},
            ensure_ascii=False,
        ).encode("utf-8")
        + b"\n"
    )
    with socket.create_connection(("127.0.0.1", state["port"]), timeout=timeout) as conn:
        conn.settimeout(timeout)
        conn.sendall(packet)
        data = bytearray()
        while b"\n" not in data:
            chunk = conn.recv(4096)
            if not chunk:
                raise ConnectionError("后台进程未确认请求")
            data.extend(chunk)
            if len(data) > MAX_PACKET:
                raise ConnectionError("后台进程返回了过大的数据")
    return json.loads(data.split(b"\n", 1)[0])


@contextmanager
def startup_lock(directory: Path, timeout: float = 30.0, name: str = "startup.lock"):
    with open(directory / name, "a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                stream.seek(0)
                if sys.platform == "win32":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("等待 cursignal 启动锁超时") from None
                time.sleep(0.05)
        try:
            yield
        finally:
            stream.seek(0)
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream, fcntl.LOCK_UN)
