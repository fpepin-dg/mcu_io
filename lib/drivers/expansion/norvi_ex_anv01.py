# ADS1115 documentation : https://www.ti.com/lit/ds/symlink/ads1115.pdf
from constants import ANV01_FSC

import time

_REG_CONVERSION = 0x00
_REG_CONFIG = 0x01


class ANV01:
    """NORVI EX-ANV01: 4-channel 0-10V analog input (ADS1115). Read-only.

    Output: 0-10000 (percent of 0-10V range, 0.01% units) to match the
    canonical IO convention. Maps to Modbus IREGS (input registers).
    """

    # MUX[2:0] single-ended: AINx vs GND (datasheet Table 8-3)

    def __init__(self, i2c, addr, full_scale_counts=None):
        self._in = {"A0": 0b100, "A1": 0b101, "A2": 0b110, "A3": 0b111}
        self._i2c = i2c
        self._addr = addr
        # measured ADC count at 10V terminal (=100%). CALIBRATE empirically.
        self._fs = full_scale_counts or ANV01_FSC
        self._last = {name: 0 for name in self._in}

    def _read_raw(self, name):
        mux = self._in[name]
        config = (
            (1 << 15)  # OS = 1: start single conversion
            | (mux << 12)  # MUX: single-ended AINx vs GND
            | (0b000 << 9)  # PGA = 000: ±6.144V (max input headroom)
            | (1 << 8)  # MODE = 1: single-shot
            | (0b100 << 5)  # DR = 100: 128SPS
            | 0b00011  # COMP_QUE = 11 (disabled) + comparator bits 0
        )
        self._i2c.writeto_mem(
            self._addr, _REG_CONFIG, bytes([config >> 8, config & 0xFF])
        )
        time.sleep_ms(10)  # 128SPS conversion ~8ms + 25us powerup
        raw = self._i2c.readfrom_mem(self._addr, _REG_CONVERSION, 2)
        v = (raw[0] << 8) | raw[1]
        return v - 0x10000 if v > 0x7FFF else v  # signed 16-bit (2's comp)

    def set_value(self, name, value):
        return False  # analog input: read-only

    def get_value(self, name):
        raw = self._read_raw(name)
        if raw < 0:
            raw = 0  # single-ended; clamp offset noise
        pct = raw * 10000 // self._fs
        self._last[name] = max(0, min(10000, pct))
        return self._last[name]

    def get_all_values(self):
        values = {name: self.get_value(name) for name in self._in}
        return values
