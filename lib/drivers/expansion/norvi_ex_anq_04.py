_CONTROL_REGISTER = 0x01
_VALUE_RANGE = 0xFFF


class ANQ04:

    def __init__(self, i2c, addr, modes=None):
        self._out = {
            "AO.0": {"config_bit": 0, "channel": 1},
            "AO.1": {"config_bit": 1, "channel": 2},
            "AO.2": {"config_bit": 2, "channel": 3},
            "AO.3": {"config_bit": 3, "channel": 4},
        }
        self._i2c = i2c
        self._addr = addr
        self._last = {name: 0 for name in self._out}  # commanded percent, for readback
        # config byte: bit per channel, 0 = 0-10V, 1 = 4-20mA
        modes = modes or {}
        ctrl = 0
        for name, config in self._out.items():
            ctrl |= (1 if modes.get(name) else 0) << config["config_bit"]
        self._i2c.writeto(self._addr, bytes([_CONTROL_REGISTER, ctrl]))

        for name in self._out:
            # if config has safe state
            self.set_value(name, 0)

    def set_value(self, name, value):
        ch = self._out[name]["channel"]
        pct = max(0, min(10000, int(value)))
        code = pct * _VALUE_RANGE // 10000  # percent -> 12-bit code
        reg = 1 + ch * 2
        self._i2c.writeto(self._addr, bytes([reg, code >> 8, code & 0xFF]))
        self._last[name] = pct

    def get_value(self, name):
        return self._last[name]  # echo commanded percent (see caveat)

    def get_all_values(self):
        return dict(self._last)  # canonical percent per channel
