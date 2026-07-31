"""Safe motor boundary until the Motor HAT mapping is bench-verified."""

from dataclasses import dataclass


class MotorsNotReady(RuntimeError):
    """Raised when movement is requested before motor bring-up is complete."""


@dataclass
class MotorController:
    left: float = 0.0
    right: float = 0.0
    ready: bool = False

    def set_motors(self, left: float, right: float) -> None:
        self.coast()
        raise MotorsNotReady("motors are not connected and bench-verified")

    def coast(self) -> None:
        self.left = 0.0
        self.right = 0.0
