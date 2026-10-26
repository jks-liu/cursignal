"""UI independent notification timing; all times are monotonic seconds."""

from dataclasses import dataclass, field

COLORS = ("#68d5ff", "#ffd166", "#95ed9a", "#f6a6ff", "#ff9d85", "#b9b2ff")
DURATION = 3.0


@dataclass
class Notification:
    messages: list[tuple[str, str]] = field(default_factory=list)
    anchor: tuple[int, int] | None = None
    fade_started: float | None = None
    color_index: int = 0

    def append(self, message: str, position: tuple[int, int]) -> None:
        self.messages.append((message, COLORS[self.color_index % len(COLORS)]))
        self.color_index += 1
        self.anchor = position
        self.fade_started = None

    def frame(self, position: tuple[int, int], now: float) -> tuple[float, float]:
        if not self.messages:
            return 1.0, 0.0
        if self.fade_started is None and position != self.anchor:
            self.fade_started = now
        progress = (
            0.0
            if self.fade_started is None
            else min(1.0, max(0.0, (now - self.fade_started) / DURATION))
        )
        # Smoothstep has zero velocity at both ends.
        eased = progress * progress * (3.0 - 2.0 * progress)
        if progress >= 1.0:
            self.clear()
        return 5.0 - 4.0 * eased, 1.0 - eased

    def clear(self) -> None:
        self.messages.clear()
        self.anchor = None
        self.fade_started = None
        self.color_index = 0
