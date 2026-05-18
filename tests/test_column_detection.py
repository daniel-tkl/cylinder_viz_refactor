from __future__ import annotations

import pandas as pd

from src.cylinder_domain.parsing import detect_datetime_column, detect_id_column, parse_dataset


def test_detect_id_column_by_name_pattern() -> None:
    df = pd.DataFrame(
        {
            "Machine No": ["M1", "M2", "M1"],
            "Date Time": ["2026-01-01 10:00:00", "2026-01-01 11:00:00", "2026-01-01 12:00:00"],
            "A/B/Motion Time Average": [10, 11, 9],
        }
    )
    assert detect_id_column(df) == "Machine No"


def test_detect_datetime_column_by_parse_ratio_fallback() -> None:
    df = pd.DataFrame(
        {
            "Machine": ["M1", "M1", "M2", "M2", "M1"],
            "Cycle Time": ["fast", "slow", "slow", "fast", "fast"],
            "Created At": [
                "2026-01-01 10:00:00",
                "2026-01-01 11:00:00",
                "2026-01-02 10:00:00",
                "2026-01-02 11:00:00",
                "2026-01-03 10:00:00",
            ],
        }
    )
    assert detect_datetime_column(df) == "Created At"


def test_detect_datetime_column_avoids_weak_match() -> None:
    df = pd.DataFrame(
        {
            "Machine": ["M1", "M2", "M3", "M4", "M5"],
            "MaybeDate": ["x", "y", "2026-01-01", "z", "k"],
            "Other": [1, 2, 3, 4, 5],
        }
    )
    assert detect_datetime_column(df) is None


def test_parse_dataset_builds_hierarchy() -> None:
    df = pd.DataFrame(
        {
            "Device SN": ["D1", "D1"],
            "Date Time": ["2026-01-01 10:00:00", "2026-01-01 11:00:00"],
            "ModuleA/ItemX/Motion Time Max": [20, 22],
            "ModuleA/ItemX/Motion Time Min": [10, 11],
        }
    )
    parsed = parse_dataset(df)
    assert parsed.id_column == "Device SN"
    assert parsed.datetime_column == "Date Time"
    assert parsed.hierarchy["ModuleA"]["ItemX"]["Motion Time Max"] == "ModuleA/ItemX/Motion Time Max"
