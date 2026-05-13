from lib.drivers.base import IOModuleBase


class NorviEX_Q4(IOModuleBase):
    """
    Driver for the NORVI-EX-Q4 expansion module.

    4 optically isolated transistor outputs (Q1-Q4) driven by an
    MCP23008 I2C I/O expander.  Supports loads up to 36V DC,
    300mW power dissipation per output.

    Address range: 0x20-0x27 (set via A0-A2 DIP switches on the board).

    DIP switch address table (active-low: ON grounds the pin = 0,
    OFF leaves it pulled high = 1; switch 4 is unused):
      A0(sw1) A1(sw2) A2(sw3) -> Address  Decimal
      OFF     OFF     OFF     -> 0x20     32
      ON      OFF     OFF     -> 0x21     33
      OFF     ON      OFF     -> 0x22     34
      ON      ON      OFF     -> 0x23     35
      OFF     OFF     ON      -> 0x24     36
      ON      OFF     ON      -> 0x25     37
      OFF     ON      ON      -> 0x26     38
      ON      ON      ON      -> 0x27     39

    Use the decimal value in config.json "i2c_address" field.

    Terminal arrangement (from NORVI official example):
      Q1 (OUTPUT1) -> GP3  (MCP23008 bit 3)
      Q2 (OUTPUT2) -> GP2  (MCP23008 bit 2)
      Q3 (OUTPUT3) -> GP1  (MCP23008 bit 1)
      Q4 (OUTPUT4) -> GP0  (MCP23008 bit 0)

    MCP23008 register map (relevant subset):
      IODIR   (0x00) - I/O direction: 0=output, 1=input
      GPIO    (0x09) - Port value (read/write)
      OLAT    (0x0A) - Output latch

    Bits 0-3 are wired to transistor outputs.
    Bits 4-7 are unused and kept as inputs (high-impedance) by default.
    """

    # MCP23008 register addresses
    _REG_IODIR = 0x00
    _REG_GPIO = 0x09
    _REG_OLAT = 0x0A

    I2C_ADDR_MASK = 0x07

    AVAILABLE_PINS = {
        "Q1": {"type": "output"},
        "Q2": {"type": "output"},
        "Q3": {"type": "output"},
        "Q4": {"type": "output"},
    }

    # Maps terminal label -> MCP23008 GPIO bit index
    _PIN_INDEX = {
        "Q1": 7,  # GP7
        "Q2": 6,  # GP6
        "Q3": 5,  # GP5
        "Q4": 4,  # GP4
    }

    INVERT_DIP_LOW_NIBBLE = False

    @classmethod
    def _resolve_address(cls, label_address):
        if not cls.INVERT_DIP_LOW_NIBBLE:
            return label_address
        upper_mask = (~cls.I2C_ADDR_MASK) & 0xFF  # everything *not* set by DIPs
        return (label_address & upper_mask) | (~label_address & cls.I2C_ADDR_MASK)

    # Bitmask covering only the 4 wired outputs (bits 0-3)
    _OUTPUT_MASK = 0xF0

    def __init__(self, i2c, address, config=None):
        """
        Args:
            i2c:     An initialized machine.I2C bus instance.
            address: The 7-bit I2C address of this MCP23008 (0x20-0x27).
            config:  Optional configuration dictionary.
        """
        self.i2c = i2c
        self.address = self._resolve_address(address)
        self.config = config or {}
        self._output_state = 0x00  # Track output latch locally

        # Bits 0-3 = outputs (0), bits 4-7 = inputs (1)
        # IODIR: 0 = output, 1 = input  ->  0xF0
        self._write_register(self._REG_IODIR, 0x0F)
        # All outputs OFF
        self._write_register(self._REG_GPIO, 0x00)

    # -- Low-level I2C register access --

    def _write_register(self, reg, value):
        """Write a single byte to a register."""
        self.i2c.writeto(self.address, bytes([reg, value]))

    def _read_register(self, reg):
        """Read a single byte from a register."""
        self.i2c.writeto(self.address, bytes([reg]))
        return self.i2c.readfrom(self.address, 1)[0]

    # -- IOModuleBase interface --

    def get_pin_value(self, hw_pin):
        idx = self._PIN_INDEX[hw_pin]
        gpio_val = self._read_register(self._REG_GPIO)
        return (gpio_val >> idx) & 1

    def set_pin_value(self, hw_pin, value):
        idx = self._PIN_INDEX[hw_pin]
        if value:
            self._output_state |= 1 << idx
        else:
            self._output_state &= ~(1 << idx)
        # Only touch bits 0-3
        self._write_register(self._REG_GPIO, self._output_state & self._OUTPUT_MASK)
        return True

    def get_all_states(self):
        gpio_val = self._read_register(self._REG_GPIO)
        return {name: (gpio_val >> idx) & 1 for name, idx in self._PIN_INDEX.items()}
