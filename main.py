import utime as time
import ujson
from lib.serial_bus import SerialBusController
from lib.hal import HAL


def load_config(path="config.json"):
    """Loads configuration from a JSON file."""
    try:
        with open(path, "r") as f:
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
            "io_mapping": {"inputs": {}, "outputs": {}},
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
# After this many consecutive I/O errors we assume the I2C bus is hung
# (a slave is stretching SCL or holding SDA low) and try to recover it.
# A single isolated glitch usually clears on its own, so we don't recover
# on the very first error.
RECOVERY_ERROR_THRESHOLD = 2
# Don't try to recover more often than this; gives the bus time to settle
# and avoids spamming the unstick procedure if recovery itself can't help.
RECOVERY_BACKOFF_MS = 1000

last_telemetry_tick = time.ticks_ms()
last_recovery_tick = time.ticks_ms()
consecutive_io_errors = 0
print("Entering main loop...")
while True:
    try:
        now = time.ticks_ms()

        # 1. Periodically send telemetry
        if time.ticks_diff(now, last_telemetry_tick) >= telemetry_freq_ms:
            try:
                current_states = hal.get_all_states()
                bus.send_message(msg_type="ED", payload=current_states)
                consecutive_io_errors = 0
            except OSError as exc:
                consecutive_io_errors += 1
                print("WARN: telemetry I/O error, skipping cycle:", exc)
                # Persistent OSErrors -> bus is almost certainly hung.
                # Try to free SCL/SDA and re-init the peripheral.
                if (
                    consecutive_io_errors >= RECOVERY_ERROR_THRESHOLD
                    and time.ticks_diff(now, last_recovery_tick)
                    >= RECOVERY_BACKOFF_MS
                ):
                    try:
                        hal.recover_i2c()
                    except Exception as rexc:
                        print("WARN: I2C recovery failed:", rexc)
                    last_recovery_tick = time.ticks_ms()
            last_telemetry_tick = now

        # 2. Check for incoming commands
        command, value = bus.check_for_command()
        if command:
            print("Received command: '%s' -> '%s'" % (command, value))
            try:
                ok = hal.set_output(command, value)
                consecutive_io_errors = 0
            except OSError as exc:
                consecutive_io_errors += 1
                print("WARN: command I/O error:", exc)
                ok = False
            if not ok:
                print("Warning: Unknown command/component '%s'." % command)
                bus.send_message(msg_type="CMD_ERROR", payload={"command": command})

        time.sleep_ms(10)

    except Exception as exc:
        # Last-resort guard: never let the main loop die. Print and keep going.
        import sys

        print("ERROR in main loop:", exc)
        sys.print_exception(exc)
        time.sleep_ms(100)
