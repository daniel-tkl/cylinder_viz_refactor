from __future__ import annotations

import logging
from time import perf_counter
from typing import Dict, List

import pandas as pd
import streamlit as st

from src.cylinder_domain.aggregation import (
    build_family_visible_cache,
    build_machine_module_cache,
    build_variant_group_plan,
    prepare_aggregation_frame,
)
from src.cylinder_domain.parsing import ParseResult
from src.cylinder_domain.visualization import plot_variants_combined
from src.shared.perf import log_duration


logger = logging.getLogger(__name__)
SHORT_SERIES_POINT_THRESHOLD = 4


def render_chart_view(
    df: pd.DataFrame,
    parsed: ParseResult,
    selected_items: List[str],
    selected_modules: List[str],
    selected_variants: List[str],
    sub_machines_global: List[str],
    selected_module_nos: List[str],
    module_no_label: str,
    display_mode: str,
    max_threshold_pct: float,
    min_threshold_pct: float,
    variant_highlight: str,
    enable_perf_logging: bool = False,
) -> None:
    with st.spinner(text="In progress...  Please Wait... ", show_time=True, width="content"):
        total_started = perf_counter()
        prep_started = perf_counter()
        prepared_df = prepare_aggregation_frame(
            df=df,
            id_column=parsed.id_column,
            datetime_column=parsed.datetime_column,
        )
        log_duration(logger, "chart.prepare_aggregation_frame", prep_started, enable_perf_logging)

        rendered_charts = 0
        st.markdown("<h2 style='text-align: center;'>Chart Visualization</h2>", unsafe_allow_html=True)
        for idx_item, item in enumerate(selected_items):
            for module in selected_modules:
                variants_map = parsed.hierarchy.get(module, {}).get(item, {})
                if not variants_map:
                    continue

                plan = build_variant_group_plan(variants_map=variants_map, selected_variants=selected_variants)
                if not plan.all_variant_columns:
                    continue

                cache_started = perf_counter()
                cached_plots_by_machine = build_machine_module_cache(
                    df=df,
                    parsed=parsed,
                    variants_map=variants_map,
                    sub_machines=sub_machines_global,
                    module=module,
                    module_no_label=module_no_label,
                    selected_module_nos=selected_module_nos,
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
                log_duration(
                    logger,
                    "chart.build_family_cache",
                    cache_started,
                    enable_perf_logging,
                    extra=f"module={module}; item={item}",
                )

                machine_header_shown: Dict[str, bool] = {machine: False for machine in sub_machines_global}
                is_single_machine_layout = len(sub_machines_global) == 1
                title_base = f"{module} / {item}"

                for family_label, items_in_group in plan.groups.items():
                    variant_names = [variant_name for variant_name, _ in items_in_group]
                    variant_columns = [col_name for _, col_name in items_in_group]
                    if not variant_columns:
                        continue

                    label_map = {col_name: variant_name for variant_name, col_name in items_in_group}
                    title = (
                        f"{title_base} / {family_label}"
                        if family_label != variant_names[0]
                        else f"{title_base} / {variant_names[0]}"
                    )

                    visible_plots_by_machine = family_visible_cache.get(family_label, {machine: [] for machine in sub_machines_global})

                    if not any(visible_plots_by_machine[machine] for machine in sub_machines_global):
                        continue

                    st.markdown(f"#### {title}")
                    cols = st.columns(len(sub_machines_global))
                    for idx_m, machine in enumerate(sub_machines_global):
                        with cols[idx_m]:
                            if not machine_header_shown.get(machine, False):
                                st.markdown(f"**{machine}**")
                                machine_header_shown[machine] = True

                            for mod_no, per_machine_res, base_time_baseline, _is_over_threshold in visible_plots_by_machine[machine]:
                                is_motion_group = family_label == "Motion Time"
                                fig = plot_variants_combined(
                                    agg=per_machine_res,
                                    variants=variant_columns,
                                    title=f"{mod_no}" if mod_no else "",
                                    max_threshold_pct=max_threshold_pct,
                                    min_threshold_pct=min_threshold_pct,
                                    machine_label_column=None,
                                    label_map=label_map,
                                    highlight_variant_column=(
                                        next(
                                            (
                                                col_name
                                                for variant_name, col_name in items_in_group
                                                if variant_name == variant_highlight
                                            ),
                                            None,
                                        )
                                        if (variant_highlight != "(None)" and variant_highlight != "(All)")
                                        else None
                                    ),
                                    highlight_all=variant_highlight == "(All)",
                                    base_time_baseline=base_time_baseline,
                                    header_title=title_base,
                                    machine_display=str(machine),
                                    header_once=is_motion_group,
                                    header_suffix=(family_label if is_motion_group else None),
                                )
                                chart_key = (
                                    f"plotly_{module}_{item}_{family_label}_{machine}_{idx_item}_{idx_m}_{mod_no}"
                                    .replace("/", "_")
                                    .replace(" ", "_")
                                )
                                is_short_series = len(per_machine_res.daily) <= SHORT_SERIES_POINT_THRESHOLD
                                if is_short_series and is_single_machine_layout:
                                    left_col, center_col, right_col = st.columns([1, 2, 1])
                                    with center_col:
                                        st.plotly_chart(
                                            fig,
                                            width="content",
                                            config={"displaylogo": False, "displayModeBar": True},
                                            key=chart_key,
                                        )
                                else:
                                    st.plotly_chart(
                                        fig,
                                        width="stretch",
                                        config={"displaylogo": False, "displayModeBar": True},
                                        key=chart_key,
                                    )
                                rendered_charts += 1

        if rendered_charts == 0:
            st.markdown(
                "<div class='empty-state-message'>No data to show within these parameters</div>",
                unsafe_allow_html=True,
            )

        log_duration(
            logger,
            "chart.render_total",
            total_started,
            enable_perf_logging,
            extra=f"charts={rendered_charts}",
        )
