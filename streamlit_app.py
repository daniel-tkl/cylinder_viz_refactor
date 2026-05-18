from __future__ import annotations

import streamlit as st
from src.config import DefaultConfigs
from src.cylinder_app.app_flow import prepare_app_data
from src.cylinder_app.ui import (
    initialize_app_bootstrap,
    build_base_sidebar_controls,
    build_sidebar_state,
    compute_matrix_slice,
    render_chart_view,
    render_table_view,
)
from src.shared.analytics_adapter import start_usage_tracking, stop_usage_tracking
from src.shared.perf import render_perf_panel, reset_perf_metrics

DEFAULTS: DefaultConfigs = DefaultConfigs()


def main():
    initialize_app_bootstrap()
    reset_perf_metrics(DEFAULTS.enable_perf_logging)
    start_usage_tracking(load_from_json="usage_log_2026-05-15.txt")
    try:
        # Aggregation is inferred per variant type (Max/Min/Average/Width → Range; others → Average)
        threshold_state, view_mode, display_mode, machines_per_row = build_base_sidebar_controls(DEFAULTS)
        app_data = prepare_app_data(defaults=DEFAULTS)
        df = app_data.df
        parsed = app_data.parsed
        selected_models = app_data.selected_models
        status_placeholder = app_data.status_placeholder

        machines = sorted([str(x) for x in df[parsed.id_column].dropna().unique().tolist()])
        modules = sorted(list(parsed.hierarchy.keys()))
        module_no_label = "Block Module No"
        sidebar_state = build_sidebar_state(
            defaults=DEFAULTS,
            df=df,
            parsed=parsed,
            selected_models=selected_models,
            threshold_state=threshold_state,
            view_mode=view_mode,
            display_mode=display_mode,
            machines_per_row=machines_per_row,
            machine_options=machines,
            module_options=modules,
            module_no_label=module_no_label,
        )
        max_threshold_pct = threshold_state.max_threshold_pct
        min_threshold_pct = threshold_state.min_threshold_pct
        selected_machines = sidebar_state.selection.selected_machines
        selected_modules = sidebar_state.selection.selected_modules
        selected_module_nos = sidebar_state.selection.selected_module_nos
        selected_items = sidebar_state.selection.selected_items
        selected_variants = sidebar_state.selection.selected_variants
        variant_highlight = sidebar_state.selection.variant_highlight

        # If no variants are selected, avoid clutter by not rendering any charts
        if not selected_variants:
            st.info("Select variants in the sidebar to display charts.")
            st.stop()
        if not selected_modules or not selected_items:
            st.warning("Select at least one Module and Item.")
            st.stop()
        if max_threshold_pct < 0.0 or min_threshold_pct < 0.0:
            st.warning("Threshold percentages must be non-negative.")
            st.stop()

        # Global matrix pagination across all rows (after machines selection)
        sub_machines_global, _, _ = compute_matrix_slice(
            selected_machines=selected_machines,
            all_machines=machines,
            machines_per_row=machines_per_row,
            matrix_page=sidebar_state.view.matrix_page,
        )
        if not sub_machines_global:
            st.warning("No machines available to display.")
            st.stop()

        if view_mode == "Table":
            render_table_view(
                df=df,
                parsed=parsed,
                selected_items=selected_items,
                selected_modules=selected_modules,
                selected_variants=selected_variants,
                sub_machines_global=sub_machines_global,
                selected_module_nos=selected_module_nos,
                module_no_label=module_no_label,
                display_mode=display_mode,
                max_threshold_pct=max_threshold_pct,
                min_threshold_pct=min_threshold_pct,
                selected_machines=selected_machines,
                enable_perf_logging=DEFAULTS.enable_perf_logging,
            )
        if view_mode == "Chart":
            render_chart_view(
                df=df,
                parsed=parsed,
                selected_items=selected_items,
                selected_modules=selected_modules,
                selected_variants=selected_variants,
                sub_machines_global=sub_machines_global,
                selected_module_nos=selected_module_nos,
                module_no_label=module_no_label,
                display_mode=display_mode,
                max_threshold_pct=max_threshold_pct,
                min_threshold_pct=min_threshold_pct,
                variant_highlight=variant_highlight,
                enable_perf_logging=DEFAULTS.enable_perf_logging,
            )
        status_placeholder.success("Data Processing & Rendering Charts Finished.")
    finally:
        render_perf_panel(DEFAULTS.enable_perf_logging)
        stop_usage_tracking(save_to_json="usage_log_2026-05-15.txt")
    
if __name__ == "__main__":
    main()