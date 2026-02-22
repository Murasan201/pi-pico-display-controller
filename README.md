# Pico Display Controller

This repository hosts the software and documentation for a Raspberry Pi 5 + Raspberry Pi Pico 2 W system that drives a WaveShare Pico-ResTouch-LCD-2.8 (WAVESHARE-19804) display. The Pico runs MicroPython, renders several predefined display modes, and receives rendering instructions over a Wi-Fi socket from the Pi 5 host. USB is used only for power; the communication channel is TCP over Wi-Fi.

## Hardware
- **Raspberry Pi 5**: Acts as the host commander. Provides power over USB, runs the TCP command server, and sends JSON commands (modes, backgrounds, refreshes) to the Pico.
- **Raspberry Pi Pico 2 W**: Controls the SPI display, handles touch input, and executes MicroPython code. Connects to the Pi host via Wi-Fi sockets.
- **WAVESHARE-19804 / Pico-ResTouch-LCD-2.8**: 2.8-inch, 320×240 IPS with ST7789 driver and XPT2046 resistive touch. Background JPEGs and drawn overlays run on this panel.

## Software Architecture
- **MicroPython code (`src/`)**:
  - `main.py`: Wi-Fi client, TCP socket glue, and command dispatcher (`set_mode`, `refresh`).
  - `display_manager.py`: Initializes ST7789, draws `status_datetime` and `tasks_short` modes, handles JPEG backgrounds (local or Base64 data), and wraps helper functions for formatting payloads.
  - `config.py`: Contains `TCP_SERVER_HOST`, port, and buffer settings. Update this file (or create `config_local.py`) to match the actual Pi host IP/hostname before deployment. This file is ignored by Git once renamed to `config_local.py`.
  - `secrets.py`: Wi-Fi SSID/password. This file is explicitly ignored; do not commit credentials.
- **Raspberry Pi host (`host/command_server.py`)**:
  - A threaded TCP server that logs Pico responses and broadcasts commands.
  - CLI allows interactive mode commands (`mode`, `refresh`) and JSON payloads. Supports `--preload`/`--headless` for automation.
  - Documented in `docs/pi-host.md`.

## Setup and Deployment
1. **Prepare the Pico files**
   - Copy `src/main.py`, `src/display_manager.py`, and any assets (backgrounds, icons) to the Pico via `mpremote` or photo load via `picotool`.
   - Before copying, update `src/config.py` (or `config_local.py`) with the Pi host address and update `src/secrets.py` with your Wi-Fi credentials. These files are ignored by Git, so maintain local copies only.
   - Convert performance-critical files with `mpy-cross` if desired and place them under `build/` for faster startup.
2. **Deploy using CLI**
   - Install `mpremote`, `picotool`, and `mpy-cross` on the Pi host. Use `picotool load build/main.uf2` for BOOTSEL-write and `mpremote` to sync files while MicroPython is running.
   - Automate using a script such as `scripts/deploy.sh` that copies files, uploads assets, and restarts the Pico.
3. **Run the host server**
   - Prefer `scripts/pico-ctl.sh` for all host operations (start/stop/status/send). This avoids FIFO blocking and shell escaping issues.
   - Launch/start the server via script:
     ```bash
     scripts/pico-ctl.sh start
     scripts/pico-ctl.sh status
     ```
   - Send commands via script (do not write directly to `/tmp/pico-cmd-fifo`):
     ```bash
     scripts/pico-ctl.sh send '{"cmd":"set_mode","mode":"status_datetime","payload":{"date":"2026/02/22","time":"00:15","weather":"Cloudy","temp":"12C"}}'
     scripts/pico-ctl.sh send '{"cmd":"set_mode","mode":"tasks_short","payload":{"tasks":[{"title":"Docs","status":"in_progress"}]}}'
     scripts/pico-ctl.sh send '{"cmd":"refresh"}'
     ```
   - If payload includes special characters like `!`, use HEREDOC-safe stdin mode:
     ```bash
     scripts/pico-ctl.sh send-stdin <<'EOF'
     {"cmd":"set_mode","mode":"free_text","payload":{"text":"Display test!"}}
     EOF
     ```
   - Background JPEGs can be referenced via `background:{"path":"/assets/bg.jpg"}` (after syncing to the Pico) or sent as Base64 data for on-the-fly images.

## Security & Secrets
- Do **not** commit real IP addresses, SSIDs, or Wi-Fi passwords. `src/config.py` and `src/secrets.py` are intentionally ignored via `.gitignore`. Copy them to local files (e.g., `config_local.py`) during deployment and fill in the environment-specific values.
- The host IP is fixed in your setup; update `TCP_SERVER_HOST` locally on a per-device basis. The documentation in `docs/system-spec.md` and `docs/pi-host.md` explains how to manage these values and keep them out of GitHub.

## Documentation
- `docs/system-spec.md`: System architecture, communication flow, CLI deployment steps, and IP management practices.
- `docs/display-modes.md`: Mode descriptions and command expectations.
- `docs/display-library.md`: Display manager helpers, data validation, and JPEG background routines.
- `docs/pi-host.md`: Host server usage, automation examples, and background handling.
- `docs/pico-restouch-lcd-2.8.md`: Hardware reference for the Waveshare display.

## Project Governance
See `AGENTS.md` (root) for hardware rules and documentation obligations. Long-term planning files (`task_plan.md`, `findings.md`, `progress.md`) log project milestones and should be updated when new work begins or concludes.
