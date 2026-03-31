"""
Client Import & Reconciliation Tool

A Streamlit app that:
  1. Converts client timesheet files to the standard import format.
  2. Reconciles converted data against the system export using fuzzy name matching.
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from converter import convert, list_templates, aggregate_by_name_date
from reconciler import load_system_export, reconcile

st.set_page_config(
    page_title="Client Import & Reconciliation",
    page_icon="📋",
    layout="wide",
)


def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def _to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
    return buf.getvalue()


def _color_status(val):
    colors = {
        "Matched": "background-color: #d4edda",
        "Hours Mismatch": "background-color: #fff3cd",
        "Missing in System": "background-color: #f8d7da",
        "Missing in Client File": "background-color: #d6d8db",
    }
    return colors.get(val, "")


# ── Sidebar ──────────────────────────────────────────────────────────────
st.sidebar.title("Settings")
template_name = st.sidebar.selectbox(
    "Client File Template",
    list_templates(),
    help="Select the format that matches the client file you're uploading.",
)
match_threshold = st.sidebar.slider(
    "Name Match Threshold",
    min_value=0.60,
    max_value=1.00,
    value=0.82,
    step=0.01,
    help="Minimum similarity score for fuzzy name matching. Lower = more lenient.",
)

# ── Header ───────────────────────────────────────────────────────────────
st.title("Client Import & Reconciliation")
st.markdown(
    "Upload a **client timesheet file** to convert it to the standard import format. "
    "Optionally add the **system export** to reconcile hours."
)

# ── Step 1: Upload & Convert ─────────────────────────────────────────────
st.header("Step 1 — Convert Client File")
client_file = st.file_uploader(
    "Upload Client File",
    type=["csv", "xls", "xlsx"],
    key="client_file",
)

if client_file is not None:
    file_bytes = client_file.read()

    with st.spinner("Converting..."):
        try:
            converted = convert(file_bytes, client_file.name, template_name)
        except Exception as e:
            st.error(f"Conversion failed: {e}")
            st.stop()

    st.success(f"Converted {len(converted)} rows from **{client_file.name}**")

    aggregated = aggregate_by_name_date(converted)

    tab_raw, tab_agg = st.tabs(["All Rows", "Aggregated (per person per day)"])
    with tab_raw:
        st.dataframe(converted, use_container_width=True, height=400)
    with tab_agg:
        st.dataframe(aggregated, use_container_width=True, height=400)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Download Import CSV",
            data=_to_csv_bytes(aggregated),
            file_name=f"import_{client_file.name.rsplit('.', 1)[0]}.csv",
            mime="text/csv",
        )
    with col2:
        st.download_button(
            "Download Import Excel",
            data=_to_excel_bytes(aggregated),
            file_name=f"import_{client_file.name.rsplit('.', 1)[0]}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # ── Step 2: Reconcile ────────────────────────────────────────────────
    st.header("Step 2 — Reconcile with System Export")
    sys_file = st.file_uploader(
        "Upload System Export (CSV/Excel)",
        type=["csv", "xls", "xlsx"],
        key="sys_file",
    )

    if sys_file is not None:
        sys_bytes = sys_file.read()

        with st.spinner("Running reconciliation..."):
            try:
                sys_df = load_system_export(sys_bytes, sys_file.name)
                recon_df, summary_df = reconcile(
                    aggregated, sys_df, threshold=match_threshold,
                )
            except Exception as e:
                st.error(f"Reconciliation failed: {e}")
                st.stop()

        # Summary metrics
        total_rows = len(recon_df)
        matched = len(recon_df[recon_df["Status"] == "Matched"])
        mismatched = len(recon_df[recon_df["Status"] == "Hours Mismatch"])
        missing_sys = len(recon_df[recon_df["Status"] == "Missing in System"])
        missing_client = len(recon_df[recon_df["Status"] == "Missing in Client File"])

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Matched", matched)
        m2.metric("Hours Mismatch", mismatched)
        m3.metric("Missing in System", missing_sys)
        m4.metric("Missing in Client", missing_client)

        tab_recon, tab_summary = st.tabs(["Detail", "Person Summary"])
        with tab_recon:
            styled = recon_df.style.map(_color_status, subset=["Status"])
            st.dataframe(styled, use_container_width=True, height=500)
        with tab_summary:
            st.dataframe(summary_df, use_container_width=True, height=400)

        st.download_button(
            "Download Reconciliation Excel",
            data=_to_excel_bytes(recon_df),
            file_name=f"recon_{client_file.name.rsplit('.', 1)[0]}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
else:
    st.info("Upload a client file above to get started.")
