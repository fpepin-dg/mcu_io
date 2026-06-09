class RegisterCallbacks:
    """Holds the get/set callbacks applied to every register of each type."""

    def __init__(self, io):
        self._io = io

    # ---- COILS (read/write) ----
    def coil_get(self, reg_type, address, val):
        pass  # Handle by _refresh in modbus loop

    def coil_set(self, reg_type, address, val):
        bit = val[0] if isinstance(val, (list, tuple)) else val
        self._io.write(reg_type, address, bool(bit))

    # ---- HREGS (read/write) ----
    def hreg_get(self, reg_type, address, val):
        pass

    def hreg_set(self, reg_type, address, val):
        pct = val[0] if isinstance(val, (list, tuple)) else val
        self._io.write(reg_type, address, pct)

    # ---- ISTS (read-only) ----
    def ist_get(self, reg_type, address, val):
        pass

    # ---- IREGS (read-only) ----
    def ireg_get(self, reg_type, address, val):
        pass

    def as_map(self) -> dict:
        return {
            "COILS": {"on_get_cb": self.coil_get, "on_set_cb": self.coil_set},
            "HREGS": {"on_get_cb": self.hreg_get, "on_set_cb": self.hreg_set},
            "ISTS": {"on_get_cb": self.ist_get},
            "IREGS": {"on_get_cb": self.ireg_get},
        }
