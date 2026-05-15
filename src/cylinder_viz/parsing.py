from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedColumn:
    """
    Represents a parsed measurement column split into module/item/variant.

    Attributes:
        original_name: The original column name in the DataFrame.
        module: Parsed module name (prefix before first '/').
        item: Parsed item name (middle section between '/').
        variant: Parsed variant name (section after second '/', may contain '/').
    """

    original_name: str
    module: str
    item: str
    variant: str


@dataclass
class ParseResult:
    """
    Container for parsing results.

    Attributes:
        id_column: The detected device/machine identifier column name.
        datetime_column: The detected datetime column name.
        measurements: List of parsed measurement columns.
        hierarchy: Nested mapping module -> item -> variant -> original column name.
    """

    id_column: str
    datetime_column: str
    measurements: List[ParsedColumn]
    hierarchy: Dict[str, Dict[str, Dict[str, str]]]


DEVICE_ID_PATTERNS: Tuple[str, ...] = (
    r"machine\s*no",
    r"device\s*sn",
    r"equipment\s*sn",
    r"serial\s*number",
    r"device\s*id",
    r"machine\s*id",
)

DATETIME_PATTERNS: Tuple[str, ...] = (
    r"date\s*time",
    r"datetime",
    r"timestamp",
    r"time",
    r"date",
)


def _normalize_col(col: str) -> str:
    """Normalize a column name for pattern matching.

    Converts to lowercase and strips surrounding whitespace.
    """
    return col.strip().lower()


def detect_id_column(df: pd.DataFrame) -> Optional[str]:
    """Detect the device/machine identifier column.

    Tries matching known patterns against column names. Returns the first match.
    """
    for col in df.columns:
        norm = _normalize_col(col)
        for pat in DEVICE_ID_PATTERNS:
            if re.search(pat, norm):
                return col
    # Fallback: if there's a column with few unique values relative to rows
    candidate = None
    min_unique_ratio = 1.0
    for col in df.columns:
        nunique = df[col].nunique(dropna=True)
        ratio = nunique / max(len(df), 1)
        if ratio < min_unique_ratio and df[col].dtype == object:
            candidate = col
            min_unique_ratio = ratio
    return candidate


def detect_datetime_column(df: pd.DataFrame) -> Optional[str]:
    """Detect a datetime column by name patterns or dtype conversion.

    Returns the first matching or convertible column.
    """
    # Prefer name patterns
    for col in df.columns:
        norm = _normalize_col(col)
        for pat in DATETIME_PATTERNS:
            if re.search(pat, norm):
                return col
    # Fallback: attempt to parse object-like columns to datetime
    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
            try:
                pd.to_datetime(df[col])
                return col
            except Exception:  # noqa: BLE001
                continue
    # Lastly, consider already datetime dtypes
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            return col
    return None


def parse_measurement_columns(df: pd.DataFrame, id_col: str, dt_col: str) -> List[ParsedColumn]:
    """Parse measurement columns into Module/Item/Variant.

    Skips `id_col` and `dt_col`. Splits other column headers by '/', ensuring exactly
    3 parts: Module, Item, Variant (Variant may include additional '/' joined back).
    """
    parsed: List[ParsedColumn] = []

    # Known non-measurement columns to ignore
    non_measurement_names = {
        "model",
        "week",
        "month",
        "day",
        "week number",
    }

    for col in df.columns:
        if col in (id_col, dt_col):
            continue
        norm = _normalize_col(str(col))
        if norm in non_measurement_names:
            # Skip known non-measurement metadata columns
            continue
        # Measurement columns must contain at least two '/' separators per PRD
        if str(col).count('/') < 2:
            continue
        parts = [p.strip() for p in str(col).split('/')]
        # Combine any extra parts into Variant
        module, item, *rest = parts
        variant = "/".join(rest) if rest else "Value"
        parsed.append(ParsedColumn(original_name=col, module=module, item=item, variant=variant))
    return parsed


def build_hierarchy(measurements: List[ParsedColumn]) -> Dict[str, Dict[str, Dict[str, str]]]:
    """Build nested hierarchy mapping module->item->variant->column name."""
    hierarchy: Dict[str, Dict[str, Dict[str, str]]] = {}
    for m in measurements:
        hierarchy.setdefault(m.module, {}).setdefault(m.item, {})[m.variant] = m.original_name
    return hierarchy


def parse_dataset(df: pd.DataFrame) -> ParseResult:
    """
    Parse dataset to identify identifiers, datetime, and measurement hierarchy.

    Raises:
        ValueError: If identifier or datetime columns cannot be detected.
    """
    id_col = detect_id_column(df)
    dt_col = detect_datetime_column(df)
    if not id_col or not dt_col:
        logger.error("Failed to detect id or datetime columns: id=%s, dt=%s", id_col, dt_col)
        raise ValueError("Required columns (Device/Machine ID and DateTime) not found.")

    measurements = parse_measurement_columns(df, id_col, dt_col)
    hierarchy = build_hierarchy(measurements)
    return ParseResult(id_column=id_col, datetime_column=dt_col, measurements=measurements, hierarchy=hierarchy)
