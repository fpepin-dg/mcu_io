from lib.drivers.board.norvi_ae01_t import AE01T

BOARDS = {
    "norvi_iiot_ae01_t": AE01T,
}

DEFAULT_BOARD = "norvi_iiot_ae01_t"


def make_board(board_type, freq):
    cls = BOARDS.get(board_type)
    if cls is None:
        raise ValueError("Unknown board type: " + str(board_type))
    return cls(freq)
