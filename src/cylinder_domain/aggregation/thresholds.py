from __future__ import annotations

import math
from typing import Dict, List

import pandas as pd

from .aggregation import AggregationResult


def variant_family_label(variant: str) -> str:
    value = variant.strip().lower()
    suffixes = {"average", "max", "min", "width"}
    parts = value.split()
    if len(parts) >= 3 and parts[0] == "motion" and parts[1] == "time" and parts[-1] in suffixes:
        return "Motion Time"
    return variant.strip()


def group_has_over_threshold(
    agg: AggregationResult,
    variant_columns: List[str],
    label_map: Dict[str, str] | None,
    base_time_baseline: float | None,
    max_pct: float,
    min_pct: float,
) -> bool:
    if agg.daily.empty:
        return False

    daily = agg.daily
    for column in variant_columns:
        baseline = agg.baselines.get(column)
        if baseline is None or not isinstance(baseline, (int, float)) or math.isnan(baseline):
            continue

        if base_time_baseline is not None and label_map is not None:
            name = label_map.get(column, "")
            if "time" in name.lower():
                baseline = base_time_baseline

        max_threshold = baseline * (1.0 + max_pct / 100.0)
        min_threshold = baseline * (1.0 - min_pct / 100.0)
        series = pd.to_numeric(daily[column], errors="coerce")
        if ((series > max_threshold) | (series < min_threshold)).any():
            return True
    return False
