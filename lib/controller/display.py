from machine import Pin, I2C, UART
from lib.constants import LOGO

import lib.modules.ssd1306 as ssd1306
import framebuf
import time


# ssd1306 docs: https://docs.micropython.org/en/latest/esp8266/tutorial/ssd1306.html
class DisplayController:
    def __init__(self, width=128, height=64, sda_pin=16, scl_pin=17, i2c_addr=0x3C):
        self.width = width
        self.height = height
        self.sda_pin = sda_pin
        self.scl_pin = scl_pin
        self.i2c_addr = i2c_addr
        i2c = I2C(sda=Pin(self.sda_pin), scl=Pin(self.scl_pin))
        self.display = ssd1306.SSD1306_I2C(self.width, self.height, i2c)

    def clear(self):
        if self.display:
            self.display.fill(0)
            self.display.show()

    def _wrap(self, text, chars_per_line):
        lines = []
        for paragraph in text.split("\n"):  # respect explicit newlines
            cur = ""
            for word in paragraph.split(" "):
                # a single word longer than the line gets hard-split
                while len(word) > chars_per_line:
                    if cur:
                        lines.append(cur)
                        cur = ""
                    lines.append(word[:chars_per_line])
                    word = word[chars_per_line:]
                if not cur:
                    cur = word
                elif len(cur) + 1 + len(word) <= chars_per_line:
                    cur += " " + word
                else:
                    lines.append(cur)
                    cur = word
            lines.append(cur)
        return lines

    def show_text(self, text, x=0, y=0, wrap=True):
        if not self.display:
            return
        self.clear()
        self.display.invert(0)

        if wrap:
            chars_per_line = (self.width - x) // 8  # 8px per char -> 16
            max_lines = (self.height - y) // 8  # 8px per line -> 8
            for i, line in enumerate(self._wrap(text, chars_per_line)[:max_lines]):
                self.display.text(line, x, y + i * 8)
        else:
            self.display.text(text, x, y)
        self.display.show()

    def show_logo(self):
        if self.display:
            fb = framebuf.FrameBuffer(LOGO, self.width, self.height, framebuf.MONO_HLSB)
            self.clear()
            self.display.invert(0)
            self.display.blit(fb, 0, 0)
            self.display.show()
