import time
import socket
import json
import os
import network
from machine import Pin, SPI

from display_manager import DisplayManager
from config import (
    TCP_SERVER_HOST, TCP_SERVER_PORT, BUFFER_SIZE, RECONNECT_DELAY,
    SOCKET_TIMEOUT, AUTO_REFRESH_INTERVAL, NTP_SYNC_INTERVAL,
    SD_CS, SD_MOUNT_POINT,
)
from secrets import WIFI_SSID, WIFI_PASSWORD


def mount_sd(timeout_sec=5):
    try:
        import sdcard
        deadline = time.time() + timeout_sec
        Pin(9, Pin.OUT, value=1)   # LCD CS HIGH
        Pin(16, Pin.OUT, value=1)  # TP CS HIGH
        spi = SPI(1, baudrate=400_000, polarity=0, phase=0,
                  sck=Pin(10), mosi=Pin(11), miso=Pin(12))
        sd = sdcard.SDCard(spi, Pin(SD_CS, Pin.OUT, value=1))
        if time.time() > deadline:
            raise OSError("SD init timeout")
        # Warmup read to wake card data transfer engine
        spi.init(baudrate=1_000_000)
        try:
            sd.readblocks(0, bytearray(512))
        except OSError:
            pass
        if time.time() > deadline:
            raise OSError("SD readblocks timeout")
        spi.init(baudrate=20_000_000)
        os.mount(os.VfsFat(sd), SD_MOUNT_POINT)
        print("SD mount OK")
        files = [SD_MOUNT_POINT + "/" + f
                 for f in os.listdir(SD_MOUNT_POINT)
                 if f.startswith("background_") and f.endswith(".jpg")]
        files.sort()
        print("SD backgrounds:", len(files))
        return files
    except Exception as e:
        print("SD mount failed:", e)
        return []


def sync_ntp():
    import ntptime
    for attempt in range(3):
        try:
            ntptime.settime()
            print("NTP sync OK")
            return True
        except Exception as e:
            print("NTP sync attempt", attempt + 1, "failed:", e)
            time.sleep(2)
    return False


def send_event(sock, event):
    if not event:
        return
    try:
        sock.send((json.dumps(event) + "\n").encode())
    except OSError:
        pass


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    if not wlan.active():
        wlan.active(True)
    if not wlan.isconnected():
        wlan.disconnect()
        time.sleep(1)
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        timeout = time.time() + 15
        while not wlan.isconnected() and time.time() < timeout:
            time.sleep(0.5)
    return wlan


def handle_command(payload, display):
    cmd = payload.get("cmd")
    if cmd == "set_mode":
        mode = payload.get("mode")
        data = payload.get("payload", {})
        return display.set_mode(mode, data)
    if cmd == "refresh":
        display.refresh()
        return {"status": "ok", "mode": display.current_mode}
    return {"status": "error", "reason": "unknown_command"}


def _show_connection_error(display, wlan, reason, retry_count):
    ip = "-"
    try:
        if wlan and wlan.isconnected():
            ip = wlan.ifconfig()[0]
    except Exception:
        pass
    lines = [
        "Pico connection error",
        "host: {}:{}".format(TCP_SERVER_HOST, TCP_SERVER_PORT),
        "reason: {}".format(reason),
        "wifi ip: {}".format(ip),
        "retry: {} ({}s)".format(retry_count, RECONNECT_DELAY),
    ]
    display.set_mode("free_text", {"text": "\n".join(lines)})


def run():
    display = DisplayManager()
    wlan = connect_wifi()
    bg_list = mount_sd()
    display.set_backgrounds(bg_list)
    ntp_ok = sync_ntp()
    last_ntp_sync = time.time() if ntp_ok else 0
    last_refresh = time.time()
    retry_count = 0
    while True:
        if not wlan.isconnected():
            wlan = connect_wifi()
            if not wlan.isconnected():
                retry_count += 1
                _show_connection_error(display, wlan, "wifi_disconnected", retry_count)
                time.sleep(RECONNECT_DELAY)
                continue
        # Periodic NTP re-sync
        now = time.time()
        if now - last_ntp_sync >= NTP_SYNC_INTERVAL:
            if sync_ntp():
                last_ntp_sync = time.time()
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(SOCKET_TIMEOUT)
            sock.connect((TCP_SERVER_HOST, TCP_SERVER_PORT))
            retry_count = 0
            buffer = b""
            while True:
                try:
                    chunk = sock.recv(BUFFER_SIZE)
                except OSError as e:
                    if e.args[0] == 110:  # ETIMEDOUT
                        send_event(sock, display.poll_touch())
                        # Auto-refresh for status_datetime mode
                        now = time.time()
                        if (display.current_mode == "status_datetime"
                                and now - last_refresh >= AUTO_REFRESH_INTERVAL):
                            display.refresh()
                            last_refresh = now
                        # Periodic NTP re-sync
                        if now - last_ntp_sync >= NTP_SYNC_INTERVAL:
                            if sync_ntp():
                                last_ntp_sync = time.time()
                        continue
                    raise
                if not chunk:
                    raise OSError("socket closed")
                buffer += chunk.replace(b"\r", b"")
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line.decode("utf-8"))
                    except Exception:
                        continue
                    response = handle_command(payload, display)
                    if response.get("status") == "ok":
                        last_refresh = time.time()
                    try:
                        sock.send((json.dumps(response) + "\n").encode())
                    except OSError:
                        raise
        except Exception as exc:
            retry_count += 1
            print("Socket error", exc)
            _show_connection_error(display, wlan, exc, retry_count)
            time.sleep(RECONNECT_DELAY)
        finally:
            if sock:
                sock.close()


if __name__ == "__main__":
    run()
