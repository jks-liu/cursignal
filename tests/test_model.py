import pytest

from cursignal.model import Notification


def test_waits_without_expiring_until_pointer_moves():
    state = Notification()
    state.append("完成", (100, 200))
    assert state.frame((100, 200), 0) == (5, 1)
    assert state.frame((100, 200), 1_000_000) == (5, 1)


def test_three_second_transition_and_cleanup():
    state = Notification()
    state.append("完成", (0, 0))
    assert state.frame((1, 0), 10) == (5, 1)
    assert state.frame((100, 0), 11.5) == pytest.approx((3, 0.5))
    assert state.frame((100, 0), 13) == (1, 0)
    assert not state.messages


def test_new_message_appends_color_and_restarts_wait_during_fade():
    state = Notification()
    state.append("第一条", (0, 0))
    state.frame((1, 0), 0)
    state.frame((2, 0), 1.5)
    state.append("第二条", (2, 0))
    assert [text for text, _ in state.messages] == ["第一条", "第二条"]
    assert state.messages[0][1] != state.messages[1][1]
    assert state.frame((2, 0), 100) == (5, 1)
    state.frame((3, 0), 101)
    assert state.frame((3, 0), 104) == (1, 0)


def test_adjacent_colors_never_repeat():
    state = Notification()
    for i in range(128):
        state.append(str(i), (0, 0))
    colors = [color for _, color in state.messages]
    assert all(a != b for a, b in zip(colors, colors[1:]))
