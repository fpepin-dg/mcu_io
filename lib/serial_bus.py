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
        msg = {"msg_type": msg_type, "payload": payload}
        sys.stdout.write(ujson.dumps(msg) + "\n")

    def check_for_command(self):
        """
        Performs a non-blocking check for an incoming command on stdin.
        Expected command format: "CMD:<LOGICAL_NAME>:<VALUE>"
        Returns a tuple (logical_name, value) or (None, None).

        Robust against UART glitches: a single corrupted byte (or a partial
        multi-byte UTF-8 sequence from a short read) would otherwise raise
        UnicodeError out of sys.stdin.readline() and kill the current loop
        iteration. We just drop the bad line and let the host retry.
        """
        if not self.poll.poll(0):
            return (None, None)

        try:
            line = sys.stdin.readline()
        except UnicodeError:
            # Garbled bytes on the link. The next \n re-syncs the stream;
            # drop this fragment and move on.
            return (None, None)

        if line is None:
            return (None, None)

        line = line.strip()
        if not line:
            return (None, None)

        parts = line.split(":", 2)
        if len(parts) == 3 and parts[0] == "CMD":
            return (parts[1], parts[2])

        return (None, None)
