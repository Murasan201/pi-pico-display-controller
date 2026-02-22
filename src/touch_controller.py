from machine import Pin, SPI



class TouchController:
    """Simple XPT2046 wrapper that reads raw touch coordinates."""

    def __init__(self, sck, mosi, miso, cs, irq=None, width=240, height=320):
        self.width = width
        self.height = height
        try:
            self.spi = SPI(1, baudrate=500_000, polarity=0, phase=0, sck=sck, mosi=mosi, miso=miso)
        except Exception:
            self.spi = None
        if self.spi:
            self.cs = Pin(cs, Pin.OUT) if isinstance(cs, int) else cs
            self.cs.value(1)
            self.irq = Pin(irq, Pin.IN) if irq is not None else None
            self._buf = bytearray(3)
        else:
            self.cs = None
            self.irq = None

    def _read_raw(self, command):
        if not self.spi or not self.cs:
            return None
        self.cs.value(0)
        self._buf[0] = command
        self._buf[1] = 0
        self._buf[2] = 0
        self.spi.write_readinto(self._buf, self._buf)
        self.cs.value(1)
        value = ((self._buf[1] << 8) | self._buf[2]) >> 3
        return value

    def get_touch(self):
        if not self.spi:
            return None
        if self.irq and self.irq.value():
            return None
        x_raw = self._read_raw(0xD0)
        y_raw = self._read_raw(0x90)
        if x_raw is None or y_raw is None:
            return None
        x = (x_raw * self.width) // 4096
        y = (y_raw * self.height) // 4096
        return x, self.height - y
