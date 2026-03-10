import sys
import ujson
import uselect

class SerialBusController:
    """
    Manages the serial bus communication (stdin/stdout) for sending
    JSON messages and receiving text-based commands.
    """
    def __init__(self):
        self.poll = uselect.poll()
        self.poll.register(sys.stdin, uselect.POLLIN)

    def send_message(self, msg_type, payload):
        """
        Constructs a standard message and sends it over stdout as a
        JSON string on a single line.
        """
        msg = {
            "msg_type": msg_type,
            "payload": payload
        }
        sys.stdout.write(ujson.dumps(msg) + "\n")

    def check_for_command(self):
        """
        Performs a non-blocking check for an incoming command on stdin.
        Expected command format: "CMD:<LOGICAL_NAME>:<VALUE>"
        Returns a tuple (logical_name, value) or (None, None).
        """
        if self.poll.poll(0):
            line = sys.stdin.readline().strip()
            if not line:
                return (None, None)
                
            parts = line.split(":")
            if len(parts) == 3 and parts[0] == "CMD":
                return (parts[1], parts[2])
        
        return (None, None)
