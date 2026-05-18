from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from src.config import DefaultConfigs
from src.cylinder_domain.parsing import ParseResult, parse_dataset
from src.shared.data_io import read_uploaded_dataframe_bytes

from src.cylinder_app.ui.sidebar import build_model_selection


@dataclass(frozen=True)
class AppDataContext:
    df: pd.DataFrame
    parsed: ParseResult
    selected_models: list[str]
    status_placeholder: Any


@st.cache_data(show_spinner=False)
def _load_uploaded_dataframe(file_name: str, file_bytes: bytes) -> pd.DataFrame:
    return read_uploaded_dataframe_bytes(file_name=file_name, file_bytes=file_bytes)


@st.cache_data(show_spinner=False)
def _parse_dataset_cached(df: pd.DataFrame) -> ParseResult:
    return parse_dataset(df)


def prepare_app_data(defaults: DefaultConfigs) -> AppDataContext:
    if "data" not in st.session_state:
        st.session_state["data"] = None

    _, middle_upload_col, _ = st.columns([1, 3, 1])
    with middle_upload_col:
        uploaded_file = st.file_uploader(
            "Upload CSV or Excel data",
            type=["csv", "xlsx", "xls"],
            help="Dataset must include a machine/device identifier and a datetime column.",
        )

    _, middle_status_col, _ = st.columns([1, 3, 1])
    status_placeholder = middle_status_col.empty()

    if uploaded_file is None:
        st.info("Please upload a file to proceed.")
        st.stop()

    try:
        df = _load_uploaded_dataframe(uploaded_file.name, uploaded_file.getvalue())
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to read file: {exc}")
        st.stop()

    st.session_state["data"] = df
    selected_models, selected_df = build_model_selection(defaults=defaults, df=df)

    try:
        parsed = _parse_dataset_cached(selected_df)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Parsing error: {exc}")
        st.stop()

    return AppDataContext(
        df=selected_df,
        parsed=parsed,
        selected_models=selected_models,
        status_placeholder=status_placeholder,
    )
