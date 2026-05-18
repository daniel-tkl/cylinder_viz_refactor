from __future__ import annotations

import json
from pathlib import Path
import datetime

from lib.streamlit_analytics2.main import (
    _load_persisted_analytics_snapshot,
    _persist_analytics_snapshot,
)


def test_load_persisted_analytics_snapshot_merges_multiple_session_records(tmp_path: Path) -> None:
    log_path = tmp_path / "usage_log_2026-05-15.txt"

    record_one = {
        "__streamlit_analytics_record_type__": "session_snapshot",
        "data": {
            "loaded_from_firestore": False,
            "total_pageviews": 2,
            "total_script_runs": 3,
            "total_time_seconds": 10.5,
            "per_day": {
                "days": ["2026-05-17"],
                "pageviews": [2],
                "script_runs": [3],
            },
            "widgets": {
                "Model(s)": {"A": 2, 1: 1},
                "Select?": 4,
            },
            "start_time": "17 May 2026, 08:00:00",
        },
    }
    record_two = {
        "__streamlit_analytics_record_type__": "session_snapshot",
        "data": {
            "loaded_from_firestore": False,
            "total_pageviews": 1,
            "total_script_runs": 4,
            "total_time_seconds": 7.25,
            "per_day": {
                "days": ["2026-05-17", "2026-05-18"],
                "pageviews": [1, 1],
                "script_runs": [4, 1],
            },
            "widgets": {
                "Model(s)": {"A": 3, "B": 1},
                "Select?": 2,
            },
            "start_time": "18 May 2026, 09:00:00",
        },
    }

    log_path.write_text(
        "\n".join([json.dumps(record_one), json.dumps(record_two)]),
        encoding="utf-8",
    )

    snapshot = _load_persisted_analytics_snapshot(log_path)

    assert snapshot is not None
    assert snapshot["total_pageviews"] == 3
    assert snapshot["total_script_runs"] == 7
    assert snapshot["total_time_seconds"] == 17.75
    assert snapshot["per_day"]["days"] == ["2026-05-17", "2026-05-18"]
    assert snapshot["per_day"]["pageviews"] == [3, 1]
    assert snapshot["per_day"]["script_runs"] == [7, 1]
    assert snapshot["widgets"]["Model(s)"]["A"] == 5
    assert snapshot["widgets"]["Model(s)"]["1"] == 1
    assert snapshot["widgets"]["Model(s)"]["B"] == 1
    assert snapshot["widgets"]["Select?"] == 6
    assert snapshot["start_time"] == "17 May 2026, 08:00:00"


def test_persisted_snapshot_round_trips_for_restart_loading(tmp_path: Path) -> None:
    log_path = tmp_path / "usage_log_2026-05-15.txt"
    yesterday = str(datetime.date.today() - datetime.timedelta(days=1))
    today = str(datetime.date.today())
    snapshot = {
        "loaded_from_firestore": False,
        "total_pageviews": 5,
        "total_script_runs": 8,
        "total_time_seconds": 12.0,
        "per_day": {
            "days": [yesterday, today],
            "pageviews": [5, 1],
            "script_runs": [8, 1],
        },
        "widgets": {"View Mode": {"Table": 3, "Chart": 2}},
        "start_time": "18 May 2026, 10:00:00",
    }

    _persist_analytics_snapshot(log_path, snapshot)

    loaded = _load_persisted_analytics_snapshot(log_path)

    assert loaded == snapshot
