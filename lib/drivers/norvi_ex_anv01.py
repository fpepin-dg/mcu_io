from lib.drivers.base import IOModuleBase
import utime


class NorviEX_ANV01(IOModuleBase):
    """
    Driver for the NORVI-EX-ANV01 4-channel 0-10 V analog input expansion.

    Hardware
    --------
      * Texas Instruments ADS1115 16-bit ADC (single-ended, 4 channels)
      * Each input passes through a 3.3 k / 2.2 k divider, so
            V_adc = 0.4 * V_terminal
        (terminal range 0..10 V -> ADC sees 0..4 V)
      * I2C interface, default address 0x48.
        Although ANV01_UG.pdf shows a DIP table for 0x20..0x27, that diagram
        is copy-pasted from the EX-Q4 (MCP23008) product. The ADS1115 can
        only physically respond at 0x48, 0x49, 0x4A or 0x4B (set by the
        ADDR pin on the chip), and the official Arduino sample hard-codes
        0x48. This driver accepts any of those four addresses.

    Naming convention
    -----------------
      AVAILABLE_PINS keys match the silkscreen: "A0", "A1", "A2", "A3".

    Reading model
    -------------
      get_pin_value(pin)  -> raw signed 16-bit ADC code (-32768..32767)
                             Negative values shouldn't occur with this
                             single-ended divider but are surfaced as-is.
      read_voltage(pin)   -> float, terminal voltage in volts (0..10 V)
      read_raw(pin)       -> alias for get_pin_value()

      get_all_states() returns the raw codes for all 4 channels, which is
      what the HAL bus payload expects (uniform with the digital drivers).

    Example config.json entry
    -------------------------
      {
        "card_number": 3,
        "type": "norvi_ex_anv01",
        "i2c_address": 72,
        "label": "tank levels",
        "config": { "gain": "2/3", "data_rate": 128 }
      }
    """

    # -------------------- ADS1115 register map --------------------

    _REG_CONVERSION = 0x00
    _REG_CONFIG = 0x01

    # Config register fields (see ADS1115 datasheet, section "Config Register")
    _CFG_OS_SINGLE = 0x8000  # Start a single conversion
    _CFG_MODE_SINGLE = 0x0100  # Single-shot mode
    _CFG_COMP_DISABLE = 0x0003  # Disable comparator

    # MUX = single-ended on AINx (channel 0..3)
    _MUX_SINGLE_ENDED = {
        0: 0x4000,  # AIN0 vs GND
        1: 0x5000,  # AIN1 vs GND
        2: 0x6000,  # AIN2 vs GND
        3: 0x7000,  # AIN3 vs GND
    }

    # PGA (Programmable Gain Amplifier) -> full-scale range in volts
    _PGA_TABLE = {
        "2/3": (0x0000, 6.144),
        "1": (0x0200, 4.096),
        "2": (0x0400, 2.048),
        "4": (0x0600, 1.024),
        "8": (0x0800, 0.512),
        "16": (0x0A00, 0.256),
    }

    # Data-rate table (samples per second -> config bits)
    _DR_TABLE = {
        8: 0x0000,
        16: 0x0020,
        32: 0x0040,
        64: 0x0060,
        128: 0x0080,  # ADS1115 default
        250: 0x00A0,
        475: 0x00C0,
        860: 0x00E0,
    }

    # -------------------- HAL surface --------------------

    AVAILABLE_PINS = {
        "A0": {"type": "analog_input"},
        "A1": {"type": "analog_input"},
        "A2": {"type": "analog_input"},
        "A3": {"type": "analog_input"},
    }

    _CHAN_INDEX = {"A0": 0, "A1": 1, "A2": 2, "A3": 3}

    # 3.3 k / 2.2 k divider on the front end -> V_adc = 0.4 * V_term
    _DIVIDER_RATIO = 0.311

    # -------------------- Construction --------------------

    def __init__(self, i2c, address, config=None):
        """
        Args:
            i2c:     An initialized machine.I2C bus.
            address: ADS1115 I2C address (0x48..0x4B). Decimal accepted.
            config:  Optional dict:
                       'gain'      : '2/3' (default), '1', '2', '4', '8', '16'
                       'data_rate' : 8/16/32/64/128/250/475/860 (default 128)
        """
        self.i2c = i2c
        self.address = address

        cfg = config or {}
        gain_key = str(cfg.get("gain", "2/3"))
        if gain_key not in self._PGA_TABLE:
            raise ValueError("ANV01: unknown gain '%s'" % gain_key)
        self._pga_bits, self._fsr_volts = self._PGA_TABLE[gain_key]

        dr = int(cfg.get("data_rate", 128))
        if dr not in self._DR_TABLE:
            raise ValueError("ANV01: unsupported data_rate %d" % dr)
        self._dr_bits = self._DR_TABLE[dr]

        # Shadow of the last raw reading per channel.
        self._last_raw = {pin: 0 for pin in self.AVAILABLE_PINS}

    # -------------------- Low-level I2C --------------------

    def _write_register(self, reg, value16):
        """Write a 16-bit big-endian word to a register."""
        hi = (value16 >> 8) & 0xFF
        lo = value16 & 0xFF
        self.i2c.writeto(self.address, bytes([reg, hi, lo]))

    def _read_register(self, reg):
        """Read a 16-bit big-endian word from a register."""
        self.i2c.writeto(self.address, bytes([reg]))
        buf = self.i2c.readfrom(self.address, 2)
        return (buf[0] << 8) | buf[1]

    @staticmethod
    def _to_signed16(u):
        return u - 0x10000 if u & 0x8000 else u

    def _convert_channel(self, channel):
        """Trigger a single-shot conversion on a channel and return signed raw."""
        cfg = (
            self._CFG_OS_SINGLE
            | self._MUX_SINGLE_ENDED[channel]
            | self._pga_bits
            | self._CFG_MODE_SINGLE
            | self._dr_bits
            | self._CFG_COMP_DISABLE
        )
        self._write_register(self._REG_CONFIG, cfg)

        # Give the ADS1115 time to actually start the conversion before we poll.
        utime.sleep_ms(2)

        # Poll OS bit until conversion completes, with a small gap between
        # transactions so we don't hammer the chip while it's still busy.
        for _ in range(200):
            status = self._read_register(self._REG_CONFIG)
            if status & 0x8000:
                break
            utime.sleep_ms(1)

        return self._to_signed16(self._read_register(self._REG_CONVERSION))

    # -------------------- IOModuleBase interface --------------------

    def get_pin_value(self, hw_pin):
        """Return the latest *terminal voltage* (volts, 0..10 V) for this channel.

        Triggers a fresh conversion. The HAL bus payload now carries volts,
        not raw codes, so downstream consumers (websocket, UI) get physical units.
        """
        if hw_pin not in self._CHAN_INDEX:
            raise KeyError(hw_pin)
        raw = self._convert_channel(self._CHAN_INDEX[hw_pin])
        self._last_raw[hw_pin] = raw
        v_adc = raw * self._fsr_volts / 32767.0
        v_term = v_adc / self._DIVIDER_RATIO
        return v_term

    def set_pin_value(self, hw_pin, value):
        """ANV01 channels are read-only."""
        return False

    def get_all_states(self):
        """Sequentially sample every channel and return raw codes."""
        return {pin: self.get_pin_value(pin) for pin in self.AVAILABLE_PINS}

    # -------------------- Convenience helpers --------------------

    def read_raw(self, hw_pin):
        """Alias for get_pin_value()."""
        return self.get_pin_value(hw_pin)

    def read_voltage(self, hw_pin):
        """Read a channel and return the *terminal* voltage in volts (0..10 V).

        Path:
            terminal V -> 3.3k/2.2k divider -> ADS1115 input
            V_adc      = raw * FSR / 32767
            V_terminal = V_adc / 0.4
        """
        raw = self.get_pin_value(hw_pin)
        v_adc = raw * self._fsr_volts / 32767.0
        return v_adc / self._DIVIDER_RATIO

    def read_all_voltages(self):
        return {pin: self.read_voltage(pin) for pin in self.AVAILABLE_PINS}
