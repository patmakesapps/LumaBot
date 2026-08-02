"""Still-photo capture for VISITOR LX-1."""

from datetime import datetime
from pathlib import Path
import subprocess
import threading


PHOTO_DIR = Path.home() / ".visitor-lx1" / "photos"


def capture_photo() -> Path:
    """Capture one autofocus JPEG and return its private file path."""
    PHOTO_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
    target = PHOTO_DIR / f"visitor-lx1-{stamp}.jpg"
    subprocess.run(
        [
            "/usr/bin/rpicam-still", "--nopreview", "--timeout", "1500",
            "--autofocus-on-capture", "--width", "1280", "--height", "720",
            "--quality", "90", "--output", str(target),
        ],
        check=True, timeout=10,
    )
    target.chmod(0o600)
    return target


class CameraUnavailable(RuntimeError):
    """Raised when camera capture has not been enabled."""


class CameraBusy(RuntimeError):
    """Raised when another photo is already being captured."""


class CameraController:
    def __init__(self, enabled: bool = False, capture_fn=capture_photo):
        self._capture_fn = capture_fn
        self._lock = threading.Lock()
        self.ready = enabled and Path("/usr/bin/rpicam-still").is_file()

    def capture(self) -> Path:
        if not self.ready:
            raise CameraUnavailable("camera is disabled or unavailable")
        if not self._lock.acquire(blocking=False):
            raise CameraBusy("camera is already capturing a photo")
        try:
            return self._capture_fn()
        finally:
            self._lock.release()
