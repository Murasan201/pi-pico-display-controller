from machine import Pin, SPI
from touch_controller import TouchController
import utime
import ubinascii
import os

from st7789 import ST7789, color565, FONT_Default
from jpegdec import JPEG


WEATHER_COLOR_MAP = {
    "Sunny": (255, 205, 60),
    "Clear": (255, 205, 60),
    "Cloudy": (180, 180, 180),
    "Rain": (64, 150, 235),
    "Snow": (200, 230, 255),
    "Storm": (220, 80, 120),
}

STATUS_DEFAULTS = {
    "date": "----/--/--",
    "time": "--:--",
    "weather": "Unknown",
    "temp": "--°C",
    "humidity": "--%",
}

BACKGROUND_FILENAME = "/background.jpg"

BUTTON_LABELS = ("MODE", "UP", "DOWN")
BUTTON_HEIGHT = 28
BUTTON_MARGIN = 6

class DisplayManager:
    WIDTH = 240
    HEIGHT = 320

    def __init__(self):
        self.spi = SPI(
            0,
            baudrate=62_500_000,
            polarity=1,
            phase=1,
            sck=Pin(10),
            mosi=Pin(11),
            miso=Pin(12),
        )
        self.panel = ST7789(
            self.spi,
            DisplayManager.WIDTH,
            DisplayManager.HEIGHT,
            reset=Pin(15, Pin.OUT),
            dc=Pin(8, Pin.OUT),
            cs=Pin(9, Pin.OUT),
            backlight=Pin(13, Pin.OUT),
            rotation=1,
        )
        self.panel.init()
        self.panel.fill(0)
        self.panel.font = FONT_Default
        self.jpeg = JPEG(self.panel)
        self.current_mode = None
        self.current_payload = {}
        self.handlers = {
            "status_datetime": self._draw_status,
            "tasks_short": self._draw_tasks,
            "free_text": self._draw_free_text,
        }
        self.touch_controller = TouchController(
            sck=Pin(10),
            mosi=Pin(11),
            miso=Pin(12),
            cs=16,
            irq=17,
            width=DisplayManager.WIDTH,
            height=DisplayManager.HEIGHT,
        )
        self._active_button = None

    def set_mode(self, mode, payload):
        handler = self.handlers.get(mode)
        if not handler:
            return {"status": "error", "reason": "unknown_mode"}
        self.current_mode = mode
        self.current_payload = payload or {}
        handler(payload or {})
        return {"status": "ok", "mode": mode}

    def refresh(self):
        if self.current_mode and self.current_mode in self.handlers:
            self.handlers[self.current_mode](self.current_payload)

    # Mode handlers ---------------------------------------------------------
    def _draw_status(self, payload):
        data = prepare_status_data(payload)
        self.panel.fill(0)
        self._apply_background(data.get("background"))
        self._draw_buttons()
        primary_color = data.get("primary_color", color565(255, 255, 255))
        secondary_color = data.get("secondary_color", color565(200, 200, 200))
        self.panel.text(FONT_Default, data["date"], 12, 4, primary_color)
        self.panel.text(FONT_Default, data["time"], 12, 28, primary_color)
        self.panel.fill_rect(8, 60, DisplayManager.WIDTH - 16, 110, color565(0, 0, 0))
        self.panel.text(FONT_Default, data["weather"], 12, 72, primary_color)
        self.panel.text(FONT_Default, data["temp"], 12, 96, primary_color)
        self.panel.text(FONT_Default, data["humidity"], 12, 120, secondary_color)
        draw_weather_icon(self.panel, data["weather"], primary_color)

    def _draw_tasks(self, payload):
        tasks = normalize_tasks(payload)
        self.panel.fill(0)
        self._apply_background(payload.get("background"))
        self._draw_buttons()
        self.panel.text(FONT_Default, "Short Tasks", 12, 2, color565(255, 255, 255))
        y = 30
        for item in tasks:
            status_color = item.get("color", color565(255, 255, 255))
            self.panel.fill_rect(6, y - 2, DisplayManager.WIDTH - 12, 20, color565(20, 20, 20))
            self.panel.text(FONT_Default, item["title"], 12, y, status_color)
            self.panel.text(FONT_Default, item["status"], 12, y + 16, color565(180, 180, 180))
            y += 36
            if y > DisplayManager.HEIGHT - 32:
                break

    def _draw_free_text(self, payload):
        text = payload.get("text") or payload.get("message") or ""
        if isinstance(text, (list, tuple)):
            text = "\n".join(text)
        lines = wrap_text_lines(text or "", 22)
        self.panel.fill(0)
        self._apply_background(payload.get("background"))
        self._draw_buttons()
        y = 10
        for line in lines:
            self.panel.text(FONT_Default, line, 12, y, color565(255, 255, 255))
            y += 18
            if y > DisplayManager.HEIGHT - 10:
                break

    def _draw_buttons(self):
        btn_height = BUTTON_HEIGHT
        btn_width = (DisplayManager.WIDTH - BUTTON_MARGIN * 2) // len(BUTTON_LABELS)
        for idx, label in enumerate(BUTTON_LABELS):
            x = BUTTON_MARGIN + idx * btn_width
            self.panel.fill_rect(x, 0, btn_width - 2, btn_height, color565(30, 30, 30))
            self.panel.rect(x, 0, btn_width - 2, btn_height, color565(180, 180, 180))
            self.panel.text(FONT_Default, label, x + 6, 6, color565(255, 255, 255))

    def poll_touch(self):
        if not self.touch_controller:
            return None
        point = self.touch_controller.get_touch()
        if not point:
            self._active_button = None
            return None
        return self._handle_button_touch(*point)

    def _handle_button_touch(self, x, y):
        if y > BUTTON_HEIGHT:
            self._active_button = None
            return None
        btn_width = (DisplayManager.WIDTH - BUTTON_MARGIN * 2) // len(BUTTON_LABELS)
        x_rel = x - BUTTON_MARGIN
        if x_rel < 0:
            return None
        idx = min(len(BUTTON_LABELS) - 1, x_rel // btn_width)
        button = BUTTON_LABELS[idx]
        if button == self._active_button:
            return None
        self._active_button = button
        if button == "MODE":
            return {"cmd": "event", "event": {"type": "mode_request", "source": "touch_button"}}
        if button == "UP":
            return {"cmd": "event", "event": {"type": "scroll", "dir": "up", "source": "touch_button"}}
        return {"cmd": "event", "event": {"type": "scroll", "dir": "down", "source": "touch_button"}}

    # Background management ------------------------------------------------
    def _apply_background(self, background):
        if not background:
            return
        if "path" in background:
            self._render_jpeg(background["path"])
        elif "data" in background:
            self._render_jpeg_bytes(background["data"])

    def _render_jpeg(self, path):
        try:
            self.jpeg.open_file(path)
            self.jpeg.decode(0, 0, 1)
        except Exception:
            pass

    def _render_jpeg_bytes(self, encoded_data):
        try:
            raw = ubinascii.a2b_base64(encoded_data)
            with open(BACKGROUND_FILENAME, "wb") as f:
                f.write(raw)
            self._render_jpeg(BACKGROUND_FILENAME)
            os.remove(BACKGROUND_FILENAME)
        except Exception:
            pass


# Helpers -----------------------------------------------------------------

def prepare_status_data(payload):
    now = utime.localtime()
    date = payload.get("date") or "{:04d}/{:02d}/{:02d}".format(now[0], now[1], now[2])
    time_text = payload.get("time") or "{:02d}:{:02d}".format(now[3], now[4])
    weather = payload.get("weather") or STATUS_DEFAULTS["weather"]
    temp = payload.get("temp") or STATUS_DEFAULTS["temp"]
    humidity = payload.get("humidity") or STATUS_DEFAULTS["humidity"]
    color_tuple = WEATHER_COLOR_MAP.get(weather, (255, 255, 255))
    status = {
        "date": date,
        "time": time_text,
        "weather": weather,
        "temp": temp,
        "humidity": humidity,
        "primary_color": color565(*color_tuple),
        "secondary_color": color565(200, 200, 200),
        "background": payload.get("background"),
    }
    return status


def normalize_tasks(payload):
    raw = payload.get("tasks") or []
    if not isinstance(raw, list):
        raw = []
    output = []
    for item in raw[:4]:
        title = item.get("title", "Untitled")[0:20]
        status_text = item.get("status", "pending")
        color = {
            "done": color565(80, 200, 80),
            "in_progress": color565(255, 220, 80),
            "pending": color565(220, 220, 220),
        }.get(status_text, color565(220, 220, 220))
        output.append({"title": title, "status": status_text, "color": color})
    while len(output) < 4:
        output.append({"title": "", "status": "", "color": color565(100, 100, 100)})
    return output


def draw_weather_icon(panel, label, primary_color):
    icon = {
        "Sunny": "☀",
        "Cloudy": "☁",
        "Rain": "☂",
        "Storm": "⚡",
        "Snow": "❄",
    }.get(label, "?")
    panel.text(FONT_Default, icon, DisplayManager.WIDTH - 40, 70, primary_color)


def wrap_text_lines(text, width):
    if not text:
        return []
    result = []
    words = text.split()
    line = ""
    for word in words:
        if len(line) + len(word) + (1 if line else 0) > width:
            if line:
                result.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        result.append(line)
    return result
