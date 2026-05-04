"""
CSS loader.

Keep ALL CSS in assets/styles/style.css.
app.py should only call process_styles() to inject that CSS into Streamlit.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from ai_datanalysis.paths import STYLE_CSS_PATH


def process_styles(css_path: str | None = None) -> None:
    """
    Inject CSS into Streamlit from an external file.

    - No fragile Streamlit auto-generated class selectors.
    - If the file is missing, we simply skip (app still runs).
    """
    resolved_path = STYLE_CSS_PATH if css_path is None else Path(css_path)
    if not resolved_path.exists():
        # Don't crash the app if CSS file is missing
        return

    with open(resolved_path, "r", encoding="utf-8") as f:
        css = f.read()

    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
