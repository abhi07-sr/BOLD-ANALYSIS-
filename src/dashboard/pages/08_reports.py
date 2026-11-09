"""Screen 8: Annual Reports & Regulatory Filings - Clickable BSE PDF archives and availability verification."""

import os
import sys
from typing import Any

# Ensure workspace root is in sys.path
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

import pandas as pd
import streamlit as st

from src.dashboard.utils.db import clean_company_name, get_annual_reports, get_companies


def _is_valid_url(url: Any) -> bool:
    """Check if the provided URL is a valid web address."""
    if url is None or pd.isna(url):
        return False
    str_url = str(url).strip()
    return str_url.startswith("http://") or str_url.startswith("https://")


def render() -> None:
    """Render the Annual Reports & Regulatory Filings screen."""
    try:
        st.set_page_config(layout="wide", page_title="Nifty 100 - Annual Reports", page_icon="📄")
    except Exception:
        pass

    st.title("📄 Annual Reports & Regulatory Filings Archive")
    st.markdown("Direct access to verified official annual report filings from BSE India and company disclosures.")

    # 1. Company Search & Selection
    companies_df = get_companies()
    if companies_df.empty:
        st.error("No companies found in database.")
        return

    company_options = {f"{r['id']} — {clean_company_name(r['company_name'])}": r["id"] for _, r in companies_df.iterrows()}
    opt_keys = list(company_options.keys())

    default_idx = 0
    if "selected_ticker" in st.session_state and st.session_state.selected_ticker:
        cur_t = st.session_state.selected_ticker
        matches = [i for i, k in enumerate(opt_keys) if company_options[k] == cur_t]
        if matches:
            default_idx = matches[0]

    col_sel, col_links = st.columns([2, 1])
    with col_sel:
        selected_display = st.selectbox(
            "🏢 Select Company (92 Constituents)",
            options=opt_keys,
            index=default_idx,
            help="Select company to view historical annual report filings.",
        )
    ticker = company_options[selected_display]
    st.session_state.selected_ticker = ticker

    company_row = companies_df[companies_df["id"] == ticker].iloc[0]

    # Quick external profile links
    with col_links:
        st.markdown("**Exchange Profiles & Disclosures:**")
        bse_link = company_row.get("bse_profile")
        nse_link = company_row.get("nse_profile")
        website = company_row.get("website")

        links_md = []
        if _is_valid_url(website):
            links_md.append(f"[🌐 Official Website]({website})")
        if _is_valid_url(bse_link):
            links_md.append(f"[🏛️ BSE Profile]({bse_link})")
        if _is_valid_url(nse_link):
            links_md.append(f"[📈 NSE Profile]({nse_link})")

        if links_md:
            st.markdown(" • ".join(links_md))
        else:
            st.caption("No direct exchange profiles registered.")

    st.markdown("---")

    # 2. Historical Annual Report Documents
    docs_df = get_annual_reports(ticker)
    st.subheader(f"📑 Annual Reports History: {clean_company_name(company_row['company_name'])} (`{ticker}`)")

    if docs_df.empty:
        st.warning(f"No document filings found in database for `{ticker}`.")
        return

    total_reports = len(docs_df)
    valid_reports = docs_df["url"].apply(_is_valid_url).sum()

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Total Document Filings", f"{total_reports}")
    with m2:
        st.metric("Direct PDF Downloads Available", f"{valid_reports}")
    with m3:
        unavailable_cnt = total_reports - valid_reports
        st.metric("Unavailable / Archived Filings", f"{unavailable_cnt}")

    st.markdown("---")

    # Display documents as clean interactive table with links / badges
    rows = []
    for _, doc in docs_df.iterrows():
        year_str = str(doc["year"])
        url = doc.get("url")
        if _is_valid_url(url):
            link_markdown = f'<a href="{url}" target="_blank" style="text-decoration: none; color: #2563eb; font-weight: 600;">📥 Open FY{year_str} Annual Report (PDF)</a>'
            status_badge = "🟢 Available"
        else:
            link_markdown = '<span style="color: #dc2626; font-weight: 600; background-color: #fee2e2; padding: 2px 8px; border-radius: 4px;">❌ Report unavailable</span>'
            status_badge = "🔴 Unavailable"

        rows.append(
            {
                "Fiscal Year": f"FY {year_str}",
                "Filing Description": f"{clean_company_name(company_row['company_name'])} Annual Report {year_str}",
                "Status": status_badge,
                "Access Link": link_markdown,
            }
        )

    table_data = pd.DataFrame(rows)

    # Render table with HTML enabled for clickable links and badges
    st.write(
        table_data.to_html(escape=False, index=False),
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    render()

