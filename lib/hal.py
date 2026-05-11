from machine import I2C, Pin  # type: ignore

# ---------------------------------------------------------------------------
# Driver registry -- maps config "type" strings to driver classes.
# New drivers are added here with a single register_driver() call.
# ---------------------------------------------------------------------------

_DRIVER_REGISTRY = {}


def register_driver(type_name, driver_class):
    """Register a driver class under a config-friendly type name."""
    _DRIVER_REGISTRY[type_name] = driver_class


# Register built-in drivers.
# Each import pulls in only the class; the module-level Pin() calls inside
# each driver are harmless on the target hardware and skipped on import
# errors (e.g. when running tests on a PC).
try:
    from lib.drivers.norvi_ae01_r import NorviAE01R

    register_driver("norvi_ae01_r", NorviAE01R)
except ImportError:
    pass

try:
    from lib.drivers.norvi_ae01_t import NorviAE01T

    register_driver("norvi_ae01_t", NorviAE01T)
except ImportError:
    pass

try:
    from lib.drivers.norvi_ex_q4 import NorviEX_Q4

    register_driver("norvi_ex_q4", NorviEX_Q4)
except ImportError:
    pass

try:
    from lib.drivers.norvi_ex_anq_04 import NorviEX_ANQ04

    register_driver("norvi_ex_anq_04", NorviEX_ANQ04)
except ImportError:
    pass


# ---------------------------------------------------------------------------
# HAL -- Hardware Abstraction Layer
# ---------------------------------------------------------------------------


