from lib.constants import *
from machine import Pin
from lib.modules.umodbus.serial import ModbusRTU
from lib.controller.display import DisplayController

import time


class ModbusController:
    def __init__(
        self,
        registers: dict[str, dict[str, dict[str, int]]],
        addr: int = 1,
        baudrate: int = BAUDRATE,
        tx: int = TX_PIN_NUMBER,
        rx: int = RX_PIN_NUMBER,
        ctrl_pin: int = FC_PIN_NUMBER,
        uart_id: int = UART_ID,
        bits: int = BITS,
        parity: int = PARITY,
        stop: int = STOP,
    ):
        self._registers = registers
        self._addr = addr
        self._baudrate = baudrate
        self._pins = (Pin(tx), Pin(rx))
        self._ctrl_pin = Pin(ctrl_pin)
        self._uart_id = uart_id
        self._bits = bits
        self._parity = parity
        self._stop = stop

    def init(self) -> None:
        self._mb = ModbusRTU(
            addr=self._addr,
            pins=self._pins,
            baudrate=self._baudrate,
            data_bits=self._bits,
            stop_bits=self._stop,
            parity=self._parity,
            ctrl_pin=self._ctrl_pin,
            uart_id=self._uart_id,
        )
        self._mb.setup_registers(registers=self._registers)
        print("Register setup done")

    def deinit(self) -> None:
        self._mb._itf._uart.deinit()

    def loop(self, oledController: DisplayController) -> None:
        while True:
            try:
                self._mb.process()
            except Exception as e:
                oledController.show_text("LOOP_ERROR:" + str(e))
                time.sleep_ms(50)
                continue

            if self._mb.get_coil(0) == MODE_UPLOAD:
                time.sleep_ms(50)  # let the Modbus ack finish on the wire
                self.deinit()
                return
