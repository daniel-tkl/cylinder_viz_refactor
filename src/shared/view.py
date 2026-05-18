from __future__ import annotations

import streamlit as st

from .assets import read_file_base64, read_text_file

sidebar_img = "./assets/tkl_navbar.png"


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
    .stApp {
        background-image: url("data:image/png;base64,%s");
        background-size: cover;
    }
    </style>
    """ % bin_str
    st.markdown(page_bg_img, unsafe_allow_html=True)


def set_sidebar_img(sidebar_img: str = sidebar_img) -> None:
    data = read_file_base64(sidebar_img)
    st.sidebar.markdown(
        f"""
        <div style="display:table;margin-top:-40%;margin-left:25%;">
            <img src="data:image/png;base64,{data}" width="100" height="150">
        </div>
        """,
        unsafe_allow_html=True,
    )
