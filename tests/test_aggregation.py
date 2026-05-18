from __future__ import annotations

import math

import pandas as pd

from src.cylinder_domain.aggregation import aggregate_daily


def test_aggregate_daily_range_method() -> None:
    df = pd.DataFrame(
        {
            "Machine No": ["M1", "M1", "M1", "M1"],
            "Date Time": [
                "2026-01-01 10:00:00",
                "2026-01-01 11:00:00",
                "2026-01-02 10:00:00",
                "2026-01-02 11:00:00",
            ],
            "A/B/Width": [10, 15, 5, 13],
        }
    )

    agg = aggregate_daily(
        df=df,
        id_column="Machine No",
        datetime_column="Date Time",
        selected_columns=["A/B/Width"],
        method={"A/B/Width": "range"},
        machines=["M1"],
    )

    values = agg.daily["A/B/Width"].tolist()
    assert values == [5, 8]
    assert agg.baselines["A/B/Width"] == 6.5


def test_aggregate_daily_returns_nan_baseline_for_all_nan_series() -> None:
    df = pd.DataFrame(
        {
            "Machine No": ["M1", "M1"],
            "Date Time": ["2026-01-01 10:00:00", "2026-01-01 11:00:00"],
            "A/B/Value": ["bad", "data"],
        }
    )

    agg = aggregate_daily(
        df=df,
        id_column="Machine No",
        datetime_column="Date Time",
        selected_columns=["A/B/Value"],
        method="average",
        machines=["M1"],
    )

    assert math.isnan(agg.baselines["A/B/Value"])


def test_aggregate_daily_single_machine_with_generator_filter() -> None:
    df = pd.DataFrame(
        {
            "Machine No": ["M1", "M1", "M2", "M2"],
            "Date Time": [
                "2026-01-01 10:00:00",
                "2026-01-01 11:00:00",
                "2026-01-01 10:00:00",
                "2026-01-01 11:00:00",
            ],
            "A/B/Motion Time Average": [10, 14, 50, 60],
        }
    )

    machines = (machine for machine in ["M1"])
    agg = aggregate_daily(
        df=df,
        id_column="Machine No",
        datetime_column="Date Time",
        selected_columns=["A/B/Motion Time Average"],
        method="average",
        machines=machines,
    )

    assert "Machine No" not in agg.daily.columns
    assert agg.daily["A/B/Motion Time Average"].iloc[0] == 12.0
