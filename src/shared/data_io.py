from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd


def read_uploaded_dataframe(uploaded_file: Any) -> pd.DataFrame:
    name = str(uploaded_file.name).lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file, dtype_backend="pyarrow")
    return pd.read_csv(uploaded_file, engine="pyarrow", dtype_backend="pyarrow")


def read_uploaded_dataframe_bytes(file_name: str, file_bytes: bytes) -> pd.DataFrame:
    buffer = BytesIO(file_bytes)
    if file_name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(buffer, dtype_backend="pyarrow")
    return pd.read_csv(buffer, engine="pyarrow", dtype_backend="pyarrow")
