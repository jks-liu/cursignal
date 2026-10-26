import json
import socket
import threading
import time

from cursignal.ipc import MAX_PACKET, publish_state, read_state, startup_lock


def test_state_round_trip_and_atomic_replacement(tmp_path):
    publish_state(tmp_path, {"port": 1234, "token": "first"})
    publish_state(tmp_path, {"port": 5678, "token": "second"})
    assert read_state(tmp_path) == {"port": 5678, "token": "second"}
    assert not (tmp_path / "server.tmp").exists()


def test_lock_releases_after_exception(tmp_path):
    try:
        with startup_lock(tmp_path):
            raise RuntimeError("test")
    except RuntimeError:
        pass
    with startup_lock(tmp_path, timeout=0):
        pass


def exchange(server, app, packet):
    results = []

    def client():
        try:
            with socket.create_connection(
                ("127.0.0.1", server.server.serverPort()), timeout=2
            ) as sock:
                sock.sendall(packet)
                data = bytearray()
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    data.extend(chunk)
                results.append(bytes(data))
        except OSError:
            results.append(b"")

    thread = threading.Thread(target=client)
    thread.start()
    deadline = time.monotonic() + 3
    while thread.is_alive() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.001)
    thread.join(timeout=0.1)
    assert not thread.is_alive()
    assert results
    return results[0]


def test_unauthorized_notify_cannot_change_cursor(server, app):
    result = exchange(server, app, b'{"token":"wrong","command":"notify","message":"x"}\n')
    assert json.loads(result)["ok"] is False
    assert server.backend.begins == 0


def test_malformed_packets_do_not_break_server(server, app):
    for packet in (b"[]\n", b"not json\n", b"\xff\n"):
        assert json.loads(exchange(server, app, packet))["ok"] is False
    packet = json.dumps({"token": server.token, "command": "status"}).encode() + b"\n"
    assert json.loads(exchange(server, app, packet))["phase"] == "idle"


def test_oversized_packet_is_disconnected(server, app):
    assert exchange(server, app, b"a" * (MAX_PACKET + 1)) == b""
    assert server.backend.begins == 0


def test_unicode_notify_is_acknowledged_after_render(server, app):
    packet = json.dumps({"token": server.token, "command": "notify", "message": "完成🎉"}).encode()
    result = json.loads(exchange(server, app, packet + b"\n"))
    assert result["messages"] == 1
    assert server.model.messages[0][0] == "完成🎉"
    assert server.backend.factor == 5
