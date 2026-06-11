FREQ = 400000
POLL_INTERVAL_MS = 1000
BAUDRATE = 115200
TX_PIN_NUMBER = 1
RX_PIN_NUMBER = 3
FC_PIN_NUMBER = 4
UART_ID = 1
BITS = 8
PARITY = None
STOP = 1

# for PGA = 000 (±6.144V) 16581
# for PGA = 001 (±4.096V) 24868
ANV01_FSC = 24868

MODE_RUN = 0
MODE_UPLOAD = 1

LOGO = bytearray(
    bytes.fromhex(
        (
            "000000001fffffffffffffffff000000000000003fffffffffffffffff000000000000003ffffffffffffffffe000000"
            "000000003ffffffffffffffffe000000000000003ffffffffffffffffe000000000000003ffffffffffffffffe000000"
            "000000003ffffffffffffffffe000000000000007ffffffffffffffffc000000000000007ffffffffffffffffc000000"
            "000000007ffffffffffffffffc000000000000007ffffffffffffffffc000000000000007ffffffffffffffffc000000"
            "00000000fffffffffffffffffc00000000000000fffffffffffffffff800000000000000fffffffffffffffff8000000"
            "00000000ffffe003fffffffff800000000000000ffffe000fffffffff800000000000000ffffe000fffffffff8000000"
            "00000001ffffe0007ffffffff800000000000001ffffe1f07ffffffff000000000000001ffffc1f07ffffffff0000000"
            "00000001ffffc1f07ffffffff000000000000001ffffc1f07ffffffff000000000000003ffffc3f07ffffffff0000000"
            "00000003ffff83f07fffffffe000000000000003ffff83f07fffffffe000000000000003ffff83f0fc03ffffe0000000"
            "00000003ffff83e0f800ffffe000000000000003ffff87e0f000ffffe000000000000007ffff07e0e060ffffe0000000"
            "00000007ffff07e1c1e0ffffc000000000000007ffff07c1c1f0ffffc000000000000007ffff07c383f0ffffc0000000"
            "00000007ffff0f8383ffffffc00000000000000ffffe000783ffffffc00000000000000ffffe000f07ffffff80000000"
            "0000000ffffe001f07ffffff800000000000000ffffe007f0700ffff800000000000000fffffffff0601ffff80000000"
            "0000000ffffffffe0e01ffff800000000000001ffffffe7e0fc1ffff800000000000001ffffffc3e0fc1ffff00000000"
            "0000001ffffffdfe0fc3ffff000000000000001ffffffcde0f83ffff000000000000001ffffff89e0f83ffff00000000"
            "0000003ffffff23e0f03ffff000000000000003fffffe67e0003ffff000000000000003fffffe03f0007fffe00000000"
            "0000003ffffff1bf0047fffe000000000000003fffffffff81c7fffe000000000000003ffffffffffffffffe00000000"
            "0000007ffffffffffffffffe000000000000007ffffffffffffffffc000000000000007ffffffffffffffffc00000000"
            "0000007ffffffffffffffffc000000000000007ffffffffffffffffc000000000000007ffffffffffffffffc00000000"
            "000000fffffffffffffffffc00000000000000fffffffffffffffff800000000000000fffffffffffffffff800000000"
            "000000fffffffffffffffff800000000000000fffffffffffffffff800000000000001fffffffffffffffff800000000"
            "000001fffffffffffffffff000000000"
        )
    )
)
