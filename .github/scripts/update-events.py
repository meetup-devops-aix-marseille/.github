#!/usr/bin/env python3
"""Update website/events.md with a new or updated meetup event entry."""

import os
import re
import sys
from datetime import datetime

MONTHS_FR = {
    1: "Janvier",
    2: "Février",
    3: "Mars",
    4: "Avril",
    5: "Mai",
    6: "Juin",
    7: "Juillet",
    8: "Août",
    9: "Septembre",
    10: "Octobre",
    11: "Novembre",
    12: "Décembre",
}

MONTH_ORDER = list(MONTHS_FR.values())

TABLE_HEADER = "| Mois | Date | Titre | Lieu |"
TABLE_SEP = "| ---- | ---- | ----- | ---- |"
EVENTS_FILE = os.environ.get("EVENTS_FILE", "website/events.md")


def make_row(month_name: str, date: str, title: str, hosting: str, link: str) -> str:
    date_cell = f"[{date}]({link})" if link else date
    return f"| {month_name} | {date_cell} | {title} | {hosting} |"


def find_year_section(lines: list[str], year: str) -> int | None:
    """Return the index of the '## YEAR' header line, or None if not found."""
    header = f"## {year}"
    for i, line in enumerate(lines):
        if line.strip() == header:
            return i
    return None


def find_table_bounds(lines: list[str], year_idx: int) -> tuple[int | None, int]:
    """Return (table_start, table_end) within the year section.

    table_start is the index of the first '| ...' line after the year header.
    table_end is the index of the first line after the table (exclusive).
    """
    table_start = None
    table_end = len(lines)
    for i in range(year_idx + 1, len(lines)):
        line = lines[i].strip()
        if re.match(r"^## \d{4}$", line):
            table_end = i
            break
        if table_start is None and line.startswith("|"):
            table_start = i
    if table_start is not None and table_end == len(lines):
        # Trim trailing blank lines
        for i in range(len(lines) - 1, table_start, -1):
            if lines[i].strip():
                table_end = i + 1
                break
    return table_start, table_end


def find_month_row(lines: list[str], table_start: int, table_end: int, month_name: str, date: str) -> int | None:
    """Return the index of the row matching the month/date, or None."""
    # Build a pattern that matches the date as a full token in the markdown link or plain text
    date_pattern = re.compile(r"(?<!\d)" + re.escape(date) + r"(?!\d)")
    for i in range(table_start + 2, table_end):  # skip header and separator
        line = lines[i]
        if not line.strip().startswith("|"):
            break
        # Match by month name (first cell) or by exact date string in the date cell
        cells = [c.strip() for c in line.split("|")]
        if len(cells) >= 2 and (cells[1] == month_name or date_pattern.search(cells[2])):
            return i
    return None


def insert_row_sorted(lines: list[str], table_start: int, table_end: int, new_row: str, month_name: str) -> list[str]:
    """Insert new_row in the correct month-order position within the table."""
    month_idx = MONTH_ORDER.index(month_name)
    insert_at = table_end  # default: append at end of table

    for i in range(table_start + 2, table_end):
        line = lines[i]
        if not line.strip().startswith("|"):
            insert_at = i
            break
        cells = [c.strip() for c in line.split("|")]
        if len(cells) >= 2:
            row_month = cells[1]
            row_idx = MONTH_ORDER.index(row_month) if row_month in MONTH_ORDER else -1
            if row_idx > month_idx:
                insert_at = i
                break

    lines.insert(insert_at, new_row)
    return lines


def frontmatter_end(lines: list[str]) -> int:
    """Return the line index just after the closing '---' of front matter."""
    if not lines or lines[0].strip() != "---":
        return 0
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return i + 1
    return 0


def update_events(date: str, title: str, hosting: str, link: str) -> None:
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    year = str(dt.year)
    month_name = MONTHS_FR[dt.month]
    new_row = make_row(month_name, date, title, hosting, link)

    with open(EVENTS_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    trailing_newline = content.endswith("\n")
    lines = content.split("\n")

    year_idx = find_year_section(lines, year)

    if year_idx is None:
        # Create a new year section inserted before the previous year's section
        # (so years are in descending order)
        new_section_lines = [
            "",
            f"## {year}",
            "",
            TABLE_HEADER,
            TABLE_SEP,
            new_row,
        ]

        first_year_idx = None
        for i, line in enumerate(lines):
            if re.match(r"^## \d{4}$", line.strip()):
                first_year_idx = i
                break

        if first_year_idx is not None:
            lines = lines[:first_year_idx] + new_section_lines + [""] + lines[first_year_idx:]
        else:
            fm_end = frontmatter_end(lines)
            lines = lines[:fm_end] + new_section_lines + lines[fm_end:]
    else:
        table_start, table_end = find_table_bounds(lines, year_idx)

        if table_start is None:
            # No table yet — add one right after the year header
            blank_lines_after = 0
            for i in range(year_idx + 1, len(lines)):
                if lines[i].strip():
                    break
                blank_lines_after += 1
            insert_pos = year_idx + 1 + blank_lines_after
            lines = lines[:insert_pos] + [TABLE_HEADER, TABLE_SEP, new_row, ""] + lines[insert_pos:]
        else:
            # Migrate old header format if needed (e.g., "Date cible" → "Date", add "Titre")
            header = lines[table_start]
            cols = [c.strip() for c in header.split("|") if c.strip()]
            if "Titre" not in cols:
                lines[table_start] = TABLE_HEADER
                lines[table_start + 1] = TABLE_SEP
                # Migrate existing data rows: old format | Mois | Date | Lieu |
                # → new format | Mois | Date | Titre | Lieu |
                for i in range(table_start + 2, table_end):
                    row = lines[i]
                    if not row.strip().startswith("|"):
                        break
                    row_cells = row.split("|")
                    # row_cells[0] is empty (before first |)
                    # row_cells[-1] is empty (after last |)
                    # For old 3-col table: ['', ' Mois ', ' Date ', ' Lieu ', '']
                    if len(row_cells) == 5:  # 3 data columns
                        mois = row_cells[1].strip()
                        date_val = row_cells[2].strip()
                        lieu = row_cells[3].strip()
                        lines[i] = f"| {mois} | {date_val} | | {lieu} |"

            month_row_idx = find_month_row(lines, table_start, table_end, month_name, date)
            if month_row_idx is not None:
                lines[month_row_idx] = new_row
            else:
                lines = insert_row_sorted(lines, table_start, table_end, new_row, month_name)

    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        result = "\n".join(lines)
        if trailing_newline and not result.endswith("\n"):
            result += "\n"
        f.write(result)

    print(f"Updated {EVENTS_FILE}: {date} | {title} | {hosting} | {link}")


if __name__ == "__main__":
    event_date = os.environ.get("EVENT_DATE", "").strip()
    event_title = os.environ.get("EVENT_TITLE", "").strip()
    event_hosting = os.environ.get("EVENT_HOSTING", "").strip()
    event_link = os.environ.get("EVENT_LINK", "").strip()

    if not event_date:
        print("ERROR: EVENT_DATE environment variable is required", file=sys.stderr)
        sys.exit(1)
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", event_date):
        print(f"ERROR: EVENT_DATE must be in YYYY-MM-DD format, got: {event_date}", file=sys.stderr)
        sys.exit(1)

    update_events(event_date, event_title, event_hosting, event_link)
