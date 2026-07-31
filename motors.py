"""Adafruit Motor Bonnet control for LumaBot's two drive motors."""


class MotorsNotReady(RuntimeError):
    """Raised when movement is requested before motor bring-up is complete."""


class MotorController:
    def __init__(self, enabled: bool = False, address: int = 0x60):
        self.left = 0.0
        self.right = 0.0
        self._kit = None
        if enabled:
            import board
            from adafruit_motorkit import MotorKit

            self._kit = MotorKit(i2c=board.I2C(), address=address)
        self.ready = self._kit is not None

    def set_motors(self, left: float, right: float) -> None:
        if not self.ready:
            self.coast()
            raise MotorsNotReady("motors are disabled")

        left = max(-1.0, min(1.0, float(left)))
        right = max(-1.0, min(1.0, float(right)))
        try:
            self._kit.motor1.throttle = -left
            self._kit.motor4.throttle = right
        except Exception:
            self.coast()
            raise
        self.left, self.right = left, right

    def coast(self) -> None:
        if self._kit is not None:
            self._kit.motor1.throttle = None
            self._kit.motor4.throttle = None
        self.left = 0.0
        self.right = 0.0
