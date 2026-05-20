from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _extract_row_index(selection: Any) -> int | None:
    if not isinstance(selection, dict):
        return None

    rows = selection.get("rows", [])
    if rows:
        try:
            return int(rows[0])
        except (TypeError, ValueError):
            return None

    cells = selection.get("cells", [])
    if not cells:
        return None

    first_cell = cells[0]
    if isinstance(first_cell, dict):
        row_value = first_cell.get("row")
        try:
            return int(row_value) if row_value is not None else None
        except (TypeError, ValueError):
            return None

    if isinstance(first_cell, (list, tuple)) and first_cell:
        try:
            return int(first_cell[0])
        except (TypeError, ValueError):
            return None

    return None


def build_selected_row_payload(selected_event: Any, df_all: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series] | None:
    if df_all.empty:
        return None

    selection = getattr(selected_event, "selection", None) or {}
    selected_row_index = _extract_row_index(selection)
    if selected_row_index is None:
        return None
    if selected_row_index < 0 or selected_row_index >= len(df_all):
        return None

    selected_row = df_all.iloc[selected_row_index]

    daily_dates = selected_row["Daily Dates"]
    daily_avg_values = selected_row["Daily Avg"]
    daily_min_values = selected_row["Daily Min"]
    daily_max_values = selected_row["Daily Max"]

    if not isinstance(daily_dates, (list, tuple)) or not isinstance(daily_avg_values, (list, tuple)):
        return None
    if not daily_dates or not daily_avg_values:
        return None

    point_count = len(daily_dates)

    def _normalize_optional_series(values: Any) -> list[float]:
        if isinstance(values, (list, tuple)) and len(values) == point_count:
            return list(values)
        return [np.nan] * point_count

    normalized_min = _normalize_optional_series(daily_min_values)
    normalized_max = _normalize_optional_series(daily_max_values)

    selected_viz = pd.DataFrame(
        {
            "Date": list(daily_dates),
            "min": normalized_min,
            "avg": list(daily_avg_values),
            "max": normalized_max,
            "equipment": selected_row["Equipment"],
        }
    )
    selected_data = selected_row.to_frame().T
    return selected_data, selected_viz, selected_row
