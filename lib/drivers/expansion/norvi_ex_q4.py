# Find from MCP23008 documentation
_IODIR = 0x00  # 1 = input, 0 = output
_GPIO = 0x09  # read actual pin states
_OLAT = 0x0A  # output latch (what we drive)


class EXQ4:

    def __init__(self, i2c, addr):
        # Map norvi Q to the bit on the MCP23008 olat byte
        # 0b00000000
        #   ||||
        # Q 1234    the rest is unuse
        self._out = {
            "Q1": 7,
            "Q2": 6,
            "Q3": 5,
            "Q4": 4,
        }

        self._i2c = i2c
        self._addr = addr

        # Local representation of the output latch in the machine.
        # We must ensure it match the device output latch.
        self._olat = 0x00  # 0b0000000

        # IODIR is the register to hold the pins direction (1 -> input, 0 -> output)
        # 0x0F -> 0b00001111. Means GPIO 7-4 are outputs and GPIO 3-0 are inputs.
        # We set GPIO 3-0 to inputs direction because they are not used for this device.
        self._i2c.writeto_mem(self._addr, _IODIR, bytes([0x0F]))

        # Set the output latch to 0
        self._i2c.writeto_mem(self._addr, _OLAT, bytes([self._olat]))

    def _bit(self, pin):
        b = self._out.get(pin)
        if b is None:
            raise KeyError("EX-Q4: no pin '{}'".format(pin))
        return b

    def set_pin(self, pin, val):
        b = self._bit(pin)
        if val:
            # Set the bit b to 1
            # EX: b = 6
            # 1 << 6 = 0b01000000
            # if self._olat = 0b10000000
            # |= -> 0b10000000 | 0b01000000 = 0b11000000
            self._olat |= 1 << b
        else:
            # Set the bit b to 0
            # EX: b = 6
            # ~(1 << 6) = ~(0b01000000) = 0b10111111
            # if self._olat = 0b11000000
            # &= -> 0b11000000 & 0b10111111 = 0b10000000
            self._olat &= ~(1 << b)
        self._i2c.writeto_mem(self._addr, _OLAT, bytes([self._olat & 0xFF]))

    def get_pin(self, pin):
        b = self._bit(pin)
        data = self._i2c.readfrom_mem(self._addr, _GPIO, 1)[0]
        return (data >> b) & 1

    def get_all_pins(self):
        data = self._i2c.readfrom_mem(self._addr, _GPIO, 1)[0]  # one read = all 8 lines
        pins = {}
        for name, b in self._out.items():
            pins[name] = (data >> b) & 1
        return pins
