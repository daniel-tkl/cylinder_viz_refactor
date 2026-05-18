from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go


def build_selected_timeseries_figure(
    selected_data: pd.DataFrame,
    selected_viz: pd.DataFrame,
    selected_row: pd.Series,
) -> go.Figure:
    point_count = len(selected_viz)
    customdata = np.stack(
        (
            selected_data["Motion"],
            selected_data["Equipment"],
            selected_data["Module"],
            selected_data["Motion"],
        ),
        axis=1,
    )
    customdata = [item for item in customdata for _ in range(len(selected_viz))]

    hover_tmpl_max = (
        "<span style='font-size:16px'><b>%{customdata[0]}</b></span>"
        "<br><span style='font-size:14px'><b>Machine:</b> %{customdata[1]}</span>"
        "<br><span style='font-size:12px'><b>Module:</b> %{customdata[2]}</span>"
        "<br><br><b>Motion Time Max</b>"
        "<br><b>Date:</b> %{x}"
        "<br><b>Value:</b> %{y:.0f}"
        "<extra></extra>"
    )
    hover_tmpl_avg = (
        "<br><br><b>Motion Time Avg</b>"
        "<br><b>Date:</b> %{x}"
        "<br><b>Value:</b> %{y:.0f}"
        "<extra></extra>"
    )
    hover_tmpl_min = (
        "<br><br><b>Motion Min</b>"
        "<br><b>Date:</b> %{x}"
        "<br><b>Value:</b> %{y:.0f}"
        "<extra></extra>"
    )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            y=selected_viz["max"],
            x=selected_viz["Date"],
            mode="lines+markers",
            customdata=customdata,
            marker=dict(color="red"),
            hovertemplate=hover_tmpl_max,
        )
    )
    fig.add_trace(
        go.Scatter(
            y=selected_viz["avg"],
            x=selected_viz["Date"],
            mode="lines+markers",
            customdata=customdata,
            marker=dict(color="green"),
            hovertemplate=hover_tmpl_avg,
        )
    )
    fig.add_trace(
        go.Scatter(
            y=selected_viz["min"],
            x=selected_viz["Date"],
            mode="lines+markers",
            customdata=customdata,
            marker=dict(color="cyan"),
            hovertemplate=hover_tmpl_min,
        )
    )

    threshold_max_value = selected_row["Threshold_Max"]
    threshold_min_value = selected_row["Threshold_Min"]
    max_label_value = pd.to_numeric(selected_data["Max"], errors="coerce").iloc[0]
    min_label_value = pd.to_numeric(selected_viz["min"], errors="coerce").min()

    if pd.notna(threshold_max_value):
        fig.add_hline(
            y=threshold_max_value,
            line=dict(color="#d62728", dash="dot"),
            annotation_text=(f"Max {max_label_value:.0f}" if pd.notna(max_label_value) else "Max"),
            annotation_position="top right",
        )
    if pd.notna(threshold_min_value):
        fig.add_hline(
            y=threshold_min_value,
            line=dict(color="#2ca02c", dash="dot"),
            annotation_text=(f"Min {min_label_value:.0f}" if pd.notna(min_label_value) else "Min"),
            annotation_position="bottom right",
        )
    if pd.notna(threshold_max_value) and pd.notna(threshold_min_value):
        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            x0=selected_viz.Date.min(),
            x1=selected_viz.Date.max(),
            y0=min(threshold_max_value, threshold_min_value),
            y1=max(threshold_max_value, threshold_min_value),
            line=dict(width=0),
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
        ),
        title={
            "text": f"{customdata[0][0]}",
            "y": 0.9,
            "x": 0.5,
            "xanchor": "center",
            "yanchor": "top",
            "font": dict(size=24, color="white"),
        },
    )
    if point_count <= 4:
        fig.update_layout(width=max(420, 220 + (point_count * 140)))
    fig.update_xaxes(tickformat="%Y-%m-%d")
    return fig
