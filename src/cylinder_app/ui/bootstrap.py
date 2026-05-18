from __future__ import annotations

import os

import streamlit as st

from src.shared.view import local_css, set_bg, set_sidebar_img


_PAGE_STYLE = """
<style>
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(circle at 12% 8%, rgba(92, 197, 205, 0.2), rgba(24, 33, 54, 0) 38%),
        radial-gradient(circle at 78% 0%, rgba(92, 197, 205, 0.08), rgba(24, 33, 54, 0) 28%);
}

[data-testid="stSidebar"] > div:first-child {
    background-image:
        linear-gradient(160deg, rgba(8, 22, 43, 0.86), rgba(16, 33, 58, 0.75)),
        url("https://wallpapers.com/images/high/dark-blue-background-high-technology-system-4w0bkhpndvqm4ayb.webp");
    background-size: cover;
    background-position: center;
    border-right: 1px solid rgba(92, 197, 205, 0.35);
    box-shadow: inset -1px 0 0 rgba(92, 197, 205, 0.22), 0 0 24px rgba(92, 197, 205, 0.06);
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
    local_css(css_path)
    set_bg(bg_path)
    set_sidebar_img()

    st.markdown(
        "<div class='app-title'><span>Cylinder Data Application</span></div>",
        unsafe_allow_html=True,
    )