class HAL:
    """
    Central Hardware Abstraction Layer.

    Reads the full config, instantiates the correct PLC driver (card 0)
    and any number of I2C expansion modules, then routes logical I/O
    names to the appropriate driver transparently.

    Expected config structure:

        {
          "system": {
            "plc": {
              "card_number": 0,
              "type": "norvi_ae01_t",
              "device_id": "NORVI-AE01-T-01"
            },
            "io_cards": [
              {"card_number": 1, "type": "norvi_ex_q4", "i2c_address": 32}
            ],
            "telemetry_frequency_ms": 1000
          },
          "io_mapping": {
            "inputs":  {"SENSOR-A": {"card_number": 0, "hw_pin": "DI0"}},
            "outputs": {"VALVE-B":  {"card_number": 1, "hw_pin": "EO0"}}
          }
        }
    """

    _I2C_SDA_PIN = 16
    _I2C_SCL_PIN = 17

    def __init__(self, config):
        self._modules = {}  # card_number -> driver instance
        self._logical_to_card = {}  # logical_name -> (card_number, hw_pin)
        self._outputs = {}  # logical_name -> (card_number, hw_pin)
        self.i2c_bus = None

        system_cfg = config.get("system", {})
        plc_cfg = system_cfg.get("plc", {})
        io_cards = system_cfg.get("io_cards", [])

        # -- 1. Instantiate the PLC module (card 0) --
        plc_type = plc_cfg.get("type", "norvi_ae01_r")
        plc_class = _DRIVER_REGISTRY.get(plc_type)
        if plc_class:
            self._modules[0] = plc_class()
            print("HAL: PLC card 0 ->", plc_type)
        else:
            print("HAL: WARNING -- unknown PLC type:", plc_type)

        # -- 2. Instantiate expansion modules (cards 1..N) --
        if io_cards:
            self._init_i2c()

        for card_cfg in io_cards:
            card_num = int(card_cfg.get("card_number", 0))
            card_type = card_cfg.get("type", "")
            address = int(card_cfg.get("i2c_address", 0))
            label = card_cfg.get("label", "")
            extra_cfg = card_cfg.get("config", {}) or {}

            driver_class = _DRIVER_REGISTRY.get(card_type)
            if driver_class is None:
                print("HAL: WARNING -- unknown expansion type:", card_type)
                continue

            try:
                self._modules[card_num] = driver_class(
                    self.i2c_bus, address, config=extra_cfg
                )
                print(
                    "HAL: Expansion card %d -> %s at I2C 0x%02X %s"
                    % (card_num, card_type, address, label)
                )
            except OSError as exc:
                print(
                    "HAL: ERROR -- I2C device at 0x%02X not responding: %s"
                    % (address, exc)
                )

        # -- 3. Build logical-name mappings from io_mapping --
        io_mapping = config.get("io_mapping", {})
        self._build_mappings(io_mapping)

    # -----------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------

    def _init_i2c(self):
        """Initialize the shared I2C bus used by all expansion modules."""
        scl = Pin(self._I2C_SCL_PIN)
        sda = Pin(self._I2C_SDA_PIN)
        self.i2c_bus = I2C(1, scl=scl, sda=sda, freq=400000)
        print(
            "HAL: I2C bus initialized on SCL=%d, SDA=%d"
            % (self._I2C_SCL_PIN, self._I2C_SDA_PIN)
        )

    def _build_mappings(self, io_mapping):
        """
        Walk the io_mapping sections and link each logical name to its
        (card_number, hw_pin) pair, validating against the driver's
        AVAILABLE_PINS.
        """
        for section in ("inputs", "outputs"):
            items = io_mapping.get(section, {})
            for logical_name, entry in items.items():
                # Support old flat schema ("PUMP": "R0") and new dict schema
                if isinstance(entry, str):
                    card_num, hw_pin = 0, entry
                elif isinstance(entry, dict):
                    card_num = int(entry.get("card_number", 0) or 0)
                    hw_pin = entry.get("hw_pin")
                else:
                    print("HAL: WARNING -- bad mapping entry for:", logical_name)
                    continue

                if card_num not in self._modules:
                    print(
                        "HAL: WARNING -- card %d not found for '%s'"
                        % (card_num, logical_name)
                    )
                    continue

                module = self._modules[card_num]
                if hw_pin not in module.AVAILABLE_PINS:
                    print(
                        "HAL: WARNING -- hw_pin '%s' not on card %d for '%s'"
                        % (hw_pin, card_num, logical_name)
                    )
                    continue

                self._logical_to_card[logical_name] = (card_num, hw_pin)
                if module.AVAILABLE_PINS[hw_pin]["type"] in ("output", "analog_output"):
                    self._outputs[logical_name] = (card_num, hw_pin)

        print("HAL: mapped outputs ->", list(self._outputs.keys()))
        print(
            "HAL: mapped inputs  ->",
            [n for n in self._logical_to_card if n not in self._outputs],
        )

    # -----------------------------------------------------------------
    # Public API (same interface the old monolithic class exposed)
    # -----------------------------------------------------------------

    def set_output(self, logical_name, value_str):
        if logical_name not in self._outputs:
            return False
        card_num, hw_pin = self._outputs[logical_name]
        module = self._modules[card_num]
        pin_type = module.AVAILABLE_PINS[hw_pin]["type"]

        if pin_type == "output":  # digital
            value = 1 if value_str.upper() == "ON" else 0
        elif pin_type == "analog_output":  # new
            try:
                value = float(value_str)
            except ValueError:
                return False
        else:
            return False
        return module.set_pin_value(hw_pin, value)

    def get_all_states(self):
        """
        Return a dict of {logical_name: value} for every mapped I/O point
        (inputs and outputs combined).
        """
        payload = {}
        for logical_name, (card_num, hw_pin) in self._logical_to_card.items():
            payload[logical_name] = self._modules[card_num].get_pin_value(hw_pin)
        return payload

    def get_module(self, card_number):
        """
        Return the raw driver instance for a given card number, or None.
        Useful for accessing peripheral helpers (init_rs485, read_buttons, etc.).
        """
        return self._modules.get(card_number)


# ---------------------------------------------------------------------------
# Debug / diagnostic entry point
# Run directly:  import lib.hal   (from REPL)
#           or:  exec(open('lib/hal.py').read())
# ---------------------------------------------------------------------------

