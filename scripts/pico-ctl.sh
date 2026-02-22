#!/usr/bin/env bash
# pico-ctl.sh — Safe utility for Pico display command server operations.

set -euo pipefail

# Resolve project root from this script location.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PICO_PROJECT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SERVER_SCRIPT="${PICO_PROJECT}/host/command_server.py"
FIFO_PATH="/tmp/pico-cmd-fifo"
LOG_FILE="/tmp/pico-server.log"
PID_FILE="/tmp/pico-server.pid"
SERVER_PORT=5000
MPREMOTE="${PICO_PROJECT}/.venv/bin/mpremote"

_server_pid() {
    pgrep -f "python3.*command_server.py.*--headless" 2>/dev/null | head -1
}

_is_running() {
    [[ -n "$(_server_pid)" ]]
}

_pico_connected() {
    ss -tn state established "( sport = :${SERVER_PORT} )" 2>/dev/null | rg -q ":${SERVER_PORT}" 2>/dev/null
}

_ensure_fifo() {
    if [[ ! -p "$FIFO_PATH" ]]; then
        rm -f "$FIFO_PATH"
        mkfifo "$FIFO_PATH"
    fi
}

_fifo_write_line() {
    local line="$1"
    # Keep FIFO writes bounded so callers never block indefinitely.
    printf '%s\n' "$line" | timeout 3 tee "$FIFO_PATH" >/dev/null
}

cmd_start() {
    if _is_running; then
        echo "OK: Server already running (PID $(_server_pid))"
        return 0
    fi
    _ensure_fifo
    cd "$PICO_PROJECT"
    nohup python3 -u "$SERVER_SCRIPT" --headless --fifo "$FIFO_PATH" > "$LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"
    for _ in $(seq 1 6); do
        sleep 0.5
        if rg -q "Listening for Pico connections" "$LOG_FILE" 2>/dev/null; then
            echo "OK: Server started (PID $pid)"
            return 0
        fi
    done
    echo "WARN: Server started (PID $pid) but may not be ready yet. Check logs."
}

cmd_stop() {
    local pid
    pid="$(_server_pid)"
    if [[ -z "$pid" ]]; then
        echo "OK: Server not running"
        rm -f "$PID_FILE"
        return 0
    fi
    kill "$pid" 2>/dev/null
    for _ in $(seq 1 6); do
        sleep 0.5
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "OK: Server stopped"
            rm -f "$PID_FILE"
            return 0
        fi
    done
    kill -9 "$pid" 2>/dev/null || true
    rm -f "$PID_FILE"
    echo "OK: Server force-killed"
}

cmd_restart() {
    cmd_stop
    sleep 0.5
    cmd_start
}

cmd_status() {
    echo "=== Pico Display Controller Status ==="
    if _is_running; then
        echo "Server: RUNNING (PID $(_server_pid))"
    else
        echo "Server: STOPPED"
    fi
    if [[ -p "$FIFO_PATH" ]]; then
        echo "FIFO: OK ($FIFO_PATH)"
    else
        echo "FIFO: MISSING"
    fi
    if _pico_connected; then
        echo "Pico: CONNECTED"
    else
        echo "Pico: NOT CONNECTED"
    fi
    if [[ -e /dev/ttyACM0 ]]; then
        echo "USB: /dev/ttyACM0 present"
    else
        echo "USB: No ttyACM device"
    fi
    if [[ -f "$LOG_FILE" ]]; then
        echo "--- Recent log ---"
        tail -3 "$LOG_FILE"
    fi
}

cmd_send() {
    local json_cmd="$1"
    if ! _is_running; then
        echo "ERROR: Server not running. Use: scripts/pico-ctl.sh start"
        return 1
    fi
    _ensure_fifo
    if _fifo_write_line "$json_cmd"; then
        echo "OK: Command sent"
    else
        echo "ERROR: FIFO write timed out (no reader?)"
        return 1
    fi
}

