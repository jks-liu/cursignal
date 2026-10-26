import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication

from cursignal.server import Server


class Backend:
    size = (32, 32)
    image = None
    hotspot = (0, 0)

    def __init__(self):
        self.begins = 0
        self.ends = 0
        self.closed = False

    def begin(self):
        self.begins += 1

    def scale(self, factor):
        self.factor = factor

    def end(self):
        self.ends += 1

    def close(self):
        self.closed = True


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def server(app, tmp_path, monkeypatch):
    monkeypatch.setattr("cursignal.server.runtime_dir", lambda: tmp_path)
    backend = Backend()
    instance = Server(app, backend)
    yield instance
    instance.close()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert backend.closed
    assert not (tmp_path / "server.json").exists()
