from __future__ import annotations
import warnings
from dataclasses import dataclass
from typing import Dict, Iterable, List, Literal, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore', message='Mean of empty slice')
AggregationMethod = Literal["max", "min", "average", "count", "range"]

@dataclass
class AggregationResult:
    """Holds aggregated daily data and baseline averages per variant."""

    daily: pd.DataFrame
    baselines: Dict[str, float]


def _to_date_series(dt_series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(dt_series, errors="coerce")
    return dt.dt.floor("D")


def aggregate_daily(
    df: pd.DataFrame,
    id_column: str,
    datetime_column: str,
    selected_columns: Iterable[str],
    method: AggregationMethod | Dict[str, AggregationMethod],
    machines: Iterable[str] | None = None,
) -> AggregationResult:
    """Aggregate hourly data into daily summaries per variant and machine.

    Returns a DataFrame indexed by date with columns as variant names (original column
    names), optionally labeled by machine if multiple machines are selected.
    Baselines are the average of the aggregated daily values per variant across the
    selected date range (and machines combined if multiple).

    Non-numeric measurement columns are coerced to numeric for numeric aggregation
    methods (max, min, average, range). Unparseable values become NaN to avoid
    aggregation failures (e.g., strings like "12-1"). For "count", values are not
    coerced and the number of non-null entries per day is returned.

    The `method` parameter may be a single method applied to all `selected_columns`,
    or a per-column mapping like `{column_name: method}` to mix methods across
    variants in one aggregation.
    """
    work = df.copy()
    work[datetime_column] = pd.to_datetime(work[datetime_column], errors="coerce")
    work = work.dropna(subset=[datetime_column])

    if machines is not None:
        work = work[work[id_column].isin(list(machines))]

    # Build date column
    work["__date"] = _to_date_series(work[datetime_column])

    # Prepare aggregation dict
    agg_funcs: Dict[str, str] = {}
    rng_pairs: List[str] = []

    # Coerce to numeric for non-count methods to avoid dtype=object mean/max issues
    numeric_methods: Tuple[AggregationMethod, ...] = ("max", "min", "average", "range")
    final_columns: List[str] = []
    # Helper to get method per column
    def _method_for_col(c: str) -> AggregationMethod:
        if isinstance(method, dict):
            m = method.get(c, "average")
            return m
        return method  # type: ignore[return-value]

    for col in selected_columns:
        m = _method_for_col(col)
        if m in numeric_methods:
            # Convert to numeric; unparseable values become NaN
            work[col] = pd.to_numeric(work[col], errors="coerce")

        if m == "max":
            agg_funcs[col] = "max"
        elif m == "min":
            agg_funcs[col] = "min"
        elif m == "average":
            agg_funcs[col] = "mean"
        elif m == "count":
            agg_funcs[col] = "count"
        elif m == "range":
            # For range, we need both max and min, then subtract post-group
            agg_funcs[col] = "max"
            rng_pairs.append(col)
        else:
            raise ValueError(f"Unsupported aggregation method: {m}")
        final_columns.append(col)

    grouped = work.groupby([id_column, "__date"]).agg(agg_funcs)

    if any(_method_for_col(c) == "range" for c in rng_pairs):
        mins = work.groupby([id_column, "__date"]).agg({c: "min" for c in rng_pairs})
        grouped[rng_pairs] = grouped[rng_pairs] - mins[rng_pairs]

    # If single machine, flatten index
    if machines is not None and len(list(machines)) == 1:
        grouped = grouped.reset_index(level=0, drop=True)

    # Compute baselines per variant (average across dates and machines)
    baselines: Dict[str, float] = {}
    for col in final_columns:
        vals = grouped[col].astype(float)
        # nanmean returns NaN if all values are NaN; cast to float for consistency
        baselines[col] = float(np.nanmean(vals.values))

    # Return daily with date index
    daily = grouped.reset_index().set_index("__date").sort_index()
    return AggregationResult(daily=daily, baselines=baselines)
