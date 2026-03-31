"""
Reconciliation engine.

Joins converted client data with the system export using fuzzy name matching,
then flags discrepancies in hours.
"""

from __future__ import annotations

import pandas as pd

from name_matcher import match_one, MatchResult

from templates import SYSTEM_EXPORT_COLUMNS

HOURS_TOLERANCE = 0.25


def load_system_export(file_bytes: bytes, filename: str) -> pd.DataFrame:
    from io import BytesIO
    buf = BytesIO(file_bytes)
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "csv":
        df = pd.read_csv(buf)
    elif ext == "xls":
        df = pd.read_excel(buf, engine="xlrd")
    else:
        df = pd.read_excel(buf, engine="openpyxl")
    return df


def _build_system_daily(sys_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate system export to one row per name per date."""
    cols = SYSTEM_EXPORT_COLUMNS
    out = sys_df.rename(columns={
        cols["date"]: "sys_date",
        cols["name"]: "sys_name",
        cols["total_hours"]: "sys_hours",
    })
    out = out[["sys_date", "sys_name", "sys_hours"]].copy()
    out["sys_hours"] = pd.to_numeric(out["sys_hours"], errors="coerce").fillna(0)
    out = out.groupby(["sys_date", "sys_name"], as_index=False).agg({"sys_hours": "sum"})
    out["sys_hours"] = out["sys_hours"].round(2)
    return out


def _build_name_lookup(sys_df: pd.DataFrame) -> list[dict]:
    """Build unique candidate list for name matching."""
    names = sys_df["sys_name"].dropna().unique()
    return [{"name": n} for n in names]


def reconcile(
    client_df: pd.DataFrame,
    sys_df: pd.DataFrame,
    threshold: float = 0.82,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Match and compare hours.

    Returns:
        recon_df: Full reconciliation with match status and hour differences.
        summary_df: Per-person summary (total hours, match quality).
    """
    sys_daily = _build_system_daily(sys_df)
    candidates = _build_name_lookup(sys_daily)

    name_cache: dict[str, MatchResult] = {}

    def match_name(first: str, last: str) -> MatchResult:
        full = f"{first} {last}".strip()
        if full in name_cache:
            return name_cache[full]
        result = match_one(full, candidates, threshold=threshold)
        name_cache[full] = result
        return result

    recon_rows = []
    for _, cr in client_df.iterrows():
        first = str(cr.get("First Name", "")).strip()
        last = str(cr.get("Last Name", "")).strip()
        shift_date = str(cr.get("Shift Date", "")).strip()
        client_hours = float(cr.get("Total Hours", 0))

        m = match_name(first, last)

        sys_row = None
        if m.found:
            mask = (sys_daily["sys_name"] == m.matched_name) & (sys_daily["sys_date"] == shift_date)
            matches = sys_daily[mask]
            if not matches.empty:
                sys_row = matches.iloc[0]

        sys_hours = float(sys_row["sys_hours"]) if sys_row is not None else None
        diff = round(client_hours - sys_hours, 2) if sys_hours is not None else None

        if sys_hours is None:
            status = "Missing in System"
        elif abs(diff) <= HOURS_TOLERANCE:
            status = "Matched"
        else:
            status = "Hours Mismatch"

        recon_rows.append({
            "Shift Date": shift_date,
            "Client Name": f"{first} {last}",
            "System Name": m.matched_name or "",
            "Match Score": round(m.score, 3),
            "Match Method": m.method,
            "Client Hours": client_hours,
            "System Hours": sys_hours if sys_hours is not None else "",
            "Difference": diff if diff is not None else "",
            "Status": status,
        })

    recon_df = pd.DataFrame(recon_rows)

    unmatched_sys = set(sys_daily["sys_name"].unique()) - set(name_cache.get(k, MatchResult(input_name="")).matched_name or "" for k in name_cache)
    matched_sys_names = {r.matched_name for r in name_cache.values() if r.found}
    all_sys_names = set(sys_daily["sys_name"].unique())
    missing_from_client = all_sys_names - matched_sys_names

    for sys_name in missing_from_client:
        name_rows = sys_daily[sys_daily["sys_name"] == sys_name]
        for _, sr in name_rows.iterrows():
            recon_rows.append({
                "Shift Date": sr["sys_date"],
                "Client Name": "",
                "System Name": sys_name,
                "Match Score": 0,
                "Match Method": "none",
                "Client Hours": "",
                "System Hours": sr["sys_hours"],
                "Difference": "",
                "Status": "Missing in Client File",
            })

    recon_df = pd.DataFrame(recon_rows)

    summary_rows = []
    for full_name, result in name_cache.items():
        client_total = client_df[
            (client_df["First Name"] + " " + client_df["Last Name"]).str.strip() == full_name
        ]["Total Hours"].sum()
        sys_total = 0.0
        if result.found:
            sys_total = sys_daily[sys_daily["sys_name"] == result.matched_name]["sys_hours"].sum()

        summary_rows.append({
            "Client Name": full_name,
            "System Name": result.matched_name or "",
            "Match Score": round(result.score, 3),
            "Match Method": result.method,
            "Client Total Hours": round(client_total, 2),
            "System Total Hours": round(sys_total, 2),
            "Difference": round(client_total - sys_total, 2),
        })

    for sys_name in missing_from_client:
        sys_total = sys_daily[sys_daily["sys_name"] == sys_name]["sys_hours"].sum()
        summary_rows.append({
            "Client Name": "",
            "System Name": sys_name,
            "Match Score": 0,
            "Match Method": "none",
            "Client Total Hours": 0,
            "System Total Hours": round(sys_total, 2),
            "Difference": round(-sys_total, 2),
        })

    summary_df = pd.DataFrame(summary_rows)
    return recon_df, summary_df
