import utime as time
import ujson
from lib.serial_bus import SerialBusController
from lib.norvi_ae01_r import NorviIIOT_AE01_R

def load_config(path="config.json"):
    """Loads configuration from a JSON file."""
    try:
        with open(path, 'r') as f:
            return ujson.load(f)
    except (OSError, ValueError):
        print(f"Warning: {path} not found or corrupt. Using defaults.")
        return {
            "system": {
                "io_cards": [],
                "plc": {
                    "card_number": 0,
                    "device_id": "unknown-device",
                },
                "telemetry_frequency_ms": 1000,
            },
            "io_mapping": {"inputs": {}, "outputs": {}}
        }

# --- Initialization ---
print("Application starting...")
config = load_config()
print(config)

telemetry_freq_ms = config.get("system", {}).get("telemetry_frequency_ms", 1000)
system_cfg = config.get("system", {})
plc_cfg = system_cfg.get("plc", {})

# Backwards-compatible: support old `system.device_id` and new `system.plc.device_id`.
device_id = plc_cfg.get("device_id") or system_cfg.get("device_id", "unknown-device")
print(f"Device '{device_id}', Telemetry: {telemetry_freq_ms}ms")
# Initialize components with config data
hal = NorviIIOT_AE01_R(config.get("io_mapping", {}))
print(hal._outputs, '\n')
print(hal._logical_to_physical, '\n')

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
        print(f"Received command: '{command}' -> '{value}'")
        
        # The giant if/elif block is replaced by this single, abstracted call
        if not hal.set_output(command, value):
            print(f"Warning: Unknown command/component '{command}'.")
            bus.send_message(msg_type="CMD_ERROR", payload={"command": command})

    time.sleep_ms(10)
