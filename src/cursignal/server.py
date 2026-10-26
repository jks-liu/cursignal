"""Single desktop process. Only its Qt thread touches widgets and cursor APIs."""

import hmac
import json
import os
import secrets
import signal
import sys
import time
import traceback

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCursor
from PySide6.QtNetwork import QHostAddress, QTcpServer
from PySide6.QtWidgets import QApplication

from .backends import create_backend
from .ipc import MAX_MESSAGE, MAX_PACKET, publish_state, read_state, runtime_dir, startup_lock
from .model import Notification
from .overlay import CursorOverlay, MessageOverlay


class Server:
    def __init__(self, app, backend):
        self.app, self.backend = app, backend
        self.directory = runtime_dir()
        self.token = secrets.token_hex(32)
        self.model = Notification()
        self.text, self.cursor = MessageOverlay(), CursorOverlay()
        self.connections = {}
        self.closed = False
        self.active = False
        self.screen_key = None
        self.last_activity = time.monotonic()
        self.server = QTcpServer()
        self.server.newConnection.connect(self.accept)
        if not self.server.listen(QHostAddress.SpecialAddress.LocalHost, 0):
            raise RuntimeError(self.server.errorString())
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)
        publish_state(
            self.directory,
            {
                "port": self.server.serverPort(),
                "token": self.token,
                "pid": os.getpid(),
                "protocol": 1,
            },
        )

    def accept(self):
        while self.server.hasPendingConnections():
            conn = self.server.nextPendingConnection()
            if len(self.connections) >= 32:
                conn.abort()
                conn.deleteLater()
                continue
            self.connections[conn] = bytearray()
            conn.readyRead.connect(lambda conn=conn: self.receive(conn))
            conn.disconnected.connect(lambda conn=conn: self.discard(conn))
            # Incomplete requests must not retain sockets indefinitely.
            timer = QTimer(conn)
            timer.setSingleShot(True)
            timer.timeout.connect(conn.abort)
            timer.start(5000)
            self.receive(conn)

    def discard(self, conn):
        self.connections.pop(conn, None)
        conn.deleteLater()

    def receive(self, conn):
        data = self.connections.get(conn)
        if data is None:
            return
        data.extend(bytes(conn.readAll()))
        if len(data) > MAX_PACKET:
            conn.abort()
            return
        if b"\n" not in data:
            return
        try:
            packet = json.loads(data.split(b"\n", 1)[0])
            if not isinstance(packet, dict) or not isinstance(packet.get("token"), str):
                raise ValueError("无效请求")
            if not hmac.compare_digest(packet["token"], self.token):
                raise ValueError("认证失败")
            reply = self.handle(packet)
        except (ValueError, TypeError, RuntimeError, OSError) as exc:
            reply = {"ok": False, "error": str(exc)}
        conn.write(json.dumps(reply, ensure_ascii=False).encode("utf-8") + b"\n")
        conn.flush()
        conn.disconnectFromHost()

    def handle(self, packet):
        command = packet.get("command")
        if command == "notify":
            message = packet.get("message")
            if not isinstance(message, str) or not message.strip() or len(message) > MAX_MESSAGE:
                raise ValueError(f"消息必须为 1 至 {MAX_MESSAGE} 个字符的非空文本")
            if len(self.model.messages) >= 128:
                raise ValueError("已有 128 条消息等待查看，请先移动鼠标清除提示")
            position = QCursor.pos()
            try:
                self.backend.begin()
                self.active = True
                self.model.append(message, (position.x(), position.y()))
                self.screen_key = None
                self.last_activity = time.monotonic()
                self.render(position, 5.0, 1.0)
            except Exception:
                self.clear()
                raise
        elif command == "stop":
            QTimer.singleShot(50, self.app.quit)
        elif command != "status":
            raise ValueError("未知命令")
        return {
            "ok": True,
            "running": True,
            "pid": os.getpid(),
            "messages": len(self.model.messages),
            "phase": "fading"
            if self.model.fade_started is not None
            else "waiting"
            if self.model.messages
            else "idle",
        }

    def render(self, position, factor, opacity):
        screen = self.app.screenAt(position) or self.app.primaryScreen()
        geometry = screen.availableGeometry()
        key = (screen.name(), geometry.getRect())
        if key != self.screen_key:
            self.text.prepare(self.model.messages, geometry)
            self.screen_key = key
        dpr = screen.devicePixelRatio()
        divisor = dpr if sys.platform != "darwin" else 1
        self.backend.scale(factor)
        self.cursor.display(self.backend, position, factor, dpr)
        self.text.display(position, self.backend.size[1] * factor / divisor, opacity, geometry)

    def clear(self):
        self.text.hide()
        self.cursor.hide()
        self.model.clear()
        if self.active:
            self.backend.end()
        self.active = False
        self.last_activity = time.monotonic()

    def tick(self):
        try:
            if self.active:
                position = QCursor.pos()
                factor, opacity = self.model.frame((position.x(), position.y()), time.monotonic())
                if self.model.messages:
                    self.render(position, factor, opacity)
                else:
                    self.clear()
            elif time.monotonic() - self.last_activity > 60:
                # Avoid exiting while a CLI client is starting or delivering a request.
                try:
                    with startup_lock(self.directory, timeout=0):
                        self.close()
                        self.app.quit()
                except TimeoutError:
                    pass
        except Exception:
            traceback.print_exc()
            self.app.exit(1)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.timer.stop()
        self.server.close()
        for conn in list(self.connections):
            conn.abort()
        self.text.hide()
        self.cursor.hide()
        # Explicit Qt-thread destruction prevents cyclic wrappers from being
        # collected later on a Python network/helper thread.
        self.text.deleteLater()
        self.cursor.deleteLater()
        self.timer.deleteLater()
        self.server.deleteLater()
        try:
            self.backend.close()
        finally:
            try:
                if read_state(self.directory).get("token") == self.token:
                    (self.directory / "server.json").unlink(missing_ok=True)
            except (OSError, ValueError):
                pass


def main():
    app = QApplication(["cursignal"])
    app.setQuitOnLastWindowClosed(False)
    backend = create_backend()
    server = None
    try:
        server = Server(app, backend)
        signal.signal(signal.SIGINT, lambda *_: app.quit())
        signal.signal(signal.SIGTERM, lambda *_: app.quit())
        return app.exec()
    finally:
        if server is not None:
            server.close()
        else:
            backend.close()


if __name__ == "__main__":
    try:
        with startup_lock(runtime_dir(), timeout=0, name="server.lock"):
            raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
