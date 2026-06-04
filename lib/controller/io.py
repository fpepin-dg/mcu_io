from lib.drivers.expansion.norvi_ex_q4 import EXQ4


class IOController:
    def __init__(self, board, cards_cfg, address_map):
        self._addr = {int(k): v for k, v in address_map.items()}
        self._cards = {0: board}  # card 0 = main board
        for cid, cfg in (cards_cfg or {}).items():
            if int(cid) != 0:
                self._cards[int(cid)] = self._make(cfg, board.i2c)

    def _make(self, cfg, i2c):
        t = cfg.get("type")
        if t == "norvi_ex_q4":
            return EXQ4(i2c, cfg["i2c_addr"])
        raise ValueError("Unknown expansion: " + str(t))

    def _resolve(self, address):
        m = self._addr.get(address)
        if m is None:
            return None
        card = self._cards.get(m["card"])
        return (card, m["pin"]) if card else None

    def write(self, address, val):
        r = self._resolve(address)
        if r:
            r[0].set_value(r[1], val)

    def read(self, address):
        r = self._resolve(address)
        return r[0].get_value(r[1]) if r else None

    def is_mapped(self, address):
        return address in self._addr

    def read_all(self):
        """Every card's pins, namespaced by card id: {'0:T5': 1, '1:Q1': 0, ...}."""
        out = {}
        for cid, card in self._cards.items():
            try:
                pins = card.get_all_values()
            except Exception:
                continue  # a dead I2C card shouldn't kill the dump
            for name, val in pins.items():
                out["{}:{}".format(cid, name)] = val
        return out

    def mapping_for(self, address):
        return self._addr.get(address)
