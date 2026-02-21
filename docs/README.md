# Documentation index

This directory collects all project-specific documents that describe the hardware, firmware, communication, operational procedures, and development artifacts for the Pico display controller.

## Core Documents
- `system-spec.md`: overall system architecture, networking, CLI deployment steps, and configuration guidance (IP management, sensitive files, power). Consider this your go-to reference for how all components interact.
- `pi-host.md`: Raspberry Pi 5 command server documentation, CLI usage patterns, automation (`--preload`, `--headless`), and JPEG background handling from the Pi side.
- `display-library.md`: `DisplayManager` helpers, payload normalization, JPEG background loading, and shared rendering utilities for all display modes.
- `display-modes.md`: summary of current display modes (`status_datetime`, `tasks_short`), payload expectations, and mode-switching handshake with the host.
- `pico-restouch-lcd-2.8.md`: Waveshare Pico-ResTouch-LCD-2.8 hardware reference (specs, pinout, features) that inspired the project’s display selection.

## Supporting Notes
- `findings.md`: captured research/decisions so far (hardware research, communication choice, mode selections, JPEG requirement).
- `progress.md`: log of phases completed during this work, including MicroPython implementation and Raspberry Pi host pieces.
- `task_plan.md`: Manus-style planning file that outlines the objective, phase breakdown, and status of ongoing tasks.

## Usage Guidelines
Keep adding documentation here when you introduce new modes, APIs, or operational procedures. When linking to these docs from the project root or other docs, always reference this index so contributors know what has already been covered.
