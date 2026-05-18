from __future__ import annotations

import logging
from time import perf_counter
from typing import List

import pandas as pd
import streamlit as st

from src.cylinder_domain.parsing import ParseResult
from src.shared.dataframe_styles import highlight_ng
from src.shared.perf import log_duration

from .table_data import build_table_dataframe_cached
from .table_plot import build_selected_timeseries_figure
from .table_selection import build_selected_row_payload


STYLED_TABLE_MAX_ROWS = 10000
SHORT_SERIES_POINT_THRESHOLD = 4
logger = logging.getLogger(__name__)


def render_table_view(
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
    selected_machines: List[str],
    enable_perf_logging: bool = False,
) -> None:
    with st.spinner(text="In progress...  Please Wait... ", show_time=True, width="content"):
        total_started = perf_counter()
        table_started = perf_counter()
        df_all = build_table_dataframe_cached(
            df=df,
            parsed=parsed,
            selected_items=tuple(selected_items),
            selected_modules=tuple(selected_modules),
            selected_variants=tuple(selected_variants),
            sub_machines_global=tuple(sub_machines_global),
            selected_module_nos=tuple(selected_module_nos),
            module_no_label=module_no_label,
            display_mode=display_mode,
            max_threshold_pct=max_threshold_pct,
            min_threshold_pct=min_threshold_pct,
            selected_machines=tuple(selected_machines),
        )
        log_duration(
            logger,
            "table.build_table_dataframe_cached",
            table_started,
            enable_perf_logging,
            extra=f"rows={len(df_all)}",
        )

        ng_list = df_all.iloc[0:0]
        ok_list = df_all.iloc[0:0]

        if not df_all.empty:
            ng_list = df_all[df_all["Result"] == "NG"]
            ok_list = df_all[df_all["Result"] == "OK"]

        st.markdown("<h2 style='text-align: center;'>List of Data</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)

        if display_mode == "Over-threshold only":
            with col1:
                st.write("- Total Data:", len(df_all))
        else:
            with col1:
                st.write("- Total Data:", len(df_all))
            with col2:
                st.write("- Total NG:", len(ng_list))
            with col3:
                st.write("- Total OK:", len(ok_list))

        drop_list = ["Daily", "Threshold"]
        pattern_drop_list = "|".join(drop_list)
        df_to_select = df_all.loc[:, ~df_all.columns.str.contains(pattern_drop_list)].copy()
        if len(df_to_select) <= STYLED_TABLE_MAX_ROWS:
            table_payload = df_to_select.style.map(highlight_ng, subset=["Result"]).format(precision=0)
        else:
            table_payload = df_to_select
        selected_x = st.dataframe(
            table_payload,
            key="selected_data",
            on_select="rerun",
            selection_mode=["single-cell"],
        )
        st.space()

        selected_payload = build_selected_row_payload(selected_event=selected_x, df_all=df_all)
        if selected_payload is None:
            if df_all.empty:
                st.markdown(
                    "<div class='empty-state-message'>No data to show within these parameters</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    "<h2 style='text-align: center;'>Select Data from Table Above to Visualize</h2>",
                    unsafe_allow_html=True,
                )
        else:
            viz_started = perf_counter()
            selected_data, selected_viz, selected_row = selected_payload
            st.markdown(
                "<h2 style='text-align: center;'>Visualization from Above Data Point</h2>",
                unsafe_allow_html=True,
            )

            selected_data_viz = (
                selected_data.loc[:, ~selected_data.columns.str.contains(pattern_drop_list)]
                .style.map(highlight_ng, subset=["Result"])
                .format(precision=0)
            )

            st.write(selected_data_viz)
            fig = build_selected_timeseries_figure(
                selected_data=selected_data,
                selected_viz=selected_viz,
                selected_row=selected_row,
            )
            is_short_series = len(selected_viz) <= SHORT_SERIES_POINT_THRESHOLD
            if is_short_series:
                left_col, center_col, right_col = st.columns([1, 2, 1])
                with center_col:
                    st.plotly_chart(fig, width="content")
            else:
                st.plotly_chart(fig, width="stretch")
            log_duration(logger, "table.build_selected_figure", viz_started, enable_perf_logging)

        log_duration(
            logger,
            "table.render_total",
            total_started,
            enable_perf_logging,
            extra=f"rows={len(df_all)}",
        )
