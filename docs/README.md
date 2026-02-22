# Documentation index

This directory collects all project-specific documents that describe the hardware, firmware, communication, operational procedures, and development artifacts for the Pico display controller.

## Core Documents
- `system-spec.md`: overall system architecture, networking, CLI deployment steps, vertical UI spec, button handling, and configuration guidance (IP management, sensitive files, power). Consider this your go-to reference for how all components interact.
- `communication-spec.md`: JSON command formats, ACK/error expectations, touch/scroll event structure, and host-priority guarantees for the Wi-Fi socket channel between the Pi host and Pico.
- `setup-guide.md`: step-by-step deployment walkthrough and touch calibration instructions to get the system running and the buttons responding accurately.
- `pi-host.md`: Raspberry Pi 5 command server documentation, CLI usage patterns, automation (`--preload`, `--headless`), and JPEG background handling from the Pi side.
- `display-library.md`: `DisplayManager` helpers, payload normalization, JPEG background loading, and shared rendering utilities for all display modes.
- `display-modes.md`: summary of current display modes (`status_datetime`, `tasks_short`), payload expectations, and mode-switching handshake with the host, including the touch button layout.
- `pico-restouch-lcd-2.8.md`: Waveshare Pico-ResTouch-LCD-2.8 hardware reference (specs, pinout, features) that inspired the project’s display selection.
