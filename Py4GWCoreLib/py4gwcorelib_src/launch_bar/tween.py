"""Minimal frame-time tween for the Launch Bar host.

Kept tiny and self-contained (no ImGui import) so the host can animate the collapse fold and
the idle-fade alpha smoothly. Values ease-out toward a target over a duration in milliseconds.
Time is supplied by the caller (host reads ``PySystem.get_tick_count64()`` once per frame), so
this stays testable and does not depend on any binding.

If ``now`` is not advancing (or 0), values snap to target — animations are strictly optional;
the UI is correct without them.
"""


def ease_out_cubic(p: float) -> float:
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    inv = 1.0 - p
    return 1.0 - inv * inv * inv


class AnimFloat:
    """A float that eases toward a target. Call :meth:`update` once per frame with ``now`` (ms)."""

    def __init__(self, value: float = 0.0, duration_ms: float = 150.0) -> None:
        self.current = float(value)
        self.target = float(value)
        self.duration_ms = float(duration_ms)
        self._from = float(value)
        self._start_ms = 0.0
        self._active = False

    def set_target(self, target: float, now_ms: float) -> None:
        target = float(target)
        if target == self.target:
            return
        self._from = self.current
        self.target = target
        self._start_ms = now_ms
        self._active = True

    def jump_to(self, value: float) -> None:
        self.current = self.target = self._from = float(value)
        self._active = False

    def update(self, now_ms: float) -> float:
        if not self._active:
            return self.current
        if self.duration_ms <= 0.0 or now_ms <= self._start_ms:
            self.current = self.target
            self._active = False
            return self.current
        p = (now_ms - self._start_ms) / self.duration_ms
        if p >= 1.0:
            self.current = self.target
            self._active = False
            return self.current
        self.current = self._from + (self.target - self._from) * ease_out_cubic(p)
        return self.current

    @property
    def animating(self) -> bool:
        return self._active
