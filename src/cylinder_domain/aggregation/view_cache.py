from __future__ import annotations

import logging
from typing import Dict, List

import pandas as pd

from src.cylinder_domain.parsing import ParseResult

from .aggregation import AggregationMethod, AggregationResult, aggregate_daily, prepare_aggregation_frame
from .thresholds import group_has_over_threshold


logger = logging.getLogger(__name__)


def slice_aggregation_result(agg: AggregationResult, selected_columns: List[str]) -> AggregationResult:
    available_columns = [column for column in selected_columns if column in agg.daily.columns]
    daily = agg.daily.loc[:, available_columns].copy() if available_columns else agg.daily.iloc[:, 0:0].copy()
    baselines = {column: agg.baselines[column] for column in selected_columns if column in agg.baselines}
    return AggregationResult(daily=daily, baselines=baselines)


def build_machine_module_cache(
    df: pd.DataFrame,
    parsed: ParseResult,
    variants_map: Dict[str, str],
    sub_machines: List[str],
    module: str,
    module_no_label: str,
    selected_module_nos: List[str],
    variant_columns: List[str],
    method_map: Dict[str, AggregationMethod],
    prepared_df: pd.DataFrame | None = None,
) -> Dict[str, List[tuple[str, AggregationResult, float | None]]]:
    if prepared_df is None:
        prepared_df = prepare_aggregation_frame(
            df=df,
            id_column=parsed.id_column,
            datetime_column=parsed.datetime_column,
        )

    module_no_col = f"{module}/{module_no_label}"
    base_time_col = next(
        (col_name for variant_name, col_name in variants_map.items() if variant_name.strip().lower() == "base time"),
        None,
    )
    selected_module_nos_set = set(selected_module_nos)
    visible_plots_by_machine: Dict[str, List[tuple[str, AggregationResult, float | None]]] = {
        machine: [] for machine in sub_machines
    }

    for machine in sub_machines:
        df_machine = prepared_df[prepared_df["__id_norm"] == str(machine)]
        if module_no_col in df_machine.columns:
            mod_nos = df_machine[module_no_col].dropna().astype(str).unique().tolist()
            if selected_module_nos:
                mod_nos = [module_no for module_no in mod_nos if module_no in selected_module_nos_set]
        else:
            mod_nos = [None]

        for mod_no in mod_nos:
            df_mod = df_machine
            if mod_no is not None and module_no_col in df_machine.columns:
                df_mod = df_machine[df_machine[module_no_col].astype(str) == str(mod_no)]

            try:
                per_machine_res = aggregate_daily(
                    df=df_mod,
                    id_column=parsed.id_column,
                    datetime_column=parsed.datetime_column,
                    selected_columns=variant_columns,
                    method=method_map,
                    machines=[machine],
                    prepared_df=df_mod,
                )
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping aggregation for module=%s machine=%s mod_no=%s due to %s",
                    module,
                    machine,
                    mod_no,
                    exc,
                )
                continue

            base_time_baseline = per_machine_res.baselines.get(base_time_col) if base_time_col is not None else None
            module_value = str(mod_no) if mod_no is not None else ""
            visible_plots_by_machine[machine].append((module_value, per_machine_res, base_time_baseline))

    return visible_plots_by_machine


def filter_visible_cached_plots(
    cached_plots_by_machine: Dict[str, List[tuple[str, AggregationResult, float | None]]],
    variant_columns: List[str],
    label_map: Dict[str, str],
    display_mode: str,
    max_threshold_pct: float,
    min_threshold_pct: float,
) -> Dict[str, List[tuple[str, AggregationResult, float | None, bool]]]:
    filtered_plots_by_machine: Dict[str, List[tuple[str, AggregationResult, float | None, bool]]] = {
        machine: [] for machine in cached_plots_by_machine
    }

    for machine, machine_plots in cached_plots_by_machine.items():
        for mod_no, full_agg, base_time_baseline in machine_plots:
            sliced_agg = slice_aggregation_result(full_agg, variant_columns)
            has_data = not sliced_agg.daily.empty and sliced_agg.daily.notna().any().any()
            is_over_threshold = group_has_over_threshold(
                agg=sliced_agg,
                variant_columns=variant_columns,
                label_map=label_map,
                base_time_baseline=base_time_baseline,
                max_pct=max_threshold_pct,
                min_pct=min_threshold_pct,
            )

            if display_mode == "Over-threshold only":
                if not is_over_threshold:
                    continue
            else:
                if not has_data:
                    continue

            filtered_plots_by_machine[machine].append((mod_no, sliced_agg, base_time_baseline, is_over_threshold))

    return filtered_plots_by_machine


def build_family_visible_cache(
    cached_plots_by_machine: Dict[str, List[tuple[str, AggregationResult, float | None]]],
    groups: Dict[str, List[tuple[str, str]]],
    display_mode: str,
    max_threshold_pct: float,
    min_threshold_pct: float,
) -> Dict[str, Dict[str, List[tuple[str, AggregationResult, float | None, bool]]]]:
    family_visible_cache: Dict[str, Dict[str, List[tuple[str, AggregationResult, float | None, bool]]]] = {}

    for family_label, items_in_group in groups.items():
        variant_columns = [col_name for _, col_name in items_in_group]
        if not variant_columns:
            continue
        label_map = {col_name: variant_name for variant_name, col_name in items_in_group}
        family_visible_cache[family_label] = filter_visible_cached_plots(
            cached_plots_by_machine=cached_plots_by_machine,
            variant_columns=variant_columns,
            label_map=label_map,
            display_mode=display_mode,
            max_threshold_pct=max_threshold_pct,
            min_threshold_pct=min_threshold_pct,
        )

    return family_visible_cache