from __future__ import annotations

import os

import streamlit as st

from .assets import read_file_base64, read_text_file

DEFAULT_SIDEBAR_IMAGE = "./assets/dx_logo.png"


def local_css(file_name: str) -> None:
    css_text = read_text_file(file_name)
    st.markdown(f"<style>{css_text}</style>", unsafe_allow_html=True)


@st.cache_data()
def get_base64_of_bin_file(bin_file: str) -> str:
    return read_file_base64(bin_file)


def set_bg(png_file: str) -> None:
    bin_str = get_base64_of_bin_file(png_file)
    page_bg_img = """
    <style>
    html,
    body,
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stAppViewContainer"] .main,
    .appview-container > section[tabindex="0"] {
        background: url("data:image/png;base64,%s") center / cover no-repeat fixed !important;
        background-color: #0d1b34 !important;
    }

    [data-testid="stMain"] > div,
    [data-testid="stMainBlockContainer"] {
        background: transparent !important;
        background-color: transparent !important;
    }
    </style>
    """ % bin_str
    st.markdown(page_bg_img, unsafe_allow_html=True)


def set_sidebar_img(sidebar_img: str | None = DEFAULT_SIDEBAR_IMAGE) -> None:
    if not sidebar_img or not os.path.exists(sidebar_img):
        return

    data = read_file_base64(sidebar_img)
    st.sidebar.markdown(
        f"""
        <div style="display:table;margin-top:-30px;margin-bottom:30px;margin-left:25%;">
            <img src="data:image/png;base64,{data}" style="width:70%;height:auto;display:block;">
        </div>
        """,
        unsafe_allow_html=True,
    )
