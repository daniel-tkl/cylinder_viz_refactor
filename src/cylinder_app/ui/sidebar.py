from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from src.config import DefaultConfigs
from src.cylinder_domain.parsing import ParseResult

from src.cylinder_app.state.options import (
    DISPLAY_OPTIONS,
    MODULE_NO_LABEL,
    MOTION_TRIPLET,
    VARIANT_HIGHLIGHT_ALL,
    VIEW_OPTIONS,
)
from src.cylinder_app.state.sidebar_state import (
    SelectionState,
    SidebarState,
    ThresholdState,
    ViewMode,
    ViewState,
)
from src.cylinder_app.state.sidebar_options import (
    build_item_options_cached,
    build_module_no_options_cached,
    build_variant_options_cached,
    choose_default_variants,
)


def build_model_selection(
    defaults: DefaultConfigs,
    df: pd.DataFrame,
) -> tuple[list[str], pd.DataFrame]:
    model_col = next((col for col in df.columns if str(col).strip().lower() == "model"), None)
    if model_col is None:
        return [], df

    model_options = sorted([str(value) for value in df[model_col].dropna().unique().tolist()])
    selected_models = st.sidebar.multiselect(
        "Model(s)",
        options=model_options,
        default=(model_options if defaults.select_all_models else (model_options[:1] if model_options else [])),
        help="Filter dataset rows by Model before parsing and aggregation.",
    )
    if selected_models:
        return selected_models, df[df[model_col].isin(selected_models)]
    return selected_models, df


def build_base_sidebar_controls(
    defaults: DefaultConfigs,
) -> tuple[ThresholdState, ViewMode, str, int]:
    st.sidebar.title("Filter Controls")

    max_threshold_pct = st.sidebar.number_input(
        "Max Threshold %",
        min_value=0.0,
        max_value=100.0,
        value=defaults.max_threshold_pct,
        step=0.5,
        help="Baseline × (1 + max%) forms upper threshold line per variant.",
    )
    min_threshold_pct = st.sidebar.number_input(
        "Min Threshold %",
        min_value=0.0,
        max_value=100.0,
        value=defaults.min_threshold_pct,
        step=0.5,
        help="Baseline × (1 - min%) forms lower threshold line per variant.",
    )
    view_mode = st.sidebar.radio(
        "View Mode",
        options=VIEW_OPTIONS,
        index=(VIEW_OPTIONS.index(defaults.view_mode) if defaults.view_mode in VIEW_OPTIONS else 0),
        help=(
            "When set to 'Chart', show charts. "
            "When set to 'Table', show table. "
        ),
    )
    display_mode = st.sidebar.radio(
        "Display Mode",
        options=DISPLAY_OPTIONS,
        index=(DISPLAY_OPTIONS.index(defaults.display_mode) if defaults.display_mode in DISPLAY_OPTIONS else 0),
        help=(
            "When set to 'Over-threshold only', only charts where any variant's "
            "daily values exceed the computed threshold band (above max or below min) "
            "will be shown. Thresholds are derived from the per-variant baseline."
        ),
    )
    machines_per_row = st.sidebar.number_input(
        "Machines per row",
        min_value=1,
        max_value=20,
        value=10,
        step=1,
        help="Controls how many machine charts appear side-by-side per row.",
    )

    return (
        ThresholdState(
            max_threshold_pct=max_threshold_pct,
            min_threshold_pct=min_threshold_pct,
        ),
        view_mode,
        display_mode,
        machines_per_row,
    )


def compute_matrix_slice(
    selected_machines: list[str],
    all_machines: list[str],
    machines_per_row: int,
    matrix_page: int,
) -> tuple[list[str], int, int]:
    machine_list = selected_machines or ([all_machines[0]] if all_machines else [])
    if not machine_list:
        return [], 1, 1

    total_pages = max(1, math.ceil(len(machine_list) / machines_per_row))
    safe_page = min(max(1, matrix_page), total_pages)
    start_idx = (safe_page - 1) * machines_per_row
    end_idx = start_idx + machines_per_row
    return machine_list[start_idx:end_idx], total_pages, safe_page


def build_sidebar_state(
    defaults: DefaultConfigs,
    df: pd.DataFrame,
    parsed: ParseResult,
    selected_models: list[str],
    threshold_state: ThresholdState,
    view_mode: ViewMode,
    display_mode: str,
    machines_per_row: int,
    machine_options: list[str],
    module_options: list[str],
    module_no_label: str = MODULE_NO_LABEL,
) -> SidebarState:
    selected_machines = st.sidebar.multiselect(
        "Machine No(s)",
        options=machine_options,
        default=(machine_options if defaults.select_all_machines else (machine_options[:1] if machine_options else [])),
        help="Select one or more machines to compare.",
    )
    selected_modules = st.sidebar.multiselect(
        "Module(s)",
        options=module_options,
        default=(module_options if defaults.select_all_modules else (module_options[:1] if module_options else [])),
        help="Modules are parsed from column names (prefix before first '/').",
    )

    module_no_options = build_module_no_options_cached(
        df=df,
        selected_modules=tuple(selected_modules),
        module_no_label=module_no_label,
    )
    selected_module_nos = st.sidebar.multiselect(
        "Module No(s)",
        options=module_no_options,
        default=(module_no_options if module_no_options else []),
        help="Module numbers (Block Module No) parsed from columns for each selected module.",
    )

    item_options = build_item_options_cached(
        hierarchy=parsed.hierarchy,
        selected_modules=tuple(selected_modules),
    )
    selected_items = st.sidebar.multiselect(
        "Item(s)",
        options=item_options,
        default=(item_options if defaults.select_all_items else (item_options[:1] if item_options else [])),
        help="Items are parsed per selected modules and module numbers (middle section).",
    )

    variant_options = build_variant_options_cached(
        hierarchy=parsed.hierarchy,
        selected_modules=tuple(selected_modules),
        selected_items=tuple(selected_items),
    )
    selected_variants = st.sidebar.multiselect(
        "Variant(s)",
        options=variant_options,
        default=choose_default_variants(variant_options, defaults.prefer_motion_time_triplet),
        help="Filter which variants to include across all selected items/modules/module numbers.",
    )

    _, total_pages, safe_page = compute_matrix_slice(
        selected_machines=selected_machines,
        all_machines=machine_options,
        machines_per_row=machines_per_row,
        matrix_page=1,
    )
    matrix_page = st.sidebar.number_input(
        "Matrix page",
        min_value=1,
        max_value=total_pages,
        value=safe_page,
        step=1,
        help="Navigate machine charts when many are selected.",
    )

    return SidebarState(
        threshold=threshold_state,
        view=ViewState(
            view_mode=view_mode,
            display_mode=display_mode,
            machines_per_row=machines_per_row,
            matrix_page=matrix_page,
            total_pages=total_pages,
        ),
        selection=SelectionState(
            selected_models=selected_models,
            selected_machines=selected_machines,
            selected_modules=selected_modules,
            selected_module_nos=selected_module_nos,
            selected_items=selected_items,
            selected_variants=selected_variants,
            variant_highlight=VARIANT_HIGHLIGHT_ALL,
        ),
    )
