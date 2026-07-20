"""Sliding-window rate limiter."""
import time
import threading
from collections import deque
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    max_actions_per_minute: int
    _window_seconds: float = 60.0
    _clock: callable = time.time
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    _actions: deque = field(default_factory=deque, repr=False)

    def allow_action(self, timestamp: float | None = None) -> bool:
        """Return True if action is allowed under the sliding window."""
        if timestamp is None:
            timestamp = self._clock()

        with self._lock:
            # Remove actions older than the window
            cutoff = timestamp - self._window_seconds
            while self._actions and self._actions[0] < cutoff:
                self._actions.popleft()

            if len(self._actions) < self.max_actions_per_minute:
                self._actions.append(timestamp)
                return True
            return False

    def reset(self) -> None:
        """Clear all recorded actions (for testing)."""
        with self._lock:
            self._actions.clear()