from machine import Pin, I2C, UART, ADC  # type: ignore
from lib.drivers.base import IOModuleBase


class NorviAE01T(IOModuleBase):
    """
    Driver for the NORVI IIOT-AE01-T (all-transistor variant).

    Provides:
      - 8 digital inputs      (DI0-DI7)
      - 8 transistor outputs   (T0-T7)

    The 6 GPIOs that are relays on the AE01-R are transistor outputs
    here (T2-T7), in addition to the original T0-T1.
    """

    AVAILABLE_PINS = {
        "DI0": {"type": "input"},
        "DI1": {"type": "input"},
        "DI2": {"type": "input"},
        "DI3": {"type": "input"},
        "DI4": {"type": "input"},
        "DI5": {"type": "input"},
        "DI6": {"type": "input"},
        "DI7": {"type": "input"},
        "T0": {"type": "output"},
        "T1": {"type": "output"},
        "T2": {"type": "output"},
        "T3": {"type": "output"},
        "T4": {"type": "output"},
        "T5": {"type": "output"},
        "T6": {"type": "output"},
        "T7": {"type": "output"},
    }

    _PIN_MAP = {
        "DI0": Pin(18, Pin.IN),
        "DI1": Pin(39, Pin.IN),
        "DI2": Pin(34, Pin.IN),
        "DI3": Pin(35, Pin.IN),
        "DI4": Pin(19, Pin.IN),
        "DI5": Pin(21, Pin.IN),
        "DI6": Pin(22, Pin.IN),
        "DI7": Pin(23, Pin.IN),
        "T0": Pin(26, Pin.OUT),
        "T1": Pin(27, Pin.OUT),
        "T2": Pin(14, Pin.OUT),
        "T3": Pin(12, Pin.OUT),
        "T4": Pin(13, Pin.OUT),
        "T5": Pin(15, Pin.OUT),
        "T6": Pin(2, Pin.OUT),
        "T7": Pin(33, Pin.OUT),
    }

    # Peripheral pin numbers
    RS485_TX_PIN = 1
    RS485_RX_PIN = 3
    RS485_FC_PIN = 4
    I2C_SDA_PIN = 16
    I2C_SCL_PIN = 17
    BUTTONS_ADC_PIN = 32

    def __init__(self):
        # All outputs OFF at startup
        for name, info in self.AVAILABLE_PINS.items():
            if info["type"] == "output":
                self._PIN_MAP[name].off()

    # -- IOModuleBase interface --

    def get_pin_value(self, hw_pin):
        return self._PIN_MAP[hw_pin].value()

    def set_pin_value(self, hw_pin, value):
        if self.AVAILABLE_PINS.get(hw_pin, {}).get("type") != "output":
            return False
        self._PIN_MAP[hw_pin].value(value)
        return True

    def get_all_states(self):
        return {name: self._PIN_MAP[name].value() for name in self._PIN_MAP}

    # -- Peripheral helpers (optional, used by HAL if needed) --

    def init_i2c(self, freq=400000):
        scl = Pin(self.I2C_SCL_PIN)
        sda = Pin(self.I2C_SDA_PIN)
        self.i2c_bus = I2C(1, scl=scl, sda=sda, freq=freq)
        return self.i2c_bus

    def init_rs485(self, baudrate=9600, uart_id=1):
        self.rs485_fc_pin = Pin(self.RS485_FC_PIN, Pin.OUT)
        self.rs485_fc_pin.value(0)  # Default to RX mode
        self.rs485_bus = UART(
            uart_id, baudrate=baudrate, tx=self.RS485_TX_PIN, rx=self.RS485_RX_PIN
        )
        return self.rs485_bus, self.rs485_fc_pin

    def read_buttons(self):
        adc = ADC(Pin(self.BUTTONS_ADC_PIN))
        adc.atten(ADC.ATTN_11DB)
        return adc.read()
