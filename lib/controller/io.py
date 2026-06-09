from lib.drivers.expansion.norvi_ex_q4 import EXQ4
from lib.drivers.expansion.norvi_ex_anq_04 import ANQ04
from lib.drivers.expansion.norvi_ex_anv01 import ANV01


class IOController:
    def __init__(self, board, cards_cfg, address_map):
        self._addr = {
            rtype: {int(k): v for k, v in entries.items()}
            for rtype, entries in address_map.items()
        }
        self._cards = {0: board}
        for cid, cfg in (cards_cfg or {}).items():
            if int(cid) != 0:
                self._cards[int(cid)] = self._make(cfg, board.i2c)

    def _make(self, cfg, i2c):
        t = cfg.get("type")
        if t == "norvi_ex_q4":
            return EXQ4(i2c, cfg["i2c_addr"])
        elif t == "norvi_ex_anq_04":
            return ANQ04(i2c, cfg["i2c_addr"], modes=cfg["modes"])
        elif t == "norvi_ex_anv01":
            return ANV01(
                i2c,
                cfg["i2c_addr"],
                full_scale_counts=cfg.get("full_scale_counts", None),
            )
        raise ValueError("Unknown expansion: " + str(t))

    def _resolve(self, reg_type, address):
        m = self._addr.get(reg_type, {}).get(address)
        if m is None:
            return None
        card = self._cards.get(m["card"])
        return (card, m["pin"]) if card else None

    def write(self, reg_type, address, value):
        r = self._resolve(reg_type, address)
        if r:
            r[0].set_value(r[1], value)

    def read(self, reg_type, address):
        r = self._resolve(reg_type, address)
        return r[0].get_value(r[1]) if r else None

    def is_mapped(self, reg_type, address):
        return address in self._addr.get(reg_type, {})

    def read_all(self):
        """One read per card, nested by card id:
        {0: {"T5": 0, ...}, 1: {"AO.0": 4095, ...}}"""
        out = {}
        for cid, card in self._cards.items():
            try:
                out[cid] = card.get_all_values()  # driver batches its own read
            except Exception as e:
                board = self._cards[0]
                if board.has_display:
                    board.display.show_error(e)
                out[cid] = {}  # dead card -> empty, not missing
        return out

    def mapping_for(self, reg_type, address):
        return self._addr.get(reg_type, {}).get(address)
