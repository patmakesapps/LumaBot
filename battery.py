"""Read the X1200's MAX17040-compatible fuel gauge at I2C address 0x36."""

from smbus2 import SMBus


class BatteryGauge:
    def __init__(self, enabled: bool = False, bus_number: int = 1, address: int = 0x36):
        self.enabled = enabled
        self.bus_number = bus_number
        self.address = address

    def read(self) -> dict:
        if not self.enabled:
            return {"battery_pct": None, "battery_voltage_v": None}

        with SMBus(self.bus_number) as bus:
            voltage_bytes = bus.read_i2c_block_data(self.address, 0x02, 2)
            percent_bytes = bus.read_i2c_block_data(self.address, 0x04, 2)

        voltage_raw = ((voltage_bytes[0] << 8) | voltage_bytes[1]) >> 4
        voltage_v = voltage_raw * 0.00125
        percent = percent_bytes[0] + percent_bytes[1] / 256.0
        return {
            "battery_pct": round(max(0.0, min(100.0, percent)), 1),
            "battery_voltage_v": round(voltage_v, 3),
        }
