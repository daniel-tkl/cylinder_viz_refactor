from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from src.cylinder_app.ui.table_selection import build_selected_row_payload


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Equipment": ["M1", "M2"],
            "Daily Dates": [
                ("2026-01-01", "2026-01-02"),
                ("2026-01-03", "2026-01-04"),
            ],
            "Daily Avg": [(10.0, 12.0), (20.0, 21.0)],
            "Daily Min": [(9.0, 11.0), (18.0, 20.0)],
            "Daily Max": [(11.0, 13.0), (22.0, 24.0)],
            "Result": ["OK", "NG"],
        }
    )


def test_build_selected_row_payload_returns_none_for_out_of_bounds_selection() -> None:
    selected_event = SimpleNamespace(selection={"cells": [(99, 0)]})

    payload = build_selected_row_payload(selected_event=selected_event, df_all=_sample_df())

    assert payload is None


def test_build_selected_row_payload_supports_rows_selection_shape() -> None:
    selected_event = SimpleNamespace(selection={"rows": [1]})

    payload = build_selected_row_payload(selected_event=selected_event, df_all=_sample_df())

    assert payload is not None
    selected_data, selected_viz, selected_row = payload
    assert selected_row["Equipment"] == "M2"
    assert selected_data.iloc[0]["Equipment"] == "M2"
    assert list(selected_viz.columns) == ["Date", "min", "avg", "max", "equipment"]
