"""Hardware-independent core for the LumaBot daemon."""

import threading
import time

from daemon_state import RobotStatus


class LumaBotDaemon:
    def __init__(self):
        self._started_at = time.monotonic()
        self._lock = threading.Lock()
        self.status = RobotStatus()

    def get_status(self) -> dict:
        with self._lock:
            snapshot = self.status.snapshot()
        snapshot["uptime_s"] = round(time.monotonic() - self._started_at, 1)
        return snapshot
