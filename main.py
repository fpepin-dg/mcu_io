from lib.drivers.board.boards import make_board, DEFAULT_BOARD
from lib.controller.rs485 import RS485Controller
from lib.controller.modbus import ModbusController
from lib.callbacks import RegisterCallbacks
from lib.controller.io import IOController
from lib.constants import *

import json
import time

config = None

try:
    with open("config.json", "r") as f:
        config = json.load(f)
except Exception:
    pass

settings = (config or {}).get("SETTINGS", {})

freq = settings.get("I2C_FREQ", FREQ)
board_type = config["CARD"]["0"]["type"] if config else DEFAULT_BOARD
board = make_board(board_type, freq)

baudrate = settings.get("BAUDRATE", BAUDRATE)
modbusController = None
if config:
    io = IOController(board, config["CARD"], config["ADDRESS_MAP"])
    modbusController = ModbusController(
        board=board,
        io=io,
        registers=config.get("REGISTERS", {}),
        callbacks=RegisterCallbacks(io=io).as_map(),
        addr=settings.get("UART_ADDR", 1),
        baudrate=baudrate,
        poll_interval_ms=settings.get("POLL_INTERVAL_MS", POLL_INTERVAL_MS),
    )

rs485Controller = RS485Controller(
    board=board,
    baudrate=baudrate,
)
board.display.show_logo()
while True:
    try:
        if modbusController:
            modbusController.init()
            modbusController.loop(board)

        time.sleep_us(50)
        rs485Controller.init()
        rs485Controller.loop(board)

    except Exception as e:
        board.display.show_error(e)
