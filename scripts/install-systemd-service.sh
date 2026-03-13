#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_SRC="${PROJECT_ROOT}/tools/systemd/pico-command-server.service"
SERVICE_DST="/etc/systemd/system/pico-command-server.service"

if [[ ! -f "${SERVICE_SRC}" ]]; then
  echo "ERROR: service template not found: ${SERVICE_SRC}"
  exit 1
fi

sudo cp "${SERVICE_SRC}" "${SERVICE_DST}"
sudo systemctl daemon-reload
sudo systemctl enable --now pico-command-server.service
sudo systemctl status --no-pager pico-command-server.service

echo "OK: pico-command-server.service installed and started"
