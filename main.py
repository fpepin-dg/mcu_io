from lib.controller.rs485 import RS485Controller
from lib.controller.modbus import ModbusController
from lib.controller.display import DisplayController

import json

config = None

try:
    with open("config.json", "r") as f:
        config = json.load(f)
except Exception as e:
    print("No config file found. Running in RS485 mode only.")

if config:
    modbusController = ModbusController(registers=config["REGISTER"])

rs485Controller = RS485Controller()
oledController = DisplayController()
oledController.show_logo()

while True:
    try:
        oledController.show_logo()
        if config:
            modbusController.init()
            modbusController.loop(oledController)

        rs485Controller.init()
        rs485Controller.loop(oledController)
    except Exception as e:
        oledController.show_error(e)
