class BoardBase:
    """Hardware abstraction every PLC card implements."""

    # ---- digital IO ----
    def set_value(self, name, val):
        raise NotImplementedError

    def get_value(self, name):
        raise NotImplementedError

    def get_all_values(self):
        raise NotImplementedError

    # ---- resources exposed to controllers ----
    @property
    def i2c(self):
        return self._i2c

    @property
    def display(self):
        return self._display  # may be None on cards without one

    @property
    def has_display(self) -> bool:
        return self._display is not None

    @property
    def rs485(self) -> dict:
        """Everything ModbusRTU / raw RS485 need to open the UART."""
        return self._rs485
