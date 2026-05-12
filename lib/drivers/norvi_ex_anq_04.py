from lib.drivers.base import IOModuleBase


class NorviEX_ANQ04(IOModuleBase):
    """
    Driver for the NORVI EX-ANQ 04 quad-channel analog-output expansion.

    Hardware
    --------
      * STM32F103 acting as an I2C slave; internally drives an AD74413R DAC
        over SPI.
      * 4 analog output channels labelled on the silkscreen as
        AO.0, AO.1, AO.2, AO.3 (each followed by an AGND terminal).
      * Each channel can be independently configured for either
        0-10 V output or 4-20 mA output via the Control register.
      * 12-bit resolution: code 0 -> 0 V / 0 mA, code 4095 -> 10 V / 20 mA.

    I2C address
    -----------
      Base address is 0x50; the 4 DIP switches at the bottom of the module
      OR in a value of 0x00..0x0F, giving a final address in 0x50..0x5F.
      The Arduino example shipped by NORVI hard-codes 0x5F (all DIPs ON).

      In config.json store the *full* address as a decimal:
          0x5F -> 95
          0x50 -> 80

    Protocol  (verified against NORVI's official Arduino example)
    --------
      Config register
          pointer = 0x01,  payload = 1 byte
          bit0 = c1 mode  -> AO.0
          bit1 = c2 mode  -> AO.1
          bit2 = c3 mode  -> AO.2
          bit3 = c4 mode  -> AO.3
              0 = 0-10 V
              1 = 4-20 mA

      Channel value registers
          pointer = 1 + (channel_1based * 2)
              -> AO.0 (channel 1) = 0x03
              -> AO.1 (channel 2) = 0x05
              -> AO.2 (channel 3) = 0x07
              -> AO.3 (channel 4) = 0x09
          payload = 2 bytes, big-endian, lower 12 bits = DAC code

    Naming convention used by this driver
    -------------------------------------
      Pin names (hw_pin / AVAILABLE_PINS keys) match the silkscreen:
          "AO.0", "AO.1", "AO.2", "AO.3"
      Config keys match NORVI's c1..c4 numbering used by config_dac():
          "c1" -> AO.0, "c2" -> AO.1, "c3" -> AO.2, "c4" -> AO.3

    Example config.json entry
    -------------------------
      {
        "card_number": 2,
        "type": "norvi_ex_anq_04",
        "i2c_address": 95,
        "label": "process AO",
        "config": { "c1": 0, "c2": 0, "c3": 1, "c4": 1 }
      }
    """

    # -------------------- Constants --------------------

    MODE_VOLTAGE = 0  # 0-10 V
    MODE_CURRENT = 1  # 4-20 mA

    DAC_RESOLUTION_BITS = 12
    DAC_MAX_CODE = 0x0FFF  # 4095

    I2C_ADDR_BASE = 0x50  # 0x50..0x5F (4 DIP switches)
    I2C_ADDR_MASK = 0x0F

    _REG_CONFIG = 0x01

    AVAILABLE_PINS = {
        "AO.0": {"type": "analog_output"},
        "AO.1": {"type": "analog_output"},
        "AO.2": {"type": "analog_output"},
        "AO.3": {"type": "analog_output"},
    }

    # Pin name -> 1-based channel index used by NORVI's protocol.
    _CHAN_INDEX = {
        "AO.0": 1,
        "AO.1": 2,
        "AO.2": 3,
        "AO.3": 4,
    }

    # NORVI's config-key numbering (c1..c4) maps onto pins AO.0..AO.3.
    _CONFIG_KEY_TO_PIN = {
        "c1": "AO.0",
        "c2": "AO.1",
        "c3": "AO.2",
        "c4": "AO.3",
    }

    # -------------------- Helpers --------------------

    @staticmethod
    def _coerce_code(value):
        """Accept int (0..4095), str int ('2000'), or percent ('50%')."""
        if isinstance(value, str):
            v = value.strip()
            if v.endswith("%"):
                pct = max(0.0, min(100.0, float(v[:-1])))
                return int(round(pct / 100.0 * NorviEX_ANQ04.DAC_MAX_CODE))
            value = int(v)
        return max(0, min(NorviEX_ANQ04.DAC_MAX_CODE, int(value)))

    @classmethod
    def address_from_dip(cls, dip_value):
        """Compute the I2C address from the 4-bit DIP value (0..15)."""
        if not 0 <= dip_value <= cls.I2C_ADDR_MASK:
            raise ValueError("DIP value must be 0x00..0x0F")
        return cls.I2C_ADDR_BASE | dip_value

    INVERT_DIP_LOW_NIBBLE = True

    @classmethod
    def _resolve_address(cls, label_address):
        """
        Convert the DIP-label address (what's written on the board) into the
        real I2C address used for transactions.

        Accepts the full 7-bit address (e.g. 0x50..0x5F). Only the low nibble
        is inverted; the upper nibble is preserved verbatim so the helper
        stays a no-op for callers passing an already-resolved address with
        INVERT_DIP_LOW_NIBBLE set to False.
        """
        if not cls.INVERT_DIP_LOW_NIBBLE:
            return label_address
        return (label_address & 0xF0) | (~label_address & cls.I2C_ADDR_MASK)

    # -------------------- Construction --------------------

    def __init__(self, i2c, address, config=None):
        """
        Args:
            i2c:     An initialized machine.I2C bus instance.
            address: 4-bit I2C address (0x00..0x0F). Decimal accepted.
            config:  Optional dict with keys 'c1'..'c4', each '0' or '1'.
                     Missing keys default to '0' (voltage mode).
        """
        self.i2c = i2c
        self.address = self._resolve_address(address)
        config = config or {}

        # Per-pin mode (0 = voltage, 1 = current). Defaults to voltage.
        self._mode = {pin: self.MODE_VOLTAGE for pin in self.AVAILABLE_PINS}
        for cfg_key, pin in self._CONFIG_KEY_TO_PIN.items():
            if cfg_key in config:
                self._mode[pin] = config[cfg_key]

        # Shadow of last commanded code per channel.
        self._last_value = {pin: 0 for pin in self.AVAILABLE_PINS}

        # Push config to the device, then drive every channel to 0.
        self._write_config()
        for pin in self.AVAILABLE_PINS:
            self.set_pin_value(pin, 0)

    # -------------------- Low-level I2C --------------------

    def _write_config(self):
        """Write the per-channel mode byte to the Config register (0x01).

        Bit ordering matches NORVI's config_dac():
            (c4 << 3) | (c3 << 2) | (c2 << 1) | c1
        which is equivalent to 'bit i = mode of channel i+1' (1-based).
        """
        ctrl = 0
        for pin, idx in self._CHAN_INDEX.items():
            if self._mode[pin] == self.MODE_CURRENT:
                ctrl |= 1 << (idx - 1)  # c1 -> bit0, c2 -> bit1, ...
        self.i2c.writeto(self.address, bytes([self._REG_CONFIG, ctrl]))

    def _write_channel_code(self, channel_1based, code):
        """Write a 12-bit code to a channel (channel_1based in 1..4)."""
        pointer = 1 + (channel_1based * 2)  # 3, 5, 7, 9
        hi = (code >> 8) & 0xFF
        lo = code & 0xFF
        self.i2c.writeto(self.address, bytes([pointer, hi, lo]))

    # -------------------- IOModuleBase interface --------------------

    def get_pin_value(self, hw_pin):
        """Return the last commanded 12-bit code for this channel."""
        if hw_pin not in self._CHAN_INDEX:
            raise KeyError(hw_pin)
        return self._last_value[hw_pin]

    def set_pin_value(self, hw_pin, value):
        """
        Write a 12-bit DAC code to a channel.
        Accepts int 0..4095, str int '2000', or percent '50%'.
        Returns True on success, False if the pin is unknown.
        """
        if hw_pin not in self._CHAN_INDEX:
            return False
        code = self._coerce_code(value)
        self._write_channel_code(self._CHAN_INDEX[hw_pin], code)
        self._last_value[hw_pin] = code
        return True

    def get_all_states(self):
        return dict(self._last_value)

    # -------------------- Analog convenience methods --------------------

    def set_voltage(self, hw_pin, volts):
        """Set channel to a voltage (0..10 V). Channel must be in 'V' mode."""
        v = max(0.0, min(10.0, float(volts)))
        return self.set_pin_value(hw_pin, int(round(v / 10.0 * self.DAC_MAX_CODE)))

    def set_current(self, hw_pin, milliamps):
        """Set channel to a current (0..20 mA). Channel must be in 'mA' mode.

        Note: per the datasheet, the DAC code maps linearly across 0..20 mA,
        so 4 mA corresponds to code = 4/20 * 4095 ~= 819, not 0.
        """
        ma = max(0.0, min(20.0, float(milliamps)))
        return self.set_pin_value(hw_pin, int(round(ma / 20.0 * self.DAC_MAX_CODE)))

    def get_mode(self, hw_pin):
        """Return 'V' or 'mA' for a channel."""
        return "mA" if self._mode[hw_pin] == self.MODE_CURRENT else "V"

    def set_mode(self, hw_pin, mode):
        """Reconfigure a channel's output mode at runtime."""
        if hw_pin not in self._mode:
            return False
        self._mode[hw_pin] = self._parse_mode(mode)
        self._write_config()
        return True

    def get_status(self):
        """
        Read the Status register.

        NOTE: Neither the datasheet nor the user guide nor the official
        Arduino example documents the I2C read protocol or pointer for
        this register, so this stub is left unimplemented. If/when NORVI
        publishes the read pointer (or you sniff it from the STM32
        firmware), populate `_REG_STATUS` and uncomment the body below.
        """
        raise NotImplementedError(
            "EX-ANQ-04 status-register read protocol is not documented."
        )
        # _REG_STATUS = 0x??
        # self.i2c.writeto(self.address, bytes([_REG_STATUS]))
        # raw = self.i2c.readfrom(self.address, 1)[0]
        # return {
        #     "raw": raw,
        #     "AO.0_fault":        bool(raw & (1 << 0)),
        #     "AO.1_fault":        bool(raw & (1 << 1)),
        #     "AO.2_fault":        bool(raw & (1 << 2)),
        #     "AO.3_fault":        bool(raw & (1 << 3)),
        #     "over_temperature":  bool(raw & (1 << 4)),
        #     "charge_pump_error": bool(raw & (1 << 5)),
        #     "psu_error":         bool(raw & (1 << 6)),
        #     "avdd_psu_error":    bool(raw & (1 << 7)),
        # }
