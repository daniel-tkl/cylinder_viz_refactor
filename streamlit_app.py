from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from time import perf_counter

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
from src.shared.analytics_adapter import (
    get_usage_tracking_backend_info,
    start_usage_tracking,
    stop_usage_tracking,
)
from src.shared.perf import render_perf_panel, reset_perf_metrics

DEFAULTS: DefaultConfigs = DefaultConfigs()
LOGS_DIR = Path("logs")
APP_LOG_DIR = LOGS_DIR / "app"
USAGE_LOG_DIR = LOGS_DIR / "usage"
USAGE_LOG_PATH = USAGE_LOG_DIR / f"usage_{datetime.now().strftime('%Y%m%d')}.log"
logger = logging.getLogger(__name__)


def _configure_daily_app_logger() -> Path:
    APP_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = (APP_LOG_DIR / f"app_{datetime.now().strftime('%Y%m%d')}.log").resolve()

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    for handler in root_logger.handlers:
        base_filename = getattr(handler, "baseFilename", None)
        if base_filename and Path(base_filename).resolve() == log_path:
            return log_path

    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    root_logger.addHandler(file_handler)
    return log_path


def _obs(event: str, **fields: object) -> None:
    logger.info("OBS %s %s", event, json.dumps(fields, default=str, sort_keys=True))


def main():
    run_started = perf_counter()
    analytics_disabled = os.environ.get("CYLINDERVIZ_DISABLE_ANALYTICS") == "1"
    app_log_path = _configure_daily_app_logger()
    _obs("logger.ready", path=str(app_log_path))
    _obs("app.start", analytics_disabled=analytics_disabled)
    backend_info = get_usage_tracking_backend_info()
    _obs("analytics.backend", **backend_info)
    initialize_app_bootstrap()
    reset_perf_metrics(DEFAULTS.enable_perf_logging)
    if not analytics_disabled:
        start_usage_tracking(load_from_json=str(USAGE_LOG_PATH))
    try:
        # Aggregation is inferred per variant type (Max/Min/Average/Width → Range; others → Average)
        threshold_state, view_mode, display_mode, machines_per_row = build_base_sidebar_controls(DEFAULTS)
        app_data = prepare_app_data(defaults=DEFAULTS)
        df = app_data.df
        parsed = app_data.parsed
        selected_models = app_data.selected_models
        status_placeholder = app_data.status_placeholder
        _obs(
            "data.prepared",
            file_name=app_data.source_file_name,
            source_rows=app_data.source_rows,
            filtered_rows=app_data.filtered_rows,
            load_ms=round(app_data.load_ms, 2),
            parse_ms=round(app_data.parse_ms, 2),
            selected_models=len(selected_models),
        )

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
        _obs(
            "selection.summary",
            machines=len(selected_machines),
            modules=len(selected_modules),
            module_nos=len(selected_module_nos),
            items=len(selected_items),
            variants=len(selected_variants),
            view_mode=view_mode,
            display_mode=display_mode,
            max_threshold_pct=max_threshold_pct,
            min_threshold_pct=min_threshold_pct,
            machines_per_row=machines_per_row,
            variant_highlight=variant_highlight,
        )

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

        render_started = perf_counter()
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
            _obs(
                "render.completed",
                view_mode="Table",
                render_ms=round((perf_counter() - render_started) * 1000.0, 2),
                machines_rendered=len(sub_machines_global),
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
            _obs(
                "render.completed",
                view_mode="Chart",
                render_ms=round((perf_counter() - render_started) * 1000.0, 2),
                machines_rendered=len(sub_machines_global),
            )
        status_placeholder.success("Data Processing & Rendering Charts Finished.")
    finally:
        _obs("app.end", total_ms=round((perf_counter() - run_started) * 1000.0, 2))
        render_perf_panel(DEFAULTS.enable_perf_logging)
        if not analytics_disabled:
            stop_usage_tracking(save_to_json=str(USAGE_LOG_PATH))
    
if __name__ == "__main__":
    main()