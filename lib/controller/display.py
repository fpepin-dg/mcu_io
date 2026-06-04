from lib.constants import LOGO

import lib.modules.ssd1306 as ssd1306
import framebuf


# ssd1306 docs: https://docs.micropython.org/en/latest/esp8266/tutorial/ssd1306.html
class SSD1306Display:
    def __init__(self, width, height, i2c, i2c_addr):
        self.width = width
        self.height = height
        self.i2c_addr = i2c_addr
        self.display = ssd1306.SSD1306_I2C(
            self.width, self.height, i2c, addr=self.i2c_addr
        )
        self._current = None

    def clear(self):
        if self._current == ("clear",):
            return
        self.display.fill(0)
        self.display.show()
        self._current = ("clear",)

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
        token = ("text", text, x, y, wrap)
        if self._current == token:
            return
        self.display.fill(0)  # inline clear; don't call self.clear()
        self.display.invert(0)
        if wrap:
            chars_per_line = (self.width - x) // 8
            max_lines = (self.height - y) // 8
            for i, line in enumerate(self._wrap(text, chars_per_line)[:max_lines]):
                self.display.text(line, x, y + i * 8)
        else:
            self.display.text(text, x, y)
        self.display.show()
        self._current = token

    def show_error(self, e):
        self.show_text("ERROR: " + str(e))

    def show_logo(self):
        if self._current == ("logo",):
            return
        fb = framebuf.FrameBuffer(LOGO, self.width, self.height, framebuf.MONO_HLSB)
        self.display.fill(0)
        self.display.invert(0)
        self.display.blit(fb, 0, 0)
        self.display.show()
        self._current = ("logo",)


class NullDisplay:
    # Pass to board with no display
    # self._display = NullDisplay()
    def show_text(self, *a, **k):
        pass

    def show_logo(self, *a, **k):
        pass

    def show_error(self, *a, **k):
        pass

    def clear(self, *a, **k):
        pass
