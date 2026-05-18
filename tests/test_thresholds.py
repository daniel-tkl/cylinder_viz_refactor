from __future__ import annotations

import pandas as pd

from src.cylinder_domain.aggregation import AggregationResult, group_has_over_threshold, variant_family_label


def test_variant_family_label_groups_motion_time_variants() -> None:
    assert variant_family_label("Motion Time Max") == "Motion Time"
    assert variant_family_label("Motion Time Average") == "Motion Time"
    assert variant_family_label("Pressure Peak") == "Pressure Peak"


def test_group_has_over_threshold_uses_base_time_baseline() -> None:
    daily = pd.DataFrame(
        {
            "m/item/Motion Time Max": [130.0, 95.0],
        }
    )
    agg = AggregationResult(
        daily=daily,
        baselines={"m/item/Motion Time Max": 200.0},
    )

    result = group_has_over_threshold(
        agg=agg,
        variant_columns=["m/item/Motion Time Max"],
        label_map={"m/item/Motion Time Max": "Motion Time Max"},
        base_time_baseline=100.0,
        max_pct=20.0,
        min_pct=20.0,
    )
    assert result is True


def test_group_has_over_threshold_false_on_empty_daily() -> None:
    agg = AggregationResult(daily=pd.DataFrame(), baselines={"x": 100.0})
    assert (
        group_has_over_threshold(
            agg=agg,
            variant_columns=["x"],
            label_map={"x": "X"},
            base_time_baseline=None,
            max_pct=10.0,
            min_pct=10.0,
        )
        is False
    )
