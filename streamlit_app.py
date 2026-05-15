from __future__ import annotations

import os, math, sys, logging, sys
import numpy as np
import pandas as pd
import streamlit as st

from datetime import date
from typing import Dict, List, Set
from pathlib import Path
from dataclasses import dataclass
import plotly.graph_objects as go

# Ensure local src/ package is importable
sys.path.append(str(Path(__file__).parent / "src"))
sys.path.append(str(Path(__file__).parent / "assets"))

from config import DefaultConfigs
from cylinder_viz.parsing import ParseResult, parse_dataset
from cylinder_viz.aggregation import AggregationMethod, AggregationResult, aggregate_daily
from cylinder_viz.visualization import plot_variants_combined
from utils.helper import _variant_family_label, _group_has_over_threshold, _read_data, highlight_ng
from utils.view import local_css, set_bg, set_sidebar_img
import streamlit_analytics2 as streamlit_analytics


page_element="""
<style>
[data-testid="stSidebar"]> div:first-child{
background-image: url("https://wallpapers.com/images/high/dark-blue-background-high-technology-system-4w0bkhpndvqm4ayb.webp");
background-size: cover;
}
</style>
"""
st.markdown(page_element, unsafe_allow_html=True)

today_date = date.today()

st.set_page_config(
    page_title="Cylinder Data Viz",
    page_icon="assets/favicon.ico", 
    layout="wide"
)
# Hiding hamburger menu from streamlit
hide_streamlit_style = """      
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Loading CSS & BG
css_path = os.path.join("assets", "custom.css")
bg_path = os.path.join("assets", "bg.png")
local_css(css_path)
set_bg(bg_path)
    
list_view: Dict = {
    "Equipment":[], 
    "Motion":[], 
    "Module":[], 
    "Result":[],
    "Base":[], 
    "Min":[], 
    "Avg":[], 
    "Max":[], 
    "Threshold_Min":[], 
    "Threshold_Max":[],
    "Daily Min":[],
    "Daily Avg":[],
    "Daily Max":[],
}

st.markdown("<h1 style='text-align: center;'>Cylinder Data Application</h1>", 
            unsafe_allow_html=True)

DEFAULTS: DefaultConfigs = DefaultConfigs()


def main():
    streamlit_analytics.start_tracking(load_from_json="usage_log_2026-05-15.txt")
    # Aggregation is inferred per variant type (Max/Min/Average/Width → Range; others → Average)
    set_sidebar_img()
    st.sidebar.title("Filter Controls")
    max_threshold_pct: float = st.sidebar.number_input(
        "Max Threshold %",
        min_value=0.0,
        max_value=100.0,
        value=DEFAULTS.max_threshold_pct,
        step=0.5,
        help="Baseline × (1 + max%) forms upper threshold line per variant.",
    )
    min_threshold_pct: float = st.sidebar.number_input(
        "Min Threshold %",
        min_value=0.0,
        max_value=100.0,
        value=DEFAULTS.min_threshold_pct,
        step=0.5,
        help="Baseline × (1 - min%) forms lower threshold line per variant.",
    )

    # Thresholds are shown only as a per-variant band when a highlight variant is selected
    # Display mode selector: show all charts or only over-threshold charts
    view_options: List[str] = ["Table", "Chart"]
    view_mode: str = st.sidebar.radio(
        "View Mode",
        options=view_options,
        index=(view_options.index(DEFAULTS.view_mode) if DEFAULTS.view_mode in view_options else 0),
        help=(
            "When set to 'Chart', show charts. "
            "When set to 'Table', show table. "
        ),
    )
    display_options: List[str] = ["Over-threshold only", "All charts"]
    display_mode: str = st.sidebar.radio(
        "Display Mode",
        options=display_options,
        index=(display_options.index(DEFAULTS.display_mode) if DEFAULTS.display_mode in display_options else 0),
        help=(
            "When set to 'Over-threshold only', only charts where any variant's "
            "daily values exceed the computed threshold band (above max or below min) "
            "will be shown. Thresholds are derived from the per-variant baseline."
        ),
    )
    machines_per_row: int = st.sidebar.number_input(
        "Machines per row",
        min_value=1,
        max_value=20,
        value=10,
        step=1,
        help="Controls how many machine charts appear side-by-side per row.",
    )
    # Upload file
    if 'data' not in st.session_state:
        st.session_state["data"] = None
        
    _, middle_upload_col, _ = st.columns([1, 3, 1])

    with middle_upload_col:
        uploaded_file = st.file_uploader(
            "Upload CSV or Excel data",
            type=["csv", "xlsx", "xls"],
            help="Dataset must include a machine/device identifier and a datetime column."
        )
        
    _, middle, _ = st.columns([1, 3, 1])
    status_placeholder = middle.empty()

    if uploaded_file is not None:
        try:
            df = _read_data(uploaded_file)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Failed to read file: {exc}")
            st.stop()
    else:
        st.info("Please upload a file to proceed.")
        st.stop()

    model_col = next((c for c in df.columns if str(c).strip().lower() == "model"), None)
    selected_models: List[str] = []
    if model_col:
        models = sorted([str(x) for x in df[model_col].dropna().unique().tolist()])
        selected_models = st.sidebar.multiselect(
            "Model(s)", 
            options=models, 
            default=(models if DEFAULTS.select_all_models else (models[:1] if models else [])),
            help="Filter dataset rows by Model before parsing and aggregation."
        )
        if selected_models:
            df = df[df[model_col].isin(selected_models)]
    try:
        parsed: ParseResult = parse_dataset(df)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Parsing error: {exc}")
        st.stop()

    # Sidebar selections
    machines = sorted([str(x) for x in df[parsed.id_column].dropna().unique().tolist()])
    selected_machines: List[str] = st.sidebar.multiselect(
        "Machine No(s)", 
        options=machines, 
        default=(machines if DEFAULTS.select_all_machines else (machines[:1] if machines else [])),
        help="Select one or more machines to compare."
    )
    modules = sorted(list(parsed.hierarchy.keys()))
    selected_modules: List[str] = st.sidebar.multiselect(
        "Module(s)", 
        options=modules, 
        default=(modules if DEFAULTS.select_all_modules else (modules[:1] if modules else [])),
        help="Modules are parsed from column names (prefix before first '/')."
    )
    # --- Build module numbers (Block Module No) based on module selection ---
    module_no_label = "Block Module No"
    module_nos_all: Set[str] = set()
    for m in selected_modules:
        # Find all Block Module No values for this module
        col_name = f"{m}/{module_no_label}"
        if col_name in df.columns:
            module_nos_all.update(df[col_name].dropna().astype(str).unique())
    module_nos = sorted(list(module_nos_all))
    selected_module_nos: List[str] = st.sidebar.multiselect(
        "Module No(s)", 
        options=module_nos, 
        default=(module_nos if module_nos else []),
        help="Module numbers (Block Module No) parsed from columns for each selected module."
    )
    # Build items based on module and module number selection
    items_all: Set[str] = set()
    for m in selected_modules:
        for mod_no in selected_module_nos or [None]:
            # If module number is selected, filter items by rows with that module number
            if mod_no is not None:
                col_name = f"{m}/{module_no_label}"
                if col_name in df.columns:
                    filtered_df = df[df[col_name].astype(str) == str(mod_no)]
                    items_all.update(list(parsed.hierarchy.get(m, {}).keys()))
            else:
                items_all.update(list(parsed.hierarchy.get(m, {}).keys()))
    items = sorted(list(items_all))
    selected_items: List[str] = st.sidebar.multiselect(
        "Item(s)", 
        options=items, 
        default=(items if DEFAULTS.select_all_items else (items[:1] if items else [])),
        help="Items are parsed per selected modules and module numbers (middle section)."
    )
    # Variant filter across selected modules/items/module numbers
    variants_all: Set[str] = set()
    for m in selected_modules:
        for mod_no in selected_module_nos or [None]:
            for it, vmap in parsed.hierarchy.get(m, {}).items():
                if it in selected_items:
                    variants_all.update(list(vmap.keys()))
    variant_options = sorted(list(variants_all))
    # Default variants: prefer Motion Time triplet if available; otherwise pick any one
    motion_triplet: List[str] = ["Motion Time Average", "Motion Time Min", "Motion Time Max"]
    has_motion_triplet: bool = all(v in variant_options for v in motion_triplet)
    default_variants: List[str] = (
        motion_triplet if (DEFAULTS.prefer_motion_time_triplet and has_motion_triplet) else (variant_options[:1] if variant_options else [])
    )
    selected_variants: List[str] = st.sidebar.multiselect(
        "Variant(s)", 
        options=variant_options, 
        default=default_variants,
        help="Filter which variants to include across all selected items/modules/module numbers."
    )
    # Optional: Highlight a single variant for thresholds when using per-variant lines
    # Always highlight all variants for thresholds
    variant_highlight: str = "(All)"

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

    use_multi_machine = len(selected_machines) > 1

    # Global matrix pagination across all rows (after machines selection)
    machine_list = selected_machines or ([machines[0]] if machines else [])
    if not machine_list:
        st.warning("No machines available to display.")
        st.stop()
    total_machines = len(machine_list)
    pages = max(1, math.ceil(total_machines / machines_per_row))
    matrix_page = st.sidebar.number_input(
        "Matrix page",
        min_value=1,
        max_value=pages,
        value=1,
        step=1,
        help="Navigate machine charts when many are selected.",
    )
    start_idx = (matrix_page - 1) * machines_per_row
    end_idx = start_idx + machines_per_row
    sub_machines_global = machine_list[start_idx:end_idx]

    # menu Option
    if view_mode == "Table":
        with st.spinner(text="In progress...  Please Wait... ", show_time=True, width="content"):
            for idx_item, item in enumerate(selected_items):
                for module in selected_modules:
                    variants_map = parsed.hierarchy.get(module, {}).get(item, {})
                    if not variants_map:
                        continue
                    # Build groups of variants: family label -> list of (variant_name, column_name)
                    groups: Dict[str, List[tuple[str, str]]] = {}
                    for variant_name, col_name in variants_map.items():
                        if selected_variants and variant_name not in selected_variants:
                            continue
                        fam = _variant_family_label(variant_name)
                        groups.setdefault(fam, []).append((variant_name, col_name))

                    # Track if we've shown the machine header for this page already
                    # _machine_header_shown: Dict[str, bool] = {m: False for m in sub_machines_global}

                    title_base = f"{module} / {item}"

                    # Render per group: multi-variant families together, otherwise single charts
                    for fam_label, items_in_group in groups.items():
                        variant_names = [vn for vn, _ in items_in_group]
                        variant_columns = [cn for _, cn in items_in_group]
                        if not variant_columns:
                            continue
                        label_map = {col: vn for vn, col in items_in_group}
                        title = f"{title_base} / {fam_label}" if fam_label != variant_names[0] else f"{title_base} / {variant_names[0]}"

                        def _infer_method_for_variant(vn: str) -> AggregationMethod:
                            v = vn.strip().lower()
                            if "max" in v:
                                return "max"
                            if "min" in v:
                                return "min"
                            if "average" in v:
                                return "average"
                            if "width" in v:
                                return "range"
                            if "range" in v:
                                return "range"
                            return "average"

                        method_map = {col: _infer_method_for_variant(vn) for vn, col in items_in_group}

                        # Compute visible module numbers per machine for this group
                        sub_machines = sub_machines_global
                        module_no_col = f"{module}/{module_no_label}"
                        visible_plots_by_machine: Dict[str, List[tuple[str, AggregationResult, float | None]]] = {m: [] for m in sub_machines}

                        for machine in sub_machines:
                            df_machine = df[df[parsed.id_column].astype(str) == str(machine)]
                            # Candidate module numbers
                            if module_no_col in df_machine.columns:
                                mod_nos = (
                                    df_machine[module_no_col]
                                    .dropna()
                                    .astype(str)
                                    .unique()
                                    .tolist()
                                )
                                # Intersect with selected_module_nos if provided
                                if 'selected_module_nos' in locals() and selected_module_nos:
                                    mod_nos = [mn for mn in mod_nos if mn in set(selected_module_nos)]
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
                                    )
                                except Exception:
                                    continue

                                sub = per_machine_res.daily[variant_columns] if not per_machine_res.daily.empty else None
                                has_data = sub is not None and sub.notna().any().any()
                                base_time_col = next((c for vn, c in variants_map.items() if vn.strip().lower() == "base time"), None)
                                base_time_baseline = None
                                
                                if base_time_col is not None:
                                    try:
                                        base_res = aggregate_daily(
                                            df=df_mod,
                                            id_column=parsed.id_column,
                                            datetime_column=parsed.datetime_column,
                                            selected_columns=[base_time_col],
                                            method={base_time_col: "average"},
                                            machines=[machine],
                                        )
                                        base_time_baseline = base_res.baselines.get(base_time_col)
                                    except Exception:
                                        base_time_baseline = None
                                        
                                if display_mode == "Over-threshold only":
                                    if not _group_has_over_threshold(
                                        agg=per_machine_res,
                                        variant_columns=variant_columns,
                                        label_map=label_map,
                                        base_time_baseline=base_time_baseline,
                                        max_pct=max_threshold_pct,
                                        min_pct=min_threshold_pct,
                                    ):
                                        continue
                                else:
                                    if not has_data:
                                        continue
                                visible_plots_by_machine[machine].append((str(mod_no) if mod_no is not None else "", per_machine_res, base_time_baseline))

                        # Skip group if no machines have visible module numbers
                        if not any(visible_plots_by_machine[m] for m in sub_machines):
                            continue

                        # Render group header and machine columns
                        # cols = st.columns(len(sub_machines))
                        for idx_m, machine in enumerate(sub_machines):
                            # with cols[idx_m]:
                                # Show machine header once per page
                                # if not _machine_header_shown.get(machine, False):
                                #     _machine_header_shown[machine] = True

                                for mod_no, per_machine_res, base_time_baseline in visible_plots_by_machine[machine]:
                                    list_view["Equipment"].append(machine)
                                    list_view["Motion"].append(title)               
                                    list_view["Module"].append(mod_no)
                                    list_view["Threshold_Min"].append((1-(min_threshold_pct/100))*base_time_baseline)
                                    list_view["Threshold_Max"].append((1+(max_threshold_pct/100))*base_time_baseline)
                                    list_view["Base"].append(base_time_baseline)
                                    list_view["Avg"].append(per_machine_res.baselines.get(f"{module}/{item}/Motion Time Average"))
                                    list_view["Min"].append(per_machine_res.baselines.get(f"{module}/{item}/Motion Time Min"))
                                    list_view["Max"].append(per_machine_res.baselines.get(f"{module}/{item}/Motion Time Max"))
                                    list_view["Daily Min"].append(per_machine_res.daily.get(f"{module}/{item}/Motion Time Min"))
                                    list_view["Daily Avg"].append(per_machine_res.daily.get(f"{module}/{item}/Motion Time Average"))
                                    list_view["Daily Max"].append(per_machine_res.daily.get(f"{module}/{item}/Motion Time Max"))
                                    # Skipping data which not over-threshold
                                    if _group_has_over_threshold(
                                        agg=per_machine_res,
                                        variant_columns=variant_columns,
                                        label_map=label_map,
                                        base_time_baseline=base_time_baseline,
                                        max_pct=max_threshold_pct,
                                        min_pct=min_threshold_pct,
                                    ):
                                        list_view["Result"].append("NG")
                                    else:
                                        list_view["Result"].append("OK")
                                    is_motion_group = (fam_label == "Motion Time")
                                    # st.session_state.data = list_view
                                    # df_all = pd.DataFrame(list_view)
            df_all = pd.DataFrame(list_view)
            
            if display_mode == "Over-threshold only":
                df_all = df_all[df_all["Result"] == "NG"]
                
            # Filtering data
            
            
                pattern_modules = "|".join(selected_modules)
                pattern_items = "|".join(selected_items)
                df_all = df_all[df_all["Equipment"].isin(selected_machines)]
                df_all = df_all[df_all["Module"].isin(selected_module_nos)]
            
                # Modules & items are in one columns
                df_all = df_all[df_all["Motion"].str.contains(pattern_modules, na=False)]
                df_all = df_all[df_all["Motion"].str.contains(pattern_items, na=False)]
                NG_list = df_all[df_all["Result"] == "NG"]
                OK_list = df_all[df_all["Result"] == "OK"]
            
            st.markdown("<h2 style='text-align: center;'>List of Data</h2>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            
            if display_mode == "Over-threshold only":
                with col1:
                    st.write(f"- Total Data:", len(df_all))
            else:
                with col1:
                    st.write(f"- Total Data:", len(df_all))
                with col2:
                    st.write(f"- Total NG:", len(NG_list))
                with col3:
                    st.write(f"- Total OK:", len(OK_list))
                
            df_to_select = df_all.copy()
            drop_list = ['Daily', 'Threshold']
            pattern_drop_list = '|'.join(drop_list)
            df_to_select = df_to_select.loc[:, ~df_to_select.columns.str.contains(pattern_drop_list)]
            selected_x = st.dataframe(
                    df_to_select.style.map(highlight_ng, subset=["Result"]).format(precision=0),
                    key="selected_data",
                    on_select="rerun",
                    selection_mode=["single-cell"],
            )
            st.space()
            try:
                idx = selected_x.selection.get("cells")[0][0]
                threshold_data = df_all.iloc[idx].to_frame().T
                selected_data = df_all.iloc[idx].to_frame().T
                idx = selected_data["Daily Avg"].values.tolist()[0].index.tolist()
                daily_min = selected_data["Daily Min"].values.tolist()[0].tolist()
                daily_avg = selected_data["Daily Avg"].values.tolist()[0].tolist()
                daily_max = selected_data["Daily Max"].values.tolist()[0].tolist()
                equipment = selected_data["Equipment"].values.tolist()[0]
                motion = selected_data["Motion"].values.tolist()[0]
                selected_viz = pd.DataFrame({
                    "Date": idx,
                    "min": daily_min,
                    "avg": daily_avg,
                    "max": daily_max,
                    "equipment": equipment
                })
            except IndexError:
                st.markdown("<h2 style='text-align: center;'>Select Data from Table Above to Visualize</h2>", 
                unsafe_allow_html=True)
            else:
                st.markdown("<h2 style='text-align: center;'>Visualization from Above Data Point</h2>",
                unsafe_allow_html=True)
                # Custom data for hoover template
                customdata = np.stack((
                    selected_data["Motion"], 
                    selected_data["Equipment"], 
                    selected_data["Module"], 
                    selected_data["Motion"]
                ), axis=1
            )
                customdata = [item for item in customdata for _ in range(len(selected_viz))] # Duplicate every item in the list
                hover_tmpl = (
                    "<span style='font-size:16px'><b>%{customdata[0]}</b></span>"  # Header
                    "<br><span style='font-size:14px'><b>Machine:</b> %{customdata[1]}</span>"  # Machine line
                    "<br><span style='font-size:12px'><b>Module:</b> %{customdata[2]}</span>"  # Module line
                    "<br><br><b>Motion Time Max</b>"  # Variant label
                    "<br><b>Date:</b> %{x}"  # Date line
                    "<br><b>Value:</b> %{y:.0f}"  # Value line
                    "<extra></extra>"
                )
                hover_tmpl_avg = (
                    "<br><br><b>Motion Time Avg</b>"  # Variant label
                    "<br><b>Date:</b> %{x}"  # Date line
                    "<br><b>Value:</b> %{y:.0f}"  # Value line
                    "<extra></extra>"
                )
                hover_tmpl_min = (
                    "<br><br><b>Motion Min</b>"  # Variant label
                    "<br><b>Date:</b> %{x}"  # Date line
                    "<br><b>Value:</b> %{y:.0f}"  # Value line
                    "<extra></extra>"
                )
                
                selected_data_viz = selected_data.loc[:, ~selected_data.columns.str.contains(pattern_drop_list)] \
                .style.map(highlight_ng, subset=["Result"]) \
                .format(precision=0)
                
                st.write(selected_data_viz)
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        y=selected_viz["max"],
                        x=selected_viz["Date"],
                        mode='lines+markers',
                        customdata=customdata,
                        marker=dict(color='red'),
                        hovertemplate=hover_tmpl,
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        y=selected_viz["avg"],
                        x=selected_viz["Date"],
                        mode='lines+markers',
                        customdata=customdata,
                        marker=dict(color='green'),
                        hovertemplate=hover_tmpl_avg
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        y=selected_viz["daily_min"],
                        x=selected_viz["Date"],
                        mode='lines+markers',
                        customdata=customdata,
                        marker=dict(color='cyan'),
                        hovertemplate=hover_tmpl_min
                    )
                )
                fig.add_hline(
                    y=threshold_data["Threshold_Max"].values[0],
                    line=dict(color="#d62728", dash="dot"),
                    annotation_text=f"Max {selected_data["Max"].values.tolist()[0]}",
                    annotation_position="top right",
                )
                fig.add_hline(
                    y=threshold_data["Threshold_Min"].values[0],
                    line=dict(color="#2ca02c", dash="dot"),
                    annotation_text=f"Min {selected_data["Daily Min"].values.tolist()[0]}",
                    annotation_position="bottom right",
                )
                x0 = selected_viz.Date.min()
                x1 = selected_viz.Date.max()
                fig.add_shape(
                    type="rect",
                    xref="x",
                    yref="y",
                    x0=x0,
                    x1=x1,
                    y0=threshold_data["Threshold_Max"].values[0],
                    y1=threshold_data["Threshold_Min"].values[0],
                    line=dict(width=0),
                    # Light green band to represent min-max threshold area
                    fillcolor="rgba(44, 160, 44, 0.12)",
                    )
                fig.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Value",
                    showlegend=False,
                    hovermode="x unified",
                    hoverlabel=dict(
                        bgcolor="rgba(0,0,0,0.75)",
                        bordercolor="#cccccc",
                        font=dict(size=12),
                    )
                )
                fig.update_layout(
                    title={
                        'text': f"{customdata[0][0]}",
                        'y': 0.9,
                        'x': 0.5,
                        'xanchor': 'center',
                        'yanchor': 'top',
                        'font': dict(size=24, color="white")
                    }
                )
                fig.update_xaxes(tickformat="%Y-%m-%d")
                st.plotly_chart(fig, width='stretch')
    if view_mode == "Chart":
        with st.spinner(text="In progress...  Please Wait... ", 
                        show_time=True, 
                        width="content"
        ):
            st.markdown("<h2 style='text-align: center;'>Chart Visualization</h2>", 
                unsafe_allow_html=True)
            for idx_item, item in enumerate(selected_items):
                for module in selected_modules:
                    variants_map = parsed.hierarchy.get(module, {}).get(item, {})
                    if not variants_map:
                        continue
                    # Build groups of variants: family label -> list of (variant_name, column_name)
                    groups: Dict[str, List[tuple[str, str]]] = {}
                    for variant_name, col_name in variants_map.items():
                        if selected_variants and variant_name not in selected_variants:
                            continue
                        fam = _variant_family_label(variant_name)
                        groups.setdefault(fam, []).append((variant_name, col_name))

                    # Track if we've shown the machine header for this page already
                    _machine_header_shown: Dict[str, bool] = {m: False for m in sub_machines_global}

                    title_base = f"{module} / {item}"

                    # Render per group: multi-variant families together, otherwise single charts
                    for fam_label, items_in_group in groups.items():
                        variant_names = [vn for vn, _ in items_in_group]
                        variant_columns = [cn for _, cn in items_in_group]
                        if not variant_columns:
                            continue
                        label_map = {col: vn for vn, col in items_in_group}
                        title = f"{title_base} / {fam_label}" if fam_label != variant_names[0] else f"{title_base} / {variant_names[0]}"

                        def _infer_method_for_variant(vn: str) -> AggregationMethod:
                            v = vn.strip().lower()
                            if "max" in v:
                                return "max"
                            if "min" in v:
                                return "min"
                            if "average" in v:
                                return "average"
                            if "width" in v:
                                return "range"
                            if "range" in v:
                                return "range"
                            return "average"

                        method_map = {col: _infer_method_for_variant(vn) for vn, col in items_in_group}

                        # Compute visible module numbers per machine for this group
                        sub_machines = sub_machines_global
                        module_no_col = f"{module}/{module_no_label}"
                        visible_plots_by_machine: Dict[str, List[tuple[str, AggregationResult, float | None]]] = {m: [] for m in sub_machines}

                        for machine in sub_machines:
                            df_machine = df[df[parsed.id_column].astype(str) == str(machine)]
                            # Candidate module numbers
                            if module_no_col in df_machine.columns:
                                mod_nos = (
                                    df_machine[module_no_col]
                                    .dropna()
                                    .astype(str)
                                    .unique()
                                    .tolist()
                                )
                                # Intersect with selected_module_nos if provided
                                if 'selected_module_nos' in locals() and selected_module_nos:
                                    mod_nos = [mn for mn in mod_nos if mn in set(selected_module_nos)]
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
                                    )
                                except Exception:
                                    continue

                                sub = per_machine_res.daily[variant_columns] if not per_machine_res.daily.empty else None
                                has_data = sub is not None and sub.notna().any().any()

                                base_time_col = next((c for vn, c in variants_map.items() if vn.strip().lower() == "base time"), None)
                                base_time_baseline = None
                                if base_time_col is not None:
                                    try:
                                        base_res = aggregate_daily(
                                            df=df_mod,
                                            id_column=parsed.id_column,
                                            datetime_column=parsed.datetime_column,
                                            selected_columns=[base_time_col],
                                            method={base_time_col: "average"},
                                            machines=[machine],
                                        )
                                        base_time_baseline = base_res.baselines.get(base_time_col)
                                    except Exception:
                                        base_time_baseline = None

                                if display_mode == "Over-threshold only":
                                    if not _group_has_over_threshold(
                                        agg=per_machine_res,
                                        variant_columns=variant_columns,
                                        label_map=label_map,
                                        base_time_baseline=base_time_baseline,
                                        max_pct=max_threshold_pct,
                                        min_pct=min_threshold_pct,
                                    ):
                                        continue
                                else:
                                    if not has_data:
                                        continue

                                visible_plots_by_machine[machine].append((str(mod_no) if mod_no is not None else "", per_machine_res, base_time_baseline))

                        # Skip group if no machines have visible module numbers
                        if not any(visible_plots_by_machine[m] for m in sub_machines):
                            continue

                        # Render group header and machine columns
                        st.markdown(f"#### {title}")
                        cols = st.columns(len(sub_machines))
                        for idx_m, machine in enumerate(sub_machines):
                            with cols[idx_m]:
                                # Show machine header once per page
                                if not _machine_header_shown.get(machine, False):
                                    st.markdown(f"**{machine}**")
                                    _machine_header_shown[machine] = True

                                for mod_no, per_machine_res, base_time_baseline in visible_plots_by_machine[machine]:
                                    is_motion_group = (fam_label == "Motion Time")
                                    fig = plot_variants_combined(
                                        agg=per_machine_res,
                                        variants=variant_columns,
                                        title=f"{mod_no}" if mod_no else "",
                                        max_threshold_pct=max_threshold_pct,
                                        min_threshold_pct=min_threshold_pct,
                                        machine_label_column=None,
                                        label_map=label_map,
                                        highlight_variant_column=(
                                            next((col for vn, col in items_in_group if vn == variant_highlight), None)
                                            if (variant_highlight != "(None)" and variant_highlight != "(All)") else None
                                        ),
                                        highlight_all=(variant_highlight == "(All)"),
                                        base_time_baseline=base_time_baseline,
                                        header_title=title_base,
                                        machine_display=str(machine),
                                        header_once=is_motion_group,
                                        header_suffix=(fam_label if is_motion_group else None),
                                    )
                                    chart_key = (
                                        f"plotly_{module}_{item}_{fam_label}_{machine}_{idx_item}_{idx_m}_{mod_no}"
                                        .replace("/", "_")
                                        .replace(" ", "_")
                                    )
                                    st.markdown(
                                        """
                                        <style>
                                        .js-plotly-plot .hoverlayer {overflow: visible !important;}
                                        </style>
                                        """,
                                        unsafe_allow_html=True,
                                    )
                                    st.plotly_chart(
                                        fig,
                                        width="stretch",
                                        config={"displaylogo": False, "displayModeBar": True},
                                        key=chart_key,
                                    )
                                    fig.update_xaxes(tickformat="%Y-%m-%d")
    status_placeholder.success("Data Processing & Rendering Charts Finished.")
    streamlit_analytics.stop_tracking(save_to_json="usage_log_2026-05-15.txt")
    
if __name__ == "__main__":
    main()