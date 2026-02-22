# Communication Specification

This document defines the JSON structures, priorities, and behaviors for the Wi-Fi socket channel between Raspberry Pi 5 (host) and Raspberry Pi Pico 2 W.

## General Flow
1. Pico acts as the TCP client and connects to the host server defined in `src/config.py`.
2. The host accepts connections (see `host/command_server.py`) and interprets newline-delimited JSON commands.
3. The Pico processes commands immediately; touch-initiated local actions (`mode`/`scroll` buttons) are subject to host priority as described below.
4. Every command emits a JSON response (ACK or error) terminated by `\n`.

## Command Structure (host → Pico)
Each command is a JSON object with the following fields:
```json
{
  "cmd": "set_mode",              // or "refresh", "event", etc.
  "mode": "status_datetime",     // optional for non-mode commands
  "payload": { ... }               // mode-specific data
}
```
### Commands Supported
- `set_mode`: instructs the Pico to activate the specified mode. `mode` must exist in `DisplayManager.handlers`. Example:
  ```json
  {
    "cmd": "set_mode",
    "mode": "status_datetime",
    "payload": {
      "date": "2026/02/22",
      "time": "00:45",
      "weather": "Sunny",
      "temp": "15°C",
      "background": {"path": "/assets/bg.jpg"}
    }
  }
  ```
  For the new `free_text` mode send plain text:
  ```json
  {
    "cmd": "set_mode",
    "mode": "free_text",
    "payload": {
      "text": "Pi says hello!"
    }
  }
  ```
- `refresh`: requests the Pico to redraw the current mode using cached payload.
  ```json
  {"cmd": "refresh"}
  ```
- `event`: the host may send this for debugging or for handshaking; Pico can ignore or log it as needed.

## Event / Touch Feedback (Pico → Host)
Pico sends JSON responses when it completes commands or when touch interactions occur:
```json
{
  "status": "ok",               // or "error"
  "mode": "tasks_short",        // optional
  "event": {
    "type": "touch",
    "target": "btn_scroll_up",
    "x": 120,
    "y": 18
  }
}
```
Examples:
- After `set_mode`, send `{ "status":"ok", "mode":"tasks_short" }`.
- When a user taps the scroll buttons, issue `{ "status":"event", "event":{"type":"scroll","dir":"up"}}`.

## Button Priority
- The top-of-screen touch buttons emit local events, allowing Pico to scroll lists or request a mode switch without host intervention.
- However, **host-initiated `set_mode` commands always win**. If a button post-dates a host command, the Pico still honors the latest host command and ignores conflicting local mode toggles.
- Scroll actions (up/down buttons) are treated as hints: Pico alters the visible window and may report the request back to the host in the `event` response. They do not override host-specified mode content.

## Payload Guidelines
- `display` payloads include optional `background` keys with either `{"path":"/assets/bg.jpg"}` or `{"data":"<base64>"}`.
- Task payloads expect `"tasks"` arrays with `title`/`status`. Additional data (like `due` or `icon`) can be forwarded to custom renderers.
- All JSON is UTF-8 encoded and newline-delimited. The host should not send partial commands; Pico buffers until `\n` is seen.
- Retries: if the Pico detects a malformed JSON, it discards the frame and sends `{ "status":"error", "reason":"bad_payload" }`.

## Reliability
- Both sides should include timeouts. Pico reconnects (`RECONNECT_DELAY`) if the socket closes.
- Host may re-broadcast the last `set_mode` after reconnection to ensure the display stays consistent.

Refer to `docs/display-modes.md` for mode-specific payloads and `docs/communication-spec.md` for behavioral guarantees when you need to extend the protocol.
