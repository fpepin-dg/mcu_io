from machine import UART, reset
from lib.constants import *

import time
import os


class RS485Controller:
    def __init__(
        self,
        board,
        baudrate,
        bits=BITS,
        parity=PARITY,
        stop=STOP,
        txbuf=4096,
        rxbuf=4096,
    ):
        self._board = board
        self._baudrate = baudrate
        self._bits = bits
        self._parity = parity
        self._stop = stop
        self._txbuf = txbuf
        self._rxbuf = rxbuf

        self._local_rx_buf = bytearray()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def init(self):
        self._uart = UART(
            self._board.rs485["uart_id"],
            baudrate=self._baudrate,
            bits=self._bits,
            parity=self._parity,
            stop=self._stop,
            tx=self._board.rs485["tx"],
            rx=self._board.rs485["rx"],
            txbuf=self._txbuf,
            rxbuf=self._rxbuf,
        )
        time.sleep_ms(50)
        self._send("UPLOAD_READY")

    def deinit(self):
        time.sleep_us(50)
        self._local_rx_buf = self._local_rx_buf[len(self._local_rx_buf) :]
        self._uart.deinit()

    def loop(self, board) -> None:
        while True:
            try:
                line = self._readline()
                if line == "RUN":
                    self._send("RUNNING")
                    self.deinit()
                    return
                elif line:
                    self._handle(line)
                else:
                    time.sleep_ms(10)
            except Exception as e:
                try:
                    board.display.show_text("LOOP_ERROR:" + str(e))
                    self._send("LOOP_ERROR:" + str(e))
                except:
                    pass
                time.sleep_ms(100)  # avoid tight error loops

    # ------------------------------------------------------------------
    # Private API
    # ------------------------------------------------------------------

    def _handle(self, line: str) -> None:
        if line == "PING":
            self._send("PONG")
        elif line == "LS":
            self._cmd_ls()
        elif line.startswith("LS:"):
            self._cmd_ls(line[3:])
        elif line.startswith("RM:"):
            self._cmd_rm(line[3:])
        elif line.startswith("CAT:"):
            self._cmd_cat(line[4:])
        elif line.startswith("CP:"):
            rest = line[3:]
            # Format: CP:<filename>:<size>
            if ":" not in rest:
                self._send("ERROR:USAGE")
            else:
                filename, _, size_str = rest.rpartition(":")
            self._cmd_cp(filename, size_str)
        elif line == "RESET":
            self._cmd_reset()
        else:
            self._send("UNKNOWN:" + line)

    # ── Bus control ───────────────────────────────────────────────────
    def _send(self, msg) -> None:
        data = (msg + "\n").encode()
        self._board.rs485["ctrl_pin"].value(1)
        time.sleep_us(200)
        self._uart.write(data)
        self._uart.flush()
        self._board.rs485["ctrl_pin"].value(0)

    def _readline(self) -> str | None:
        read = self._uart.read()
        if read:
            self._local_rx_buf.extend(read)

        i = self._local_rx_buf.find(b"\n")
        if i != -1:
            line = bytes(self._local_rx_buf[:i]).decode("utf-8", "ignore").strip()
            self._local_rx_buf = self._local_rx_buf[i + 1 :]
            return line
        return None

    def _read_exact(self, n, timeout_ms=5000):
        buf = bytearray()
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while len(buf) < n:
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                return None
            avail = self._uart.any()
            if avail:
                chunk = self._uart.read(min(avail, n - len(buf)))
                if chunk:
                    buf.extend(chunk)
            else:
                time.sleep_us(100)
        return bytes(buf)

    # ── Upload state machine ──────────────────────────────────────────
    def _ensure_parents(self, filename):
        parts = filename.split("/")
        if len(parts) <= 1:
            return
        path = ""
        for part in parts[:-1]:
            if not part:
                continue
            path = path + "/" + part if path else part
            try:
                os.mkdir(path)
            except OSError:
                pass

    def _cmd_cp(self, filename, size_str):
        try:
            size = int(size_str)
        except ValueError:
            self._send("ERROR:BAD_SIZE")
            return

        try:
            self._ensure_parents(filename)
            tmp = filename + ".new"
            fp = open(tmp, "wb")
        except Exception as e:
            self._send("ERROR:" + str(e))
            return

        self._send("READY")

        # Stream-read `size` bytes into the file
        remaining = size
        deadline = time.ticks_add(time.ticks_ms(), 30000)  # 30s total
        READ_CHUNK = 1024

        while remaining > 0:
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                fp.close()
                try:
                    os.remove(tmp)
                except:
                    pass
                self._send("ERROR:TIMEOUT")
                return

            want = min(READ_CHUNK, remaining)
            avail = self._uart.any()
            if avail:
                data = self._uart.read(min(avail, want))
                if data:
                    fp.write(data)
                    remaining -= len(data)
            else:
                time.sleep_us(100)

        fp.close()
        try:
            os.remove(filename)
        except OSError:
            pass
        os.rename(tmp, filename)
        self._send("OK:" + str(size))

    # ── Runtime commands ──────────────────────────────────────────────
    def _cmd_ls(self, path=""):
        try:
            entries = os.listdir(path) if path else os.listdir()
            self._send("LS:" + ",".join(entries))
        except Exception as e:
            self._send("LS:ERROR:" + str(e))

    def _cmd_rm(self, path):
        path = path.rstrip("/")
        try:
            mode = os.stat(path)[0]
            if mode & 0x4000:  # S_IFDIR — it's a directory
                self._rmtree(path)
            else:
                os.remove(path)
            self._send("RM:OK")
        except Exception as e:
            self._send("RM:ERROR:" + str(e))

    def _rmtree(self, path):
        for entry in os.listdir(path):
            full = path + "/" + entry
            if os.stat(full)[0] & 0x4000:
                self._rmtree(full)
            else:
                os.remove(full)
        os.rmdir(path)

    def _cmd_cat(self, filename):
        """
        Send file as raw binary.
        Protocol: CAT:<size>\n then exactly <size> raw bytes.
        """
        try:
            size = os.stat(filename)[6]
            self._send("CAT:" + str(size))
            self._board.rs485["ctrl_pin"].value(1)
            time.sleep_us(200)
            with open(filename, "rb") as f:
                while True:
                    chunk = f.read(2048)
                    if not chunk:
                        break
                    self._uart.write(chunk)
                    self._uart.flush()
            self._board.rs485["ctrl_pin"].value(0)
        except Exception as e:
            self._send("ERROR:" + str(e))

    def _cmd_reset(self):
        self._send("RESETTING")
        time.sleep_ms(50)

        reset()
