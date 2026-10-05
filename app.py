"""
Media Ecosystem Atlas — auto-reload edition
============================================

Edit the two CSV files in the `data/` folder, then refresh the browser.
That's the whole workflow. No buttons, no uploads — just save and refresh.

The app reads the files fresh whenever they change on disk (it watches the
file modification time), so a refresh after a save always reflects the edits.

Run with:   streamlit run app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import pipeline as P

st.set_page_config(page_title="Media Ecosystem Atlas", page_icon="🗺️", layout="wide")

ROOT = Path(__file__).parent
TEMPLATE_PATH = ROOT / "index.html"
EUR_CSV = ROOT / "data" / "european_media_outlets.csv"
ECO_CSV = ROOT / "data" / "wider_media_ecosystem.csv"

# Make the embedded dashboard fill the window, no Streamlit chrome on top.
st.markdown(
    """
    <style>
      header[data-testid="stHeader"] {height: 0; visibility: hidden;}
      .block-container {padding: 0 !important; max-width: 100% !important;}
      [data-testid="stSidebar"] {display: none;}
      footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------------------- 
# Read CSVs from disk and build the dashboard data.
#
# The cache is keyed on the file modification times, so:
#   - file unchanged → cache hit → instant load
#   - file edited and saved → mtime changes → cache miss → fresh read
# Effectively: refresh the browser after saving the CSV and the dashboard updates.
# ----------------------------------------------------------------------------- 
@st.cache_data(show_spinner=False)
def render_dashboard(eur_mtime: float, eco_mtime: float) -> str:
    df_eur = pd.read_csv(EUR_CSV)
    df_eco = pd.read_csv(ECO_CSV)
    raw = P.build_full_raw(df_eur, df_eco)
    raw_js = json.dumps(raw, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE_PATH.read_text(encoding="utf-8").replace("__RAW_JSON__", raw_js)


eur_mtime = EUR_CSV.stat().st_mtime
eco_mtime = ECO_CSV.stat().st_mtime
html = render_dashboard(eur_mtime, eco_mtime)

components.html(html, height=1000, scrolling=True)
