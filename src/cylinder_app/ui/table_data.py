from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd
import streamlit as st

from src.cylinder_domain.aggregation import (
    build_family_visible_cache,
    build_machine_module_cache,
    build_variant_group_plan,
    prepare_aggregation_frame,
    resolve_motion_time_columns,
)
from src.cylinder_domain.parsing import ParseResult
from .table_state import new_table_list_view


def _series_values(series: pd.Series | None) -> tuple[float | int | str | None, ...] | None:
    if series is None:
        return None
    return tuple(series.tolist())


@st.cache_data(show_spinner=False)
def build_table_dataframe_cached(
    df: pd.DataFrame,
    parsed: ParseResult,
    selected_items: tuple[str, ...],
    selected_modules: tuple[str, ...],
    selected_variants: tuple[str, ...],
    sub_machines_global: tuple[str, ...],
    selected_module_nos: tuple[str, ...],
    module_no_label: str,
    display_mode: str,
    max_threshold_pct: float,
    min_threshold_pct: float,
    selected_machines: tuple[str, ...],
) -> pd.DataFrame:
    list_view: Dict[str, list] = new_table_list_view()
    prepared_df = prepare_aggregation_frame(
        df=df,
        id_column=parsed.id_column,
        datetime_column=parsed.datetime_column,
    )

    for item in selected_items:
        for module in selected_modules:
            variants_map = parsed.hierarchy.get(module, {}).get(item, {})
            if not variants_map:
                continue

            plan = build_variant_group_plan(variants_map=variants_map, selected_variants=selected_variants)
            if not plan.all_variant_columns:
                continue

            cached_plots_by_machine = build_machine_module_cache(
                df=df,
                parsed=parsed,
                variants_map=variants_map,
                sub_machines=list(sub_machines_global),
                module=module,
                module_no_label=module_no_label,
                selected_module_nos=list(selected_module_nos),
                variant_columns=plan.all_variant_columns,
                method_map=plan.method_map,
                prepared_df=prepared_df,
            )
            family_visible_cache = build_family_visible_cache(
                cached_plots_by_machine=cached_plots_by_machine,
                groups=plan.groups,
                display_mode=display_mode,
                max_threshold_pct=max_threshold_pct,
                min_threshold_pct=min_threshold_pct,
            )

            title_base = f"{module} / {item}"
            motion_cols = resolve_motion_time_columns(variants_map)

            for family_label, items_in_group in plan.groups.items():
                variant_names = [variant_name for variant_name, _ in items_in_group]
                variant_columns = [col_name for _, col_name in items_in_group]
                if not variant_columns:
                    continue

                title = (
                    f"{title_base} / {family_label}"
                    if family_label != variant_names[0]
                    else f"{title_base} / {variant_names[0]}"
                )

                visible_plots_by_machine = family_visible_cache.get(
                    family_label,
                    {machine: [] for machine in sub_machines_global},
                )

                if not any(visible_plots_by_machine[machine] for machine in sub_machines_global):
                    continue

                for machine in sub_machines_global:
                    for mod_no, per_machine_res, base_time_baseline, is_over_threshold in visible_plots_by_machine[machine]:
                        list_view["Equipment"].append(machine)
                        list_view["Motion"].append(title)
                        list_view["Module"].append(mod_no)
                        threshold_min = (
                            (1 - (min_threshold_pct / 100)) * base_time_baseline
                            if base_time_baseline is not None
                            else np.nan
                        )
                        threshold_max = (
                            (1 + (max_threshold_pct / 100)) * base_time_baseline
                            if base_time_baseline is not None
                            else np.nan
                        )
                        list_view["Threshold_Min"].append(threshold_min)
                        list_view["Threshold_Max"].append(threshold_max)
                        list_view["Base"].append(base_time_baseline)
                        list_view["Daily Dates"].append(tuple(per_machine_res.daily.index.tolist()))

                        list_view["Avg"].append(
                            per_machine_res.baselines.get(motion_cols.avg_col) if motion_cols.avg_col else None
                        )
                        list_view["Min"].append(
                            per_machine_res.baselines.get(motion_cols.min_col) if motion_cols.min_col else None
                        )
                        list_view["Max"].append(
                            per_machine_res.baselines.get(motion_cols.max_col) if motion_cols.max_col else None
                        )
                        list_view["Daily Min"].append(
                            _series_values(per_machine_res.daily.get(motion_cols.min_col)) if motion_cols.min_col else None
                        )
                        list_view["Daily Avg"].append(
                            _series_values(per_machine_res.daily.get(motion_cols.avg_col)) if motion_cols.avg_col else None
                        )
                        list_view["Daily Max"].append(
                            _series_values(per_machine_res.daily.get(motion_cols.max_col)) if motion_cols.max_col else None
                        )
                        list_view["Result"].append("NG" if is_over_threshold else "OK")

    df_all = pd.DataFrame(list_view)
    if display_mode == "Over-threshold only":
        df_all = df_all[df_all["Result"] == "NG"]
    if not df_all.empty:
        df_all = df_all[df_all["Equipment"].isin(selected_machines)]
        df_all = df_all[df_all["Module"].isin(selected_module_nos)]
    return df_all