if __name__ == "__main__" or __name__ == "lib.hal":
    import sys

    def _run_diagnostics():
        """
        Standalone I2C and expansion-module diagnostics.
        Scans the bus, probes the NORVI-EX-Q4 starting at 0x20
        (auto-detects in 0x20-0x27 range), and toggles each output
        to verify wiring.
        """
        print("=" * 50)
        print("HAL DIAGNOSTICS")
        print("=" * 50)

        # -- 1. I2C bus scan --
        print("\n[1] I2C bus scan (SCL=17, SDA=16)...")
        try:
            i2c = I2C(1, scl=Pin(17), sda=Pin(16), freq=400000)
            devices = i2c.scan()
            if devices:
                print("    Found %d device(s):" % len(devices))
                for addr in devices:
                    print("      - 0x%02X  (decimal %d)" % (addr, addr))
            else:
                print("    WARNING: No I2C devices found!")
                print("    Check wiring: SDA=GPIO16, SCL=GPIO17, 3.3V, GND")
                print("    Check DIP switch settings on expansion board")
                return
        except OSError as exc:
            print("    ERROR: I2C bus init failed:", exc)
            return

        # -- 2. Probe NORVI-EX-Q4 in range 0x20-0x27 --
        target_addr = 0x20
        print("\n[2] Probing NORVI-EX-Q4 at 0x%02X..." % target_addr)
        if target_addr not in devices:
            print("    WARNING: Device at 0x%02X not found on bus!" % target_addr)
            print("    Devices found:", ["0x%02X" % d for d in devices])
            # Try all possible addresses
            for addr in range(0x20, 0x28):
                if addr in devices:
                    print("    -> Found MCP23008 at 0x%02X instead?" % addr)
                    target_addr = addr
                    break
            else:
                print("    No MCP23008 found in range 0x20-0x27.")
                return

        # -- 3. Read MCP23008 registers --
        print("\n[3] Reading MCP23008 registers at 0x%02X..." % target_addr)
        REG_IODIR = 0x00
        REG_GPIO = 0x09
        REG_OLAT = 0x0A

        def read_reg(reg):
            i2c.writeto(target_addr, bytes([reg]))
            return i2c.readfrom(target_addr, 1)[0]

        def write_reg(reg, val):
            i2c.writeto(target_addr, bytes([reg, val]))

        iodir = read_reg(REG_IODIR)
        gpio = read_reg(REG_GPIO)
        olat = read_reg(REG_OLAT)
        print("    IODIR = 0x%02X  (expect 0xF0: bits 0-3 output, 4-7 input)" % iodir)
        print("    GPIO  = 0x%02X" % gpio)
        print("    OLAT  = 0x%02X" % olat)

        # -- 4. Configure and test outputs --
        print("\n[4] Configuring IODIR = 0xF0 (GP0-GP3 as outputs)...")
        write_reg(REG_IODIR, 0xF0)
        iodir = read_reg(REG_IODIR)
        print("    IODIR after write = 0x%02X" % iodir)

        print("\n[5] Toggling outputs one by one...")
        import utime

        pin_map = {"Q1": 3, "Q2": 2, "Q3": 1, "Q4": 0}
        for name, bit in pin_map.items():
            val = 1 << bit
            print("    %s (GP%d, bit %d) -> ON  (GPIO=0x%02X)" % (name, bit, bit, val))
            write_reg(REG_GPIO, val)
            utime.sleep_ms(500)

            readback = read_reg(REG_GPIO)
            print(
                "    %s readback GPIO = 0x%02X  %s"
                % (name, readback, "OK" if (readback & val) else "FAIL - bit not set!")
            )

            write_reg(REG_GPIO, 0x00)
            utime.sleep_ms(200)

        # -- 5. All ON, then all OFF --
        print("\n[6] All outputs ON (GPIO=0x0F)...")
        write_reg(REG_GPIO, 0x0F)
        readback = read_reg(REG_GPIO)
        print(
            "    Readback = 0x%02X  %s"
            % (readback, "OK" if readback & 0x0F == 0x0F else "FAIL")
        )
        utime.sleep_ms(1000)

        print("    All outputs OFF...")
        write_reg(REG_GPIO, 0x00)
        readback = read_reg(REG_GPIO)
        print("    Readback = 0x%02X" % readback)

        # -- 6. Test via driver class --
        print("\n[7] Testing via NorviEX_Q4 driver class...")
        try:
            from lib.drivers.norvi_ex_q4 import NorviEX_Q4

            module = NorviEX_Q4(i2c, target_addr)
            print("    Driver instantiated OK")

            # Toggle each output individually (turn off after each)
            for pin_name in ("Q1", "Q2", "Q3", "Q4"):
                module.set_pin_value(pin_name, 1)
                state = module.get_pin_value(pin_name)
                print(
                    "    %s -> ON, readback=%d  %s"
                    % (pin_name, state, "OK" if state == 1 else "FAIL")
                )
                utime.sleep_ms(5000)
                module.set_pin_value(pin_name, 0)

            # Turn all ON, then verify get_all_states()
            for pin_name in ("Q1", "Q2", "Q3", "Q4"):
                module.set_pin_value(pin_name, 1)
            all_states = module.get_all_states()
            print("    get_all_states() (all ON):", all_states)

            # Turn all OFF
            for pin_name in ("Q1", "Q2", "Q3", "Q4"):
                module.set_pin_value(pin_name, 0)
            all_states = module.get_all_states()
            print("    get_all_states() (all OFF):", all_states)
        except Exception as exc:
            print("    ERROR in driver test:", exc)
            sys.print_exception(exc)

        print("\n" + "=" * 50)
        print("DIAGNOSTICS COMPLETE")
        print("=" * 50)

    # Only auto-run when executed as main script
    if __name__ == "__main__":
        _run_diagnostics()
