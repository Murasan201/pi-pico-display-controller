import time
import socket
import json
import network

from display_manager import DisplayManager
from config import (
    TCP_SERVER_HOST, TCP_SERVER_PORT, BUFFER_SIZE, RECONNECT_DELAY,
    SOCKET_TIMEOUT, AUTO_REFRESH_INTERVAL, NTP_SYNC_INTERVAL,
)
from secrets import WIFI_SSID, WIFI_PASSWORD


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


def run():
    display = DisplayManager()
    wlan = connect_wifi()
    ntp_ok = sync_ntp()
    last_ntp_sync = time.time() if ntp_ok else 0
    last_refresh = time.time()
    while True:
        if not wlan.isconnected():
            wlan = connect_wifi()
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
            print("Socket error", exc)
            time.sleep(RECONNECT_DELAY)
        finally:
            if sock:
                sock.close()


if __name__ == "__main__":
    run()
