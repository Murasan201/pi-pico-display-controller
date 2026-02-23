# Configuration values for Raspberry Pi Pico MicroPython stack.
TCP_SERVER_HOST = "192.168.11.16"  # Pi 5 local IP
TCP_SERVER_PORT = 5000
BUFFER_SIZE = 1024
RECONNECT_DELAY = 5
SOCKET_TIMEOUT = 0.75  # shorter timeout to allow touch polling
AUTO_REFRESH_INTERVAL = 60  # seconds between auto-refresh in status_datetime mode
JST_OFFSET = 9 * 3600       # UTC+9 in seconds
NTP_SYNC_INTERVAL = 86400   # re-sync NTP every 24 hours
SD_CS = 22
SD_MOUNT_POINT = "/sd"
