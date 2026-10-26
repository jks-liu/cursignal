import pytest


def test_notifications_share_state_and_cleanup(server):
    assert server.handle({"command": "notify", "message": "第一条"})["messages"] == 1
    assert server.handle({"command": "notify", "message": "第二条"})["messages"] == 2
    assert len(server.text.layouts) == 2
    assert server.backend.factor == 5
    server.clear()
    assert server.backend.ends == 1
    assert server.handle({"command": "status"})["phase"] == "idle"


@pytest.mark.parametrize("message", [None, [], {}, "", " " * 3, "x" * 4097])
def test_rejects_bad_messages_without_cursor_changes(server, message):
    with pytest.raises(ValueError):
        server.handle({"command": "notify", "message": message})
    assert server.backend.begins == 0


def test_failed_begin_clears_active_messages(server):
    server.handle({"command": "notify", "message": "已有消息"})

    def fail():
        raise RuntimeError("模拟故障")

    server.backend.begin = fail
    with pytest.raises(RuntimeError):
        server.handle({"command": "notify", "message": "新消息"})
    assert not server.active
    assert not server.model.messages
    assert server.backend.ends == 1


def test_render_failure_restores_cursor(server):
    def fail(*args):
        raise RuntimeError("模拟绘制失败")

    server.render = fail
    with pytest.raises(RuntimeError):
        server.handle({"command": "notify", "message": "新消息"})
    assert not server.active
    assert not server.model.messages
    assert server.backend.ends == 1
