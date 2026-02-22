"""Text rendering with Japanese font support for ST7789 display.

Provides unified text drawing that auto-selects between:
- panel.text(vga1_8x16, ...) fast path for ASCII-only text (8px/char)
- panel.write(font_jp16, ...) for text containing Japanese/non-ASCII (16px/char)
- Custom rendering for ° (degree sign) which has a broken glyph in the font

Also provides pixel-width-based text wrapping for Japanese text.
"""

import vga1_8x16 as font_ascii
import font_jp16

# Character widths by rendering path
_ASCII_CHAR_W = 8   # vga1_8x16 fixed width
_JP_CHAR_W = 16     # font_jp16 (DroidSansFallbackFull full-width)
_DEGREE_CHAR_W = 7  # custom ° rendering width


def _char_px_width(ch):
    """Get pixel width for a character as draw_text would render it."""
    if ch == '\u00b0':
        return _DEGREE_CHAR_W
    if ord(ch) > 126:
        return _JP_CHAR_W
    return _ASCII_CHAR_W


def _has_non_ascii(text):
    """Check if text contains any non-ASCII character."""
    for ch in text:
        if ord(ch) > 126:
            return True
    return False


def draw_text(panel, text, x, y, fg_color, bg_color=0):
    """Draw text, auto-selecting the appropriate font per character.

    - ASCII chars: vga1_8x16 at 8px
    - ° (degree sign): custom small circle (font glyph is broken)
    - Other non-ASCII: font_jp16 at 16px
    """
    if not text:
        return
    if not _has_non_ascii(text):
        panel.text(font_ascii, text, x, y, fg_color)
        return
    # Mixed text: render character by character
    for ch in text:
        if ch == '\u00b0':
            # Draw ° as a small hollow rectangle (degree sign)
            panel.rect(x + 1, y + 1, 4, 4, fg_color)
            x += _DEGREE_CHAR_W
        elif ord(ch) <= 126:
            panel.text(font_ascii, ch, x, y, fg_color)
            x += _ASCII_CHAR_W
        else:
            panel.write(font_jp16, ch, x, y, fg_color, bg_color)
            x += _JP_CHAR_W


def wrap_text_jp(text, max_width_px):
    """Wrap text by pixel width with Japanese-aware line breaking.

    Each paragraph (split by newline) is wrapped independently.
    Japanese chars can break at any boundary; ASCII words break at spaces.
    """
    if not text:
        return []

    lines = []
    for paragraph in text.split('\n'):
        if not paragraph:
            lines.append('')
            continue

        non_ascii = _has_non_ascii(paragraph)

        if not non_ascii:
            _wrap_ascii(paragraph, max_width_px, _ASCII_CHAR_W, lines)
        else:
            _wrap_mixed(paragraph, max_width_px, lines)

    return lines


def _wrap_ascii(text, max_w, char_w, lines):
    """Wrap pure ASCII text by words."""
    line = ''
    line_w = 0
    for word in text.split(' '):
        w_w = len(word) * char_w
        if line:
            if line_w + char_w + w_w > max_w:
                lines.append(line)
                line = word
                line_w = w_w
            else:
                line += ' ' + word
                line_w += char_w + w_w
        else:
            line = word
            line_w = w_w
    if line:
        lines.append(line)


def _wrap_mixed(text, max_w, lines):
    """Wrap mixed Japanese/ASCII text with per-character width."""
    line = ''
    line_w = 0
    word = ''
    word_w = 0

    for ch in text:
        ch_w = _char_px_width(ch)
        if ord(ch) > 0x7E and ch != '\u00b0':
            # Non-ASCII (not °): flush pending ASCII word first
            if word:
                if line and line_w + word_w > max_w:
                    lines.append(line)
                    line = word
                    line_w = word_w
                else:
                    line += word
                    line_w += word_w
                word = ''
                word_w = 0
            # Add the Japanese character (can break at any char)
            if line and line_w + ch_w > max_w:
                lines.append(line)
                line = ch
                line_w = ch_w
            else:
                line += ch
                line_w += ch_w
        elif ch == ' ':
            # Space: flush word
            if word:
                if line and line_w + word_w > max_w:
                    lines.append(line)
                    line = word
                    line_w = word_w
                else:
                    line += word
                    line_w += word_w
                word = ''
                word_w = 0
            if line and line_w + ch_w > max_w:
                lines.append(line)
                line = ''
                line_w = 0
            else:
                line += ch
                line_w += ch_w
        else:
            # ASCII or ° : accumulate into word
            word += ch
            word_w += ch_w

    # Flush remaining
    if word:
        if line and line_w + word_w > max_w:
            lines.append(line)
            line = word
        else:
            line += word
    if line:
        lines.append(line)


def truncate_to_width(text, max_px):
    """Truncate text to fit within max_px pixels."""
    if not text:
        return text
    width = 0
    for i, ch in enumerate(text):
        w = _char_px_width(ch)
        if width + w > max_px:
            return text[:i]
        width += w
    return text
