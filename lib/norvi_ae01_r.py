from machine import Pin, I2C, UART, ADC  # type: ignore

class NorviIIOT_AE01_R:
    """
    Hardware Abstraction Layer for the NORVI IIOT-AE01-R.
    This class maps logical component names from a config file to the
    physical pins of the device.
    """

    # Private map of all physical pins available on this specific board
    _PHYSICAL_PINS = {
        "DI0": Pin(18, Pin.IN), "DI1": Pin(39, Pin.IN), "DI2": Pin(34, Pin.IN),
        "DI3": Pin(35, Pin.IN), "DI4": Pin(19, Pin.IN), "DI5": Pin(21, Pin.IN),
        "DI6": Pin(22, Pin.IN), "DI7": Pin(23, Pin.IN),
        "R0": Pin(14, Pin.OUT), "R1": Pin(12, Pin.OUT), "R2": Pin(13, Pin.OUT),
        "R3": Pin(15, Pin.OUT), "R4": Pin(2, Pin.OUT),   "R5": Pin(33, Pin.OUT),
        "T0": Pin(26, Pin.OUT), "T1": Pin(27, Pin.OUT),
    }
    # Pins for other fixed peripherals
    _RS485_TX_PIN = 1
    _RS485_RX_PIN = 3
    _RS485_FC_PIN = 4
    _I2C_SDA_PIN = 16
    _I2C_SCL_PIN = 17
    _BUTTONS_ADC_PIN = 32

    def __init__(self, io_mapping):
        """
        Initializes the HAL using a mapping dictionary from the config.
        """
        self._logical_to_physical = {}
        self._outputs = {} # Quick lookup dict for all logical outputs

        def _entry_to_hw_pin(entry):
            """Returns a `(card_number, hw_pin)` tuple from old/new schema entries."""
            # Old schema: "MAIN-PUMP": "R0"
            if isinstance(entry, str):
                return 0, entry

            # New schema: "MAIN-PUMP": {"card_number": 0, "hw_pin": "R0"}
            if isinstance(entry, dict):
                return int(entry.get('card_number', 0) or 0), entry.get('hw_pin')

            return 0, None

        # Process the mappings provided in the config
        # This builds the bridge between "MAIN-PUMP" and the actual Pin object
        if io_mapping and 'inputs' in io_mapping:
            for logical_name, entry in io_mapping['inputs'].items():
                card_number, hw_pin = _entry_to_hw_pin(entry)
                if card_number != 0:
                    print("Warning: ignoring input on unsupported card_number:", logical_name, card_number)
                    continue
                if hw_pin in self._PHYSICAL_PINS:
                    self._logical_to_physical[logical_name] = self._PHYSICAL_PINS[hw_pin]
                else:
                    print("Warning: unknown input hw_pin:", logical_name, hw_pin)

        if io_mapping and 'outputs' in io_mapping:
            for logical_name, entry in io_mapping['outputs'].items():
                card_number, hw_pin = _entry_to_hw_pin(entry)
                if card_number != 0:
                    print("Warning: ignoring output on unsupported card_number:", logical_name, card_number)
                    continue
                if hw_pin in self._PHYSICAL_PINS:
                    pin_obj = self._PHYSICAL_PINS[hw_pin]
                    pin_obj.off() # Default to OFF state
                    self._logical_to_physical[logical_name] = pin_obj
                    self._outputs[logical_name] = pin_obj
                else:
                    print("Warning: unknown output hw_pin:", logical_name, hw_pin)

        print("HAL initialized with outputs:", list(self._outputs.keys()))

    def set_output(self, logical_name, value_str):
        """
        Sets the state of a logical output, abstracting away the pin.
        """
        if logical_name in self._outputs:
            pin_obj = self._outputs[logical_name]
            if value_str.upper() == "ON":
                pin_obj.value(1)
                return True
            elif value_str.upper() == "OFF":
                pin_obj.value(0)
                return True
        return False
    
        
    def get_all_states(self):
        """
        Returns a dictionary of all mapped I/O states, using logical names as keys.
        """
        payload = {}
        for logical_name, pin_obj in self._logical_to_physical.items():
            payload[logical_name] = pin_obj.value()
        return payload
    
    # --- 2. METHODS FOR DIRECT HARDWARE ACCESS ---

    def init_i2c(self, freq=400000):
        """
        Initializes the I2C bus for the OLED display and returns the I2C object.
        """
        scl = Pin(self._I2C_SCL_PIN)
        sda = Pin(self._I2C_SDA_PIN)
        # Use I2C bus 1 as per original code
        self.i2c_bus = I2C(1, scl=scl, sda=sda, freq=freq)
        print(f"I2C bus initialized on SCL={self._I2C_SCL_PIN}, SDA={self._I2C_SDA_PIN}")
        return self.i2c_bus

    def init_rs485(self, baudrate=9600, uart_id=1):
        """
        Initializes the RS-485 bus and returns the UART object and flow control pin.
        """
        self.rs485_fc_pin = Pin(self._RS485_FC_PIN, Pin.OUT)
        self.rs485_fc_pin.value(0)  # Default to RX mode
        
        self.rs485_bus = UART(uart_id, baudrate=baudrate,
                              tx=self._RS485_TX_PIN, rx=self._RS485_RX_PIN)
        print(f"RS-485 bus (UART{uart_id}) initialized at {baudrate} baud.")
        return self.rs485_bus, self.rs485_fc_pin

    def read_buttons(self):
        """
        Reads the analog value from the ADC connected to the physical buttons.
        """
        # Initialize ADC on demand
        adc = ADC(Pin(self._BUTTONS_ADC_PIN))
        # Set attenuation to read up to 3.3V
        adc.atten(ADC.ATTN_11DB)
        return adc.read()
