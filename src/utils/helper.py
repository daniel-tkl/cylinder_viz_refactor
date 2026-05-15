import math
import numpy as np
import pandas as pd
import streamlit as st
from typing import List, Dict
from src.cylinder_viz.aggregation import AggregationResult

def _variant_family_label(variant: str) -> str:
    """Return a grouping label for the variant.

    - Variants matching "Motion Time <suffix>" are grouped into family "Motion Time".
    - Otherwise, each variant is its own family label.
    """
    v = variant.strip().lower()
    # Group Motion Time related variants into one chart
    suffixes = {"average", "max", "min", "width"}
    parts = v.split()
    if len(parts) >= 3 and parts[0] == "motion" and parts[1] == "time" and parts[-1] in suffixes:
        return "Motion Time"
    return variant.strip()

def _group_has_over_threshold(
    agg: AggregationResult,
    variant_columns: List[str],
    label_map: Dict[str, str] | None,
    base_time_baseline: float | None,
    max_pct: float,
    min_pct: float,
) -> bool:
    """Return True if any variant's daily series crosses its threshold band.

    Thresholds are computed per variant as:
    - `max_thr = baseline * (1 + max_pct/100)`
    - `min_thr = baseline * (1 - min_pct/100)`

    For time-related variants (name contains 'time' via `label_map`), if
    `base_time_baseline` is provided, it supersedes the per-variant baseline.

    Parameters
    - agg: Aggregation result containing `daily` and `baselines`.
    - variant_columns: List of variant column names to check.
    - label_map: Optional mapping from column name to display name.
    - base_time_baseline: Optional baseline for time-related variants.
    - max_pct: Upper threshold percentage.
    - min_pct: Lower threshold percentage.

    Returns
    - True if any value across checked variants is > max_thr or < min_thr; else False.
    """
    if agg.daily.empty:
        return False
    daily = agg.daily
    
    for col in variant_columns:
        baseline = agg.baselines.get(col)
        if baseline is None or not isinstance(baseline, (int, float)) or math.isnan(baseline):
            continue
        if base_time_baseline is not None and label_map is not None:
            name = label_map.get(col, "")
            if "time" in name.lower():
                baseline = base_time_baseline
        max_thr = baseline * (1.0 + max_pct / 100.0)
        min_thr = baseline * (1.0 - min_pct / 100.0)
        series = pd.to_numeric(daily[col], errors="coerce")
        
        if ((series > max_thr) | (series < min_thr)).any():
            return True
    return False

@st.cache_data
def _read_data(uploaded_file: np.ndarray | dict) -> pd.DataFrame:
    if uploaded_file.name.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(uploaded_file, engine="pyarrow", dtype_backend="pyarrow")
    else:
        df = pd.read_csv(uploaded_file, engine="pyarrow", dtype_backend="pyarrow")
    return df

def highlight_ng(val):
                color = 'red' if 'NG' in str(val) else 'black'
                return f'color: {color}'