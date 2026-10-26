import pytest

from cursignal.cli import main


@pytest.fixture(autouse=True)
def graphical_environment(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":test")
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)


@pytest.mark.parametrize(
    "args", [[], [""], ["   "], ["a" * 4097], ["message", "--stop"], ["--status", "--stop"]]
)
def test_invalid_input_does_not_start_server(args):
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2


def test_literal_unicode_message(monkeypatch):
    received = []
    monkeypatch.setattr(
        "cursignal.cli.send", lambda d, c, m: received.append((c, m)) or {"ok": True}
    )
    monkeypatch.setattr("cursignal.cli.runtime_dir", lambda: None)
    assert main(["完成 <b>不是HTML</b>\n第二行"]) == 0
    assert received == [("notify", "完成 <b>不是HTML</b>\n第二行")]


def test_backend_error_is_nonzero(monkeypatch, capsys):
    monkeypatch.setattr("cursignal.cli.send", lambda *_: {"ok": False, "error": "不可用"})
    monkeypatch.setattr("cursignal.cli.runtime_dir", lambda: None)
    assert main(["完成"]) == 1
    assert "不可用" in capsys.readouterr().err


def test_wayland_is_rejected_before_launch(monkeypatch, capsys):
    monkeypatch.setattr("cursignal.cli.sys.platform", "linux")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    assert main(["完成"]) == 1
    assert "Wayland" in capsys.readouterr().err
