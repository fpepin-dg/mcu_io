import utime as time
import ujson
from lib.serial_bus import SerialBusController
from lib.hal import HAL


def load_config(path="config.json"):
    """Loads configuration from a JSON file."""
    try:
        with open(path, 'r') as f:
            return ujson.load(f)
    except (OSError, ValueError):
        print("Warning: %s not found or corrupt. Using defaults." % path)
        return {
            "system": {
                "io_cards": [],
                "plc": {
                    "card_number": 0,
                    "type": "norvi_ae01_r",
                    "device_id": "unknown-device",
                },
                "telemetry_frequency_ms": 1000,
            },
            "io_mapping": {"inputs": {}, "outputs": {}}
        }


# --- Initialization ---
print("Application starting...")
config = load_config()

system_cfg = config.get("system", {})
plc_cfg = system_cfg.get("plc", {})
telemetry_freq_ms = system_cfg.get("telemetry_frequency_ms", 1000)

# Backwards-compatible: support old system.device_id and new system.plc.device_id.
device_id = plc_cfg.get("device_id") or system_cfg.get("device_id", "unknown-device")
print("Device '%s', Telemetry: %dms" % (device_id, telemetry_freq_ms))

# The HAL reads the full config, instantiates the correct PLC driver and
# any expansion modules, and builds the logical-name mappings automatically.
hal = HAL(config)

bus = SerialBusController()

# --- Main Application Loop ---
last_telemetry_tick = time.ticks_ms()
print("Entering main loop...")
while True:
    now = time.ticks_ms()
    
    # 1. Periodically send telemetry
    if time.ticks_diff(now, last_telemetry_tick) >= telemetry_freq_ms:
        current_states = hal.get_all_states()
        bus.send_message(msg_type="ED", payload=current_states)
        last_telemetry_tick = now

    # 2. Check for incoming commands
    command, value = bus.check_for_command()
    if command:
        print("Received command: '%s' -> '%s'" % (command, value))

        # The HAL routes the command to the correct driver (local or expansion)
        if not hal.set_output(command, value):
            print("Warning: Unknown command/component '%s'." % command)
            bus.send_message(msg_type="CMD_ERROR", payload={"command": command})

    time.sleep_ms(10)
