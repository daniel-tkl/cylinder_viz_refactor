from __future__ import annotations

import os

import streamlit as st

from src.shared.view import local_css, set_bg


_PAGE_STYLE = """
<style>
[data-testid="stAppViewContainer"] {
    background: transparent !important;
}

header[data-testid="stHeader"] {
    background: rgba(0, 0, 0, 0);
}

[data-testid="stToolbar"] {
    right: 0.65rem;
}
</style>
"""

_HIDE_STREAMLIT_STYLE = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""

_PLOTLY_HOVER_STYLE = """
<style>
.js-plotly-plot .hoverlayer {overflow: visible !important;}
</style>
"""


def initialize_app_bootstrap() -> None:
    st.set_page_config(
        page_title="Cylinder Data Viz",
        page_icon="assets/favicon.ico",
        layout="wide",
    )
    st.markdown(_PAGE_STYLE, unsafe_allow_html=True)
    st.markdown(_HIDE_STREAMLIT_STYLE, unsafe_allow_html=True)
    st.markdown(_PLOTLY_HOVER_STYLE, unsafe_allow_html=True)

    css_path = os.path.join("assets", "custom.css")
    bg_path = os.path.join("assets", "bg.png")
    set_bg(bg_path)
    local_css(css_path)

    st.markdown(
        "<div class='app-title'><span>Cylinder Data Application</span></div>",
        unsafe_allow_html=True,
    )
