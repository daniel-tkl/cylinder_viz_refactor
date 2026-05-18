from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd


@dataclass(frozen=True)
class ParsedColumn:
    original_name: str
    module: str
    item: str
    variant: str


@dataclass
class ParseResult:
    id_column: str
    datetime_column: str
    measurements: List[ParsedColumn]
    hierarchy: Dict[str, Dict[str, Dict[str, str]]]


NON_MEASUREMENT_COLUMN_NAMES = {
    "model",
    "week",
    "month",
    "day",
    "week number",
}


def parse_measurement_columns(df: pd.DataFrame, id_col: str, dt_col: str) -> List[ParsedColumn]:
    parsed: List[ParsedColumn] = []
    for col in df.columns:
        col_name = str(col)
        if col_name in (id_col, dt_col):
            continue

        normalized = col_name.strip().lower()
        if normalized in NON_MEASUREMENT_COLUMN_NAMES:
            continue

        if col_name.count("/") < 2:
            continue

        parts = [part.strip() for part in col_name.split("/")]
        module, item, *rest = parts
        variant = "/".join(rest) if rest else "Value"
        parsed.append(ParsedColumn(original_name=col_name, module=module, item=item, variant=variant))
    return parsed


def build_hierarchy(measurements: List[ParsedColumn]) -> Dict[str, Dict[str, Dict[str, str]]]:
    hierarchy: Dict[str, Dict[str, Dict[str, str]]] = {}
    for measurement in measurements:
        hierarchy.setdefault(measurement.module, {}).setdefault(measurement.item, {})[
            measurement.variant
        ] = measurement.original_name
    return hierarchy