cmd_send_stdin() {
    if ! _is_running; then
        echo "ERROR: Server not running. Use: scripts/pico-ctl.sh start"
        return 1
    fi
    _ensure_fifo
    local payload
    payload="$(cat)"
    payload="$(printf '%s' "$payload" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    if [[ -z "$payload" ]]; then
        echo "ERROR: Empty stdin payload"
        return 1
    fi
    if _fifo_write_line "$payload"; then
        echo "OK: Command sent (stdin)"
    else
        echo "ERROR: FIFO write timed out (no reader?)"
        return 1
    fi
}

cmd_send_file() {
    local file="$1"
    if [[ ! -f "$file" ]]; then
        echo "ERROR: File not found: $file"
        return 1
    fi
    if ! _is_running; then
        echo "ERROR: Server not running. Use: scripts/pico-ctl.sh start"
        return 1
    fi
    _ensure_fifo
    local count=0
    while IFS= read -r line || [[ -n "$line" ]]; do
        line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        [[ -z "$line" || "$line" == \#* ]] && continue
        if _fifo_write_line "$line"; then
            ((count++))
        else
            echo "ERROR: FIFO write timed out at line $count"
            return 1
        fi
    done < "$file"
    echo "OK: Sent $count commands from $file"
}

cmd_reset_pico() {
    if [[ ! -e /dev/ttyACM0 ]]; then
        echo "ERROR: No Pico USB device (/dev/ttyACM0 not found)"
        return 1
    fi
    if [[ -x "$MPREMOTE" ]]; then
        timeout 10 "$MPREMOTE" connect /dev/ttyACM0 reset >/dev/null 2>&1
        echo "OK: Pico reset command sent"
    else
        echo "ERROR: mpremote not found at $MPREMOTE"
        return 1
    fi
}

cmd_wait_pico() {
    local timeout_sec="${1:-30}"
    local elapsed=0
    echo "Waiting for Pico to connect (timeout: ${timeout_sec}s)..."
    while (( elapsed < timeout_sec )); do
        if _pico_connected; then
            echo "OK: Pico connected (waited ${elapsed}s)"
            return 0
        fi
        sleep 1
        ((elapsed++))
    done
    echo "TIMEOUT: Pico did not connect within ${timeout_sec}s"
    return 1
}

cmd_logs() {
    local n="${1:-30}"
    if [[ -f "$LOG_FILE" ]]; then
        tail -"$n" "$LOG_FILE"
    else
        echo "No log file found at $LOG_FILE"
    fi
}

case "${1:-help}" in
    start)      cmd_start ;;
    stop)       cmd_stop ;;
    restart)    cmd_restart ;;
    status)     cmd_status ;;
    send)
        if [[ -z "${2:-}" ]]; then
            echo "Usage: scripts/pico-ctl.sh send '<json>'"
            exit 1
        fi
        cmd_send "$2"
        ;;
    send-stdin) cmd_send_stdin ;;
    send-file)
        if [[ -z "${2:-}" ]]; then
            echo "Usage: scripts/pico-ctl.sh send-file <path>"
            exit 1
        fi
        cmd_send_file "$2"
        ;;
    reset-pico) cmd_reset_pico ;;
    wait-pico)  cmd_wait_pico "${2:-30}" ;;
    logs)       cmd_logs "${2:-30}" ;;
    help|*)
        echo "pico-ctl.sh — Pico display controller utility"
        echo ""
        echo "Commands:"
        echo "  start          Start the command server (idempotent)"
        echo "  stop           Stop the command server"
        echo "  restart        Restart the command server"
        echo "  status         Quick status check"
        echo "  send <json>    Send JSON command via FIFO"
        echo "  send-stdin     Send one JSON command from stdin (HEREDOC-safe)"
        echo "  send-file <f>  Send commands from file"
        echo "  reset-pico     Soft-reset the Pico"
        echo "  wait-pico [s]  Wait for Pico connection (default 30s)"
        echo "  logs [n]       Show last n log lines (default 30)"
        ;;
esac
