"""One in-process lock for every device on LumaBot's shared I2C bus."""

import threading


I2C_LOCK = threading.RLock()
