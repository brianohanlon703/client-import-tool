"""
Convert client files to the standard import format.

Standard output columns:
  Shift Date | First Name | Last Name | Total Hours
  (optionally: Clock In | Clock Out)
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from io import BytesIO

import pandas as pd

from templates import TEMPLATES, DAY_OFFSETS_SAT_ENDING


def list_templates() -> list[str]:
    return list(TEMPLATES.keys())


def convert(file_bytes: bytes, filename: str, template_name: str) -> pd.DataFrame:
    """Convert an uploaded client file to standard import format."""
    tmpl = TEMPLATES[template_name]
    layout = tmpl["layout"]

    if layout == "horizontal":
        return _convert_horizontal(file_bytes, filename, tmpl)
    if layout == "week_days":
        return _convert_week_days(file_bytes, filename, tmpl)
    raise ValueError(f"Unknown layout: {layout}")


def _read_file(file_bytes: bytes, filename: str, header_row: int) -> pd.DataFrame:
    ext = filename.rsplit(".", 1)[-1].lower()
    buf = BytesIO(file_bytes)
    if ext == "csv":
        return pd.read_csv(buf, header=header_row)
    if ext == "xls":
        return pd.read_excel(buf, header=header_row, engine="xlrd")
    return pd.read_excel(buf, header=header_row, engine="openpyxl")


def _read_raw(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Read without treating any row as header (for cell lookups)."""
    ext = filename.rsplit(".", 1)[-1].lower()
    buf = BytesIO(file_bytes)
    if ext == "csv":
        return pd.read_csv(buf, header=None)
    if ext == "xls":
        return pd.read_excel(buf, header=None, engine="xlrd")
    return pd.read_excel(buf, header=None, engine="openpyxl")


def _split_name(full_name: str, order: str, strip_digits: bool = False) -> tuple[str, str]:
    """Split a full name into (first, last)."""
    name = str(full_name).strip()
    if strip_digits:
        name = re.sub(r"^\d+", "", name).strip()

    if order == "last_first" and "," in name:
        parts = [p.strip() for p in name.split(",", 1)]
        return parts[1], parts[0]

    parts = name.split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _parse_hours(val) -> float:
    if pd.isna(val):
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _strip_tz(s: str) -> str:
    """Remove trailing timezone abbreviation (e.g. CDT, EST, PST)."""
    return re.sub(r"\s+[A-Z]{2,5}$", "", s.strip())


_DATE_FORMATS = [
    "%m/%d/%Y",
    "%m/%d/%y",
    "%Y-%m-%d",
    "%m-%d-%Y",
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%Y %H:%M",
    "%m/%d/%y %I:%M %p",
    "%m/%d/%y %H:%M",
    "%m/%d/%Y %I:%M:%S %p",
    "%m/%d/%y %I:%M:%S %p",
    "%Y-%m-%dT%H:%M:%S",
]


def _parse_date(val) -> str | None:
    """Parse various date representations to MM/DD/YYYY."""
    if pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val.strftime("%m/%d/%Y")
    s = _strip_tz(str(val))
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime("%m/%d/%Y")
        except ValueError:
            continue
    return None


def _parse_datetime(val) -> datetime | None:
    if pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val
    s = _strip_tz(str(val))
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _is_skip_row(name_val) -> bool:
    """Return True for rows that should be filtered out."""
    if pd.isna(name_val):
        return True
    s = str(name_val).strip().lower()
    if s in ("", "total", "totals", "grand total"):
        return True
    if s.endswith(" total") or s.endswith(" totals"):
        return True
    return False


def _convert_horizontal(file_bytes: bytes, filename: str, tmpl: dict) -> pd.DataFrame:
    df = _read_file(file_bytes, filename, tmpl["header_row"])
    cols = tmpl["columns"]
    order = tmpl.get("name_order", "first_last")
    strip_digits = tmpl.get("strip_leading_digits", False)
    dt_in_clock = tmpl.get("datetime_in_clock", False)

    rows = []
    for _, r in df.iterrows():
        raw_name = r.get(cols["full_name"])
        if _is_skip_row(raw_name):
            continue

        first, last = _split_name(raw_name, order, strip_digits)

        if dt_in_clock and "clock_in" in cols:
            shift_date = _parse_date(r.get(cols["clock_in"]))
        else:
            shift_date = _parse_date(r.get(cols.get("shift_date", "")))

        hours = _parse_hours(r.get(cols.get("total_hours", "")))

        row = {
            "Shift Date": shift_date or "",
            "First Name": first,
            "Last Name": last,
            "Total Hours": hours,
        }

        if "clock_in" in cols:
            cin = _parse_datetime(r.get(cols["clock_in"]))
            cout = _parse_datetime(r.get(cols["clock_out"]))
            row["Clock In"] = cin.strftime("%m/%d/%Y %I:%M %p") if cin else ""
            row["Clock Out"] = cout.strftime("%m/%d/%Y %I:%M %p") if cout else ""

        rows.append(row)

    return pd.DataFrame(rows)


def _convert_week_days(file_bytes: bytes, filename: str, tmpl: dict) -> pd.DataFrame:
    df = _read_file(file_bytes, filename, tmpl["header_row"])
    raw_df = _read_raw(file_bytes, filename)

    cols = tmpl["columns"]
    day_cols = tmpl["day_columns"]
    order = tmpl.get("name_order", "first_last")

    we_cell = tmpl.get("week_ending_cell")
    week_ending: datetime | None = None
    if we_cell:
        we_val = raw_df.iat[we_cell["row"], we_cell["col"]]
        if isinstance(we_val, datetime):
            week_ending = we_val
        elif we_val:
            d = _parse_date(we_val)
            if d:
                week_ending = datetime.strptime(d, "%m/%d/%Y")

    rows = []
    for _, r in df.iterrows():
        raw_name = r.get(cols["full_name"])
        if _is_skip_row(raw_name):
            continue

        first, last = _split_name(raw_name, order)

        for day_name, col_name in day_cols.items():
            hours = _parse_hours(r.get(col_name))
            if hours == 0.0:
                continue

            shift_date = ""
            if week_ending:
                offset = DAY_OFFSETS_SAT_ENDING.get(day_name, 0)
                dt = week_ending + timedelta(days=offset)
                shift_date = dt.strftime("%m/%d/%Y")

            rows.append({
                "Shift Date": shift_date,
                "First Name": first,
                "Last Name": last,
                "Total Hours": hours,
            })

    return pd.DataFrame(rows)


def aggregate_by_name_date(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate converted rows so there's one row per person per date."""
    if df.empty:
        return df
    group_cols = ["Shift Date", "First Name", "Last Name"]
    agg = df.groupby(group_cols, as_index=False).agg({"Total Hours": "sum"})
    agg["Total Hours"] = agg["Total Hours"].round(2)
    return agg
