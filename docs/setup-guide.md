# Setup and Calibration Guide

This note captures the recommended steps for first-time execution and for calibrating the Pico-ResTouch LCD’s touch interface.

## 1. Environment Preparation
1. Clone the repository and install dependencies on Raspberry Pi 5:
   ```bash
   git clone https://github.com/Murasan201/pi-pico-display-controller
   cd pi-pico-display-controller
   pip3 install mpremote
   sudo apt install picotool python3-pip
   pip3 install mpy-cross
   ```
2. Customize hardware-sensitive files:
   - Copy `src/config.py` to `src/config_local.py` and fill in the actual `TCP_SERVER_HOST` (Pi 5 IP or mDNS name).
   - Populate `src/secrets.py` with Wi-Fi SSID and password. This ensures Git ignores credentials while the device has accurate values.
3. Prepare assets (JPEG backgrounds, icons) under `assets/` and keep them synced with the Pico via `mpremote` or by embedding in the UF2.

## 2. MicroPython Deployment
1. Build/prepare files:
   ```bash
   mpy-cross src/main.py -o build/main.mpy
   mpy-cross src/display_manager.py -o build/display_manager.mpy
   ```
   (Optional: keep original `.py` for easier edits.)
2. Copy files to the Pico using `mpremote`:
   ```bash
   mpremote connect usb0 fs cp build/main.mpy :/main.mpy
   mpremote connect usb0 fs mkdir -p assets
   mpremote connect usb0 fs cp assets/* :/assets/
   mpremote connect usb0 run main.mpy
   ```
3. Alternatively, if performing a fresh flash: create a UF2 (`picotool convert` or `uf2conv.py`) and use:
   ```bash
   picotool load build/main.uf2
   ```
4. Make sure `src/config_local.py` (or `config.py`) on the Pico contains the host IP before running.

## 3. Host Server Execution
1. Start the TCP command server on Raspberry Pi 5:
   ```bash
   python3 host/command_server.py --bind 0.0.0.0 --port 5000
   ```
2. Use the interactive prompt (`mode`, `refresh`, raw JSON) to send mode commands. Example:
   ```bash
   mode status_datetime {"date":"2026/02/22","time":"00:45","weather":"Sunny","temp":"15°C"}
   ```
3. Background JPEGs can be referenced after syncing them to `/assets/` on the Pico or encoded as Base64 in the payload.

## 4. Touch Driver Calibration
The touchscreen uses the XPT2046 controller. Calibration ensures the drawn touch buttons (mode/up/down) respond accurately.

1. **Wiring Verification**
   - CS → GP16, IRQ → GP17 (configurable in `touch_controller.py`).
   - SPI signals already match the display pins (SCK=GP10, MOSI=GP11, MISO=GP12).
2. **Calibration Routine**
   - Run a short MicroPython script on the Pico (via `mpremote` run) to sample raw touch values at known screen coordinates (10, 10), (230, 10), (10, 310), (230, 310).
   - Compare the raw readings with expected coordinates, then adjust scaling in `TouchController.get_touch()` (`width`/`height` multipliers or apply offsets) to map raw values to actual screen pixels.
   - The current `TouchController` implementation simply scales by 4096 and flips Y. If you notice consistent bias, insert offsets or calibrate `x = (x_raw * width) // 4096 + x_offset`.
3. **Testing**
   - With the Pico running, touch the on-screen buttons and confirm `main.py` prints `event` responses in the host server terminal.
   - If button responses jump, revisit `TouchController` scaling or filter the raw values (e.g., average multiple samples) to reduce jitter.

## 5. Maintenance
- Keep `docs/setup-guide.md` updated if the deployment flow or calibration steps change.
- For automated deployments, introduce a shell script (e.g., `scripts/deploy.sh`) that wraps `mpremote`/`picotool` commands and refreshes the Pico after copying assets.

Refer back to `docs/system-spec.md` for the overall architecture and `docs/communication-spec.md` for protocol guarantees. These documents remain the canonical references for any future adjustments.
