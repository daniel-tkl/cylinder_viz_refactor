from __future__ import annotations

import re
from typing import Optional, Tuple

import pandas as pd

DEVICE_ID_PATTERNS: Tuple[str, ...] = (
    r"machine\s*no",
    r"device\s*sn",
    r"equipment\s*sn",
    r"serial\s*number",
    r"device\s*id",
    r"machine\s*id",
)

DATETIME_NAME_PATTERNS: Tuple[str, ...] = (
    r"(^|\b)date\s*time(\b|$)",
    r"(^|\b)datetime(\b|$)",
    r"(^|\b)timestamp(\b|$)",
)

DATE_LIKE_VALUE_PATTERNS: Tuple[str, ...] = (
    r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b",
    r"\b\d{1,2}:\d{2}(:\d{2})?\b",
)


def normalize_column_name(column_name: str) -> str:
    return column_name.strip().lower()


def _is_date_like_text(value: object) -> bool:
    text = str(value).strip().lower()
    if not text:
        return False
    for pattern in DATE_LIKE_VALUE_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def _date_like_text_ratio(series: pd.Series) -> float:
    non_null = series.dropna()
    total = max(len(non_null), 1)
    hits = sum(1 for value in non_null if _is_date_like_text(value))
    return float(hits / total)


def detect_id_column(df: pd.DataFrame) -> Optional[str]:
    for col in df.columns:
        norm = normalize_column_name(str(col))
        for pat in DEVICE_ID_PATTERNS:
            if re.search(pat, norm):
                return str(col)

    best_col: Optional[str] = None
    best_ratio = 1.0
    row_count = max(len(df), 1)
    for col in df.columns:
        series = df[col]
        if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
            continue
        unique_ratio = series.nunique(dropna=True) / row_count
        if unique_ratio < best_ratio:
            best_ratio = unique_ratio
            best_col = str(col)
    return best_col


def _datetime_parse_ratio(series: pd.Series) -> float:
    if _date_like_text_ratio(series) < 0.5:
        return 0.0

    try:
        parsed = pd.to_datetime(series, errors="coerce", format="mixed")
    except TypeError:
        parsed = pd.to_datetime(series, errors="coerce")
    total = max(len(series), 1)
    return float(parsed.notna().sum() / total)


def detect_datetime_column(df: pd.DataFrame) -> Optional[str]:
    for col in df.columns:
        norm = normalize_column_name(str(col))
        for pat in DATETIME_NAME_PATTERNS:
            if re.search(pat, norm):
                return str(col)

    best_col: Optional[str] = None
    best_ratio = 0.0
    for col in df.columns:
        series = df[col]
        if pd.api.types.is_datetime64_any_dtype(series):
            return str(col)
        if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
            continue
        ratio = _datetime_parse_ratio(series)
        if ratio > best_ratio:
            best_ratio = ratio
            best_col = str(col)

    if best_col is not None and best_ratio >= 0.8:
        return best_col
    return None
