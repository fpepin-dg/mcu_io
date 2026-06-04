from machine import Pin, I2C
from lib.controller.display import SSD1306Display
from lib.drivers.board.board_base import BoardBase


class AE01T(BoardBase):
    def __init__(self, freq):
        self._freq = freq

        self._out = {
            "T0.0": Pin(27, Pin.OUT),
            "T0.1": Pin(26, Pin.OUT),
            "T0": Pin(14, Pin.OUT),
            "T1": Pin(12, Pin.OUT),
            "T2": Pin(13, Pin.OUT),
            "T3": Pin(15, Pin.OUT),
            "T4": Pin(2, Pin.OUT),
            "T5": Pin(33, Pin.OUT),
        }
        self._in = {
            "DI0": Pin(18, Pin.IN),
            "DI1": Pin(39, Pin.IN),
            "DI2": Pin(34, Pin.IN),
            "DI3": Pin(35, Pin.IN),
            "DI4": Pin(19, Pin.IN),
            "DI5": Pin(21, Pin.IN),
            "DI6": Pin(22, Pin.IN),
            "DI7": Pin(23, Pin.IN),
        }

        # RS485
        self._rs485 = {
            "tx": Pin(1),
            "rx": Pin(3),
            "ctrl_pin": Pin(4, Pin.OUT, value=0),
            "uart_id": 1,
        }

        # I2C
        self._sda = Pin(16)
        self._scl = Pin(17)
        self._i2c = I2C(0, sda=self._sda, scl=self._scl, freq=self._freq)

        self._display = SSD1306Display(
            width=128, height=64, i2c=self._i2c, i2c_addr=0x3C
        )

    def set_pin(self, pin, val):
        p = self._out.get(pin)
        if p is None:
            raise KeyError("AE01T: no output pin '{}'".format(pin))
        if isinstance(val, (list, tuple)):  # umodbus passes [0] / [1]
            val = val[0] if val else 0
        p.value(1 if val else 0)

    def get_pin(self, pin):
        p = self._in.get(pin) or self._out.get(pin)
        if p is None:
            raise KeyError("AE01T: no pin '{}'".format(pin))
        return p.value()

    def get_all_pins(self):
        pins = {}
        for k, p in self._in.items():
            pins[k] = p.value()
        for k, p in self._out.items():
            pins[k] = p.value()
        return pins
