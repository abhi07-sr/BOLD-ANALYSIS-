"""Main entry point for the Nifty 100 Financial Analytics Streamlit dashboard."""

import os
import sys

# Ensure workspace root is in sys.path
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

import streamlit as st

st.set_page_config(
    layout="wide",
    page_title="Nifty 100 Analytics",
    page_icon="📈",
    initial_sidebar_state="expanded",
)

# Define all 8 pages using st.Page
pages_dir = os.path.join(os.path.dirname(__file__), "pages")

pages = [
    st.Page(os.path.join(pages_dir, "01_home.py"), title="Home / Macro Overview", icon="🏛️", default=True),
    st.Page(os.path.join(pages_dir, "02_profile.py"), title="Company Profile", icon="🏢"),
    st.Page(os.path.join(pages_dir, "03_screener.py"), title="Financial Screener", icon="🔍"),
    st.Page(os.path.join(pages_dir, "04_peers.py"), title="Peer Comparison", icon="👥"),
    st.Page(os.path.join(pages_dir, "05_trends.py"), title="Trend Analysis", icon="📈"),
    st.Page(os.path.join(pages_dir, "06_sectors.py"), title="Sector Deep-Dive", icon="🏭"),
    st.Page(os.path.join(pages_dir, "07_capital.py"), title="Capital Allocation", icon="💰"),
    st.Page(os.path.join(pages_dir, "08_reports.py"), title="Annual Reports & Filings", icon="📄"),
]

# Sidebar branding header
with st.sidebar:
    st.markdown("### 🏛️ Nifty 100 Analytics")
    st.caption("Institutional Financial Intelligence System")
    st.markdown("---")

nav = st.navigation(pages)

# Sidebar metadata footer
with st.sidebar:
    st.markdown("---")
    st.caption("📦 92 Constituents | 10 Financial Years")
    st.caption("⚡ Powered by SQLite + Streamlit + Plotly")

nav.run()

