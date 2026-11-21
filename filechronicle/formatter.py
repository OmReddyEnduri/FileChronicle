"""Terminal formatting, ANSI colors, and output presentation."""

import os
import sys
from typing import List, Optional


# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
UNDERLINE = "\033[4m"

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
GRAY = "\033[90m"

BG_RED = "\033[41m"
BG_GREEN = "\033[42m"


def supports_color() -> bool:
    """Check if the current terminal supports ANSI colors."""
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    return True


USE_COLOR = supports_color()


def colorize(text: str, color_code: str) -> str:
    if not USE_COLOR:
        return text
    return f"{color_code}{text}{RESET}"


def format_size(num_bytes: int) -> str:
    """Format byte count into human-readable string (KB, MB, GB)."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    for unit in ["KB", "MB", "GB", "TB"]:
        num_bytes /= 1024.0
        if num_bytes < 1024.0 or unit == "TB":
            return f"{num_bytes:.1f} {unit}"
    return f"{num_bytes:.1f} PB"


def format_diff(diff_text: str) -> str:
    """Colorize a unified diff for terminal display."""
    if not diff_text:
        return ""
    if not USE_COLOR:
        return diff_text

    lines = diff_text.splitlines()
    colored_lines = []
    for line in lines:
        if line.startswith("+++") or line.startswith("---"):
            colored_lines.append(colorize(line, BOLD))
        elif line.startswith("@@"):
            colored_lines.append(colorize(line, CYAN))
        elif line.startswith("+"):
            colored_lines.append(colorize(line, GREEN))
        elif line.startswith("-"):
            colored_lines.append(colorize(line, RED))
        else:
            colored_lines.append(line)
    return "\n".join(colored_lines)


def render_table(headers: List[str], rows: List[List[str]], alignments: Optional[List[str]] = None) -> str:
    """
    Render clean ASCII / ANSI tabular output.
    alignments: list of 'L' or 'R' (default: 'L')
    """
    if not rows:
        return ""

    num_cols = len(headers)
    col_widths = [len(h) for h in headers]

    for row in rows:
        for idx in range(min(len(row), num_cols)):
            # Strip ANSI codes for length calculation
            plain_val = _strip_ansi(str(row[idx]))
            col_widths[idx] = max(col_widths[idx], len(plain_val))

    if not alignments:
        alignments = ["L"] * num_cols

    # Build header
    header_cells = []
    for idx, h in enumerate(headers):
        w = col_widths[idx]
        cell = h.ljust(w) if alignments[idx] == "L" else h.rjust(w)
        header_cells.append(colorize(cell, BOLD + CYAN))
    header_line = "  " + "   ".join(header_cells)

    separator_cells = ["-" * w for w in col_widths]
    separator_line = "  " + "   ".join(colorize(s, GRAY) for s in separator_cells)

    # Build rows
    row_lines = []
    for row in rows:
        row_cells = []
        for idx in range(num_cols):
            val = str(row[idx]) if idx < len(row) else ""
            plain_val = _strip_ansi(val)
            pad_len = col_widths[idx] - len(plain_val)
            if alignments[idx] == "L":
                padded = val + (" " * pad_len)
            else:
                padded = (" " * pad_len) + val
            row_cells.append(padded)
        row_lines.append("  " + "   ".join(row_cells))

    return "\n".join([header_line, separator_line] + row_lines)


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from string for visual length calculations."""
    import re
    ansi_regex = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_regex.sub("", text)
