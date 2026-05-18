from __future__ import annotations

import logging

import pandas as pd

from .column_detection import detect_datetime_column, detect_id_column
from .schema import ParseResult, build_hierarchy, parse_measurement_columns

logger = logging.getLogger(__name__)


def parse_dataset(df: pd.DataFrame) -> ParseResult:
    id_col = detect_id_column(df)
    dt_col = detect_datetime_column(df)
    if not id_col or not dt_col:
        logger.error("Failed to detect id or datetime columns: id=%s, dt=%s", id_col, dt_col)
        raise ValueError("Required columns (Device/Machine ID and DateTime) not found.")

    measurements = parse_measurement_columns(df, id_col, dt_col)
    hierarchy = build_hierarchy(measurements)
    return ParseResult(id_column=id_col, datetime_column=dt_col, measurements=measurements, hierarchy=hierarchy)
