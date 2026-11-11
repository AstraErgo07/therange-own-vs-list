"""
streamlit_app.py - entry point for the Own vs List app (The Range, part of CDS).

Run locally:  streamlit run streamlit_app.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="Own vs List (The Range)", layout="wide")

from common.nav import footer  # noqa: E402

nav = st.navigation({
    "Own vs List": [st.Page("app_pages/cds_own_vs_list_page.py", title="Own vs List (The Range)", default=True)],
    "About": [st.Page("app_pages/method_page.py", title="Data and method", url_path="data-and-method")],
})
nav.run()
footer()
