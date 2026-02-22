#!/bin/bash
# Generate Japanese bitmap font module for Pico 2 W display
#
# Prerequisites:
#   - freetype-py (pip install freetype-py)
#   - DroidSansFallbackFull.ttf
#
# Output: src/font_jp16.py

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

FONT2BITMAP="/mnt/ssd/workspace/st7789_mpy/utils/font2bitmap.py"
TTF_FILE="/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
CHARSET_SCRIPT="${SCRIPT_DIR}/jp_charset.py"
OUTPUT="${PROJECT_DIR}/src/font_jp16.py"
FONT_HEIGHT=16

# Validate prerequisites
for f in "$FONT2BITMAP" "$TTF_FILE" "$CHARSET_SCRIPT"; do
    if [ ! -f "$f" ]; then
        echo "ERROR: Required file not found: $f" >&2
        exit 1
    fi
done

# Get character set string
CHARSET=$(python3 "$CHARSET_SCRIPT")

echo "Generating Japanese font (${FONT_HEIGHT}px)..."
echo "  Font: $TTF_FILE"
echo "  Output: $OUTPUT"

python3 "$FONT2BITMAP" "$TTF_FILE" "$FONT_HEIGHT" -c "$CHARSET" > "$OUTPUT"

# Show file size
SIZE=$(wc -c < "$OUTPUT")
echo "Done! Generated ${SIZE} bytes -> ${OUTPUT}"
