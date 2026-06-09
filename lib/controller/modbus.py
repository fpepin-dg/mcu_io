from lib.constants import *
from lib.modules.umodbus.serial import ModbusRTU

import time


class ModbusController:

    def __init__(
        self,
        board,
        io,
        registers,
        baudrate,
        poll_interval_ms,
        addr=1,
        bits=BITS,
        parity=PARITY,
        stop=STOP,
        callbacks=None,
    ):
        self._board = board
        self._io = io
        rs = board.rs485
        self._pins = (rs["tx"], rs["rx"])
        self._ctrl_pin = rs["ctrl_pin"]
        self._uart_id = rs["uart_id"]
        self._registers = registers
        self._callbacks = callbacks or {}
        self._addr = addr
        self._baudrate = baudrate
        self._bits = bits
        self._parity = parity
        self._stop = stop
        self._poll_interval_ms = poll_interval_ms

        self._refresh_list = []
        for rtype in ("COILS", "HREGS", "ISTS", "IREGS"):
            for name, reg in registers.get(rtype, {}).items():
                m = io.mapping_for(rtype, reg["register"])
                if m:
                    self._refresh_list.append(
                        (rtype, reg["register"], m["card"], m["pin"])
                    )

    def _refresh(self):
        snapshot = self._io.read_all()
        for rtype, addr, card, pin in self._refresh_list:
            val = snapshot.get(card, {}).get(pin)
            if val is None:
                continue
            try:
                if rtype == "COILS":
                    self._mb.set_coil(addr, bool(val))
                elif rtype == "HREGS":
                    self._mb.set_hreg(addr, val)
                elif rtype == "ISTS":
                    self._mb.set_ist(addr, bool(val))
                elif rtype == "IREGS":
                    self._mb.set_ireg(addr, val)
            except Exception:
                pass

    def _attach_callbacks(self) -> None:
        for reg_type, cbs in self._callbacks.items():
            for name, reg in self._registers.get(reg_type, {}).items():
                reg.update(cbs)

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
        self._attach_callbacks()
        try:
            self._mb.setup_registers(registers=self._registers)
        except Exception as e:
            self._board.display.show_error(e)

    def deinit(self) -> None:
        self._mb._itf._uart.deinit()

    def loop(self, board):
        last = time.ticks_ms()
        while True:
            try:
                now = time.ticks_ms()
                if time.ticks_diff(now, last) >= self._poll_interval_ms:
                    self._refresh()
                    last = now
                self._mb.process()  # must stay responsive every loop
            except Exception as e:
                board.display.show_text("{}: {}".format(type(e).__name__, e))
                time.sleep_ms(50)
                continue
            if self._mb.get_coil(0) == MODE_UPLOAD:
                time.sleep_ms(50)
                self.deinit()
                return
