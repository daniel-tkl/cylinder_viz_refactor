from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Literal, Tuple

import numpy as np
import pandas as pd

AggregationMethod = Literal["max", "min", "average", "count", "range"]


@dataclass
class AggregationResult:
    daily: pd.DataFrame
    baselines: Dict[str, float]


def _to_date_series(dt_series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(dt_series, errors="coerce")
    return dt.dt.floor("D")


def _safe_nanmean(values: np.ndarray) -> float:
    if values.size == 0 or np.isnan(values).all():
        return float("nan")
    return float(np.nanmean(values))


def prepare_aggregation_frame(
    df: pd.DataFrame,
    id_column: str,
    datetime_column: str,
) -> pd.DataFrame:
    work = df.copy()
    work[datetime_column] = pd.to_datetime(work[datetime_column], errors="coerce")
    work = work.dropna(subset=[datetime_column])
    work["__id_norm"] = work[id_column].astype(str)
    work["__date"] = _to_date_series(work[datetime_column])
    return work


def aggregate_daily(
    df: pd.DataFrame,
    id_column: str,
    datetime_column: str,
    selected_columns: Iterable[str],
    method: AggregationMethod | Dict[str, AggregationMethod],
    machines: Iterable[str] | None = None,
    prepared_df: pd.DataFrame | None = None,
) -> AggregationResult:
    selected_columns_list = list(selected_columns)

    if prepared_df is not None:
        base = prepared_df
    else:
        base = prepare_aggregation_frame(df=df, id_column=id_column, datetime_column=datetime_column)

    required_columns = [id_column, "__date", *selected_columns_list]
    work = base.loc[:, [c for c in required_columns if c in base.columns]].copy()

    if "__id_norm" in base.columns:
        work["__id_norm"] = base["__id_norm"].values
    else:
        work["__id_norm"] = work[id_column].astype(str)

    machine_list = list(machines) if machines is not None else None
    if machine_list is not None:
        machine_set = {str(machine) for machine in machine_list}
        work = work[work["__id_norm"].isin(machine_set)]

    agg_funcs: Dict[str, str] = {}
    rng_pairs: List[str] = []
    numeric_methods: Tuple[AggregationMethod, ...] = ("max", "min", "average", "range")
    final_columns: List[str] = []

    def _method_for_col(column_name: str) -> AggregationMethod:
        if isinstance(method, dict):
            return method.get(column_name, "average")
        return method

    for col in selected_columns_list:
        col_method = _method_for_col(col)
        if col_method in numeric_methods:
            work[col] = pd.to_numeric(work[col], errors="coerce")

        if col_method == "max":
            agg_funcs[col] = "max"
        elif col_method == "min":
            agg_funcs[col] = "min"
        elif col_method == "average":
            agg_funcs[col] = "mean"
        elif col_method == "count":
            agg_funcs[col] = "count"
        elif col_method == "range":
            agg_funcs[col] = "max"
            rng_pairs.append(col)
        else:
            raise ValueError(f"Unsupported aggregation method: {col_method}")
        final_columns.append(col)

    grouped = work.groupby([id_column, "__date"]).agg(agg_funcs)

    if any(_method_for_col(c) == "range" for c in rng_pairs):
        mins = work.groupby([id_column, "__date"]).agg({c: "min" for c in rng_pairs})
        grouped[rng_pairs] = grouped[rng_pairs] - mins[rng_pairs]

    if machine_list is not None and len(machine_list) == 1:
        grouped = grouped.reset_index(level=0, drop=True)

    baselines: Dict[str, float] = {}
    for col in final_columns:
        vals = grouped[col].astype(float)
        baselines[col] = _safe_nanmean(vals.values)

    daily = grouped.reset_index().set_index("__date").sort_index()
    return AggregationResult(daily=daily, baselines=baselines)
