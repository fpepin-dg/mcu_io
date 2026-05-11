class IOModuleBase:
    """
    Abstract base class for all I/O module drivers.

    Every driver (PLC or expansion) must implement these methods so the
    HAL can treat them uniformly.

    Class attribute AVAILABLE_PINS must be a dict mapping hw_pin names
    to their metadata, e.g.:
        {"T0": {"type": "output"}, "DI0": {"type": "input"}}
    """

    AVAILABLE_PINS = {}

    def get_pin_value(self, hw_pin):
        """Read the current value of a hardware pin. Returns 0 or 1."""
        raise NotImplementedError

    def set_pin_value(self, hw_pin, value):
        """
        Set a hardware pin to the given value (0 or 1).
        Returns True on success, False if the pin is read-only or unknown.
        """
        raise NotImplementedError

    def get_all_states(self):
        """
        Return a dict of {hw_pin: value} for every pin declared in
        AVAILABLE_PINS.
        """
        raise NotImplementedError


class AnalogOutputModuleBase(IOModuleBase):
    """
    Base class for analog-output expansion modules.

    Channel values are integers (e.g. 0..4095 for 12-bit DACs) instead
    of binary 0/1. Subclasses define DAC_RESOLUTION_BITS and the value
    range expected by set_pin_value/get_pin_value.
    """

    DAC_RESOLUTION_BITS = 12

    def get_status(self):
        """Return a dict describing fault/diagnostic flags."""
        raise NotImplementedError
