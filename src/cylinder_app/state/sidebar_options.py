from __future__ import annotations

import pandas as pd
import streamlit as st

from .options import MOTION_TRIPLET


def build_module_no_options(
    df: pd.DataFrame,
    selected_modules: list[str],
    module_no_label: str,
) -> list[str]:
    module_nos_all: set[str] = set()
    for module in selected_modules:
        column_name = f"{module}/{module_no_label}"
        if column_name in df.columns:
            module_nos_all.update(df[column_name].dropna().astype(str).unique())
    return sorted(module_nos_all)


@st.cache_data(show_spinner=False)
def build_module_no_options_cached(
    df: pd.DataFrame,
    selected_modules: tuple[str, ...],
    module_no_label: str,
) -> list[str]:
    return build_module_no_options(df=df, selected_modules=list(selected_modules), module_no_label=module_no_label)


@st.cache_data(show_spinner=False)
def build_item_options_cached(
    hierarchy: dict[str, dict[str, dict[str, str]]],
    selected_modules: tuple[str, ...],
) -> list[str]:
    items_all: set[str] = set()
    for module in selected_modules:
        items_all.update(hierarchy.get(module, {}).keys())
    return sorted(items_all)


@st.cache_data(show_spinner=False)
def build_variant_options_cached(
    hierarchy: dict[str, dict[str, dict[str, str]]],
    selected_modules: tuple[str, ...],
    selected_items: tuple[str, ...],
) -> list[str]:
    selected_items_set = set(selected_items)
    variants_all: set[str] = set()
    for module in selected_modules:
        for item, variant_map in hierarchy.get(module, {}).items():
            if item in selected_items_set:
                variants_all.update(variant_map.keys())
    return sorted(variants_all)


def choose_default_variants(
    variant_options: list[str],
    prefer_motion_time_triplet: bool,
) -> list[str]:
    has_motion_triplet = all(variant in variant_options for variant in MOTION_TRIPLET)
    if prefer_motion_time_triplet and has_motion_triplet:
        return list(MOTION_TRIPLET)
    return variant_options[:1] if variant_options else []