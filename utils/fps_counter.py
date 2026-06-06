"""Simple rolling FPS counter."""

import time


class FPSCounter:
    def __init__(self, avg_over: int = 30):
        # Sliding window of timestamps (one per tick call)
        self._times: list[float] = []
        # Maximum window size — larger = smoother FPS, slower to react to changes
        self._avg_over = avg_over

    def tick(self):
        """Record the current timestamp.
        Call once per processed frame to keep the window up to date."""
        self._times.append(time.time())
        # Drop the oldest entry when the window is full
        if len(self._times) > self._avg_over:
            self._times.pop(0)

    @property
    def fps(self) -> float:
        """Return the average FPS over the rolling window.
        Returns 0.0 if fewer than 2 ticks have been recorded."""
        if len(self._times) < 2:
            return 0.0
        # Total time spanned by the window
        elapsed = self._times[-1] - self._times[0]
        # (n-1) intervals between n timestamps
        return (len(self._times) - 1) / elapsed if elapsed > 0 else 0.0