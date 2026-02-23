from machine import Pin, SPI
from touch_controller import TouchController
import utime
import ubinascii
import os

from st7789 import ST7789, color565
import vga1_8x16 as font
from text_renderer import draw_text, wrap_text_jp, truncate_to_width
from config import JST_OFFSET


WEATHER_COLOR_MAP = {
    "Sunny": (255, 205, 60),
    "Clear": (255, 205, 60),
    "晴れ": (255, 205, 60),
    "晴": (255, 205, 60),
    "Cloudy": (180, 180, 180),
    "曇り": (180, 180, 180),
    "曇": (180, 180, 180),
    "Rain": (64, 150, 235),
    "雨": (64, 150, 235),
    "Snow": (200, 230, 255),
    "雪": (200, 230, 255),
    "Storm": (220, 80, 120),
    "雷": (220, 80, 120),
    "雷雨": (220, 80, 120),
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
CONTENT_TOP = BUTTON_HEIGHT + 4

class DisplayManager:
    WIDTH = 240
    HEIGHT = 320

    def __init__(self):
        self.spi = SPI(
            1,
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
            rotation=2,
        )
        self.panel.init()
        self.panel.fill(0)
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
        if mode == "status_datetime" and self.current_mode == "status_datetime":
            self.current_payload.update(payload or {})
        else:
            self.current_payload = payload or {}
        self.current_mode = mode
        handler(self.current_payload)
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
        y = CONTENT_TOP
        draw_text(self.panel, data["date"], 12, y, primary_color)
        draw_text(self.panel, data["time"], 12, y + 24, primary_color)
        self.panel.fill_rect(8, y + 56, DisplayManager.WIDTH - 16, 110, color565(0, 0, 0))
        draw_text(self.panel, data["weather"], 12, y + 68, primary_color)
        draw_text(self.panel, data["temp"], 12, y + 92, primary_color)
        draw_text(self.panel, data["humidity"], 12, y + 116, secondary_color)
        draw_weather_icon(self.panel, data["weather"], primary_color, y + 66)

    def _draw_tasks(self, payload):
        tasks = normalize_tasks(payload)
        self.panel.fill(0)
        self._apply_background(payload.get("background"))
        self._draw_buttons()
        self.panel.text(font, "Short Tasks", 12, CONTENT_TOP, color565(255, 255, 255))
        y = CONTENT_TOP + 24
        for item in tasks:
            status_color = item.get("color", color565(255, 255, 255))
            self.panel.fill_rect(6, y - 2, DisplayManager.WIDTH - 12, 20, color565(20, 20, 20))
            draw_text(self.panel, item["title"], 12, y, status_color)
            draw_text(self.panel, item["status"], 12, y + 16, color565(180, 180, 180))
            y += 36
            if y > DisplayManager.HEIGHT - 32:
                break

    def _draw_free_text(self, payload):
        text = payload.get("text") or payload.get("message") or ""
        if isinstance(text, (list, tuple)):
            text = "\n".join(text)
        lines = wrap_text_jp(text or "", 216)
        self.panel.fill(0)
        self._apply_background(payload.get("background"))
        self._draw_buttons()
        y = CONTENT_TOP
        for line in lines:
            draw_text(self.panel, line, 12, y, color565(255, 255, 255))
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
            self.panel.text(font, label, x + 6, 6, color565(255, 255, 255))

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
            self.panel.jpg(path, 0, 0)
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
    now = utime.localtime(utime.time() + JST_OFFSET)
    date = "{:04d}/{:02d}/{:02d}".format(now[0], now[1], now[2])
    time_text = "{:02d}:{:02d}".format(now[3], now[4])
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
        title = truncate_to_width(item.get("title", "Untitled"), 216)
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


def draw_weather_icon(panel, label, primary_color, y=70):
    x = DisplayManager.WIDTH - 44
    if label in ("Sunny", "Clear", "晴れ", "晴"):
        # Sun: filled circle with rays
        panel.fill_rect(x + 8, y + 8, 16, 16, primary_color)
        for dy in (0, 28):
            panel.fill_rect(x + 12, y + dy, 8, 4, primary_color)
        for dx in (0, 28):
            panel.fill_rect(x + dx, y + 12, 4, 8, primary_color)
    elif label in ("Cloudy", "曇り", "曇"):
        # Cloud: two overlapping rectangles
        panel.fill_rect(x + 4, y + 12, 24, 12, primary_color)
        panel.fill_rect(x + 8, y + 6, 16, 8, primary_color)
    elif label in ("Rain", "雨"):
        # Cloud + rain drops
        c = color565(100, 100, 100)
        panel.fill_rect(x + 4, y + 4, 24, 10, c)
        panel.fill_rect(x + 8, y + 0, 16, 6, c)
        for dx in (6, 14, 22):
            panel.fill_rect(x + dx, y + 18, 2, 6, primary_color)
            panel.fill_rect(x + dx, y + 26, 2, 4, primary_color)
    elif label in ("Storm", "雷", "雷雨"):
        # Cloud + lightning bolt
        c = color565(100, 100, 100)
        panel.fill_rect(x + 4, y + 4, 24, 10, c)
        panel.fill_rect(x + 8, y + 0, 16, 6, c)
        panel.fill_rect(x + 14, y + 14, 6, 4, primary_color)
        panel.fill_rect(x + 12, y + 18, 6, 4, primary_color)
        panel.fill_rect(x + 10, y + 22, 6, 4, primary_color)
    elif label in ("Snow", "雪"):
        # Snowflake: cross pattern
        panel.fill_rect(x + 14, y + 2, 4, 28, primary_color)
        panel.fill_rect(x + 2, y + 14, 28, 4, primary_color)
        panel.fill_rect(x + 6, y + 6, 4, 4, primary_color)
        panel.fill_rect(x + 22, y + 6, 4, 4, primary_color)
        panel.fill_rect(x + 6, y + 22, 4, 4, primary_color)
        panel.fill_rect(x + 22, y + 22, 4, 4, primary_color)
    else:
        panel.text(font, "?", x + 8, y + 8, primary_color)


