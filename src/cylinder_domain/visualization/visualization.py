from __future__ import annotations

from typing import Dict, Iterable, Optional

import plotly.graph_objs as go

from src.cylinder_domain.aggregation import AggregationResult


def plot_variants_combined(
    agg: AggregationResult,
    variants: Iterable[str],
    title: str,
    max_threshold_pct: float,
    min_threshold_pct: float,
    machine_label_column: Optional[str] = None,
    label_map: Optional[Dict[str, str]] = None,
    highlight_variant_column: Optional[str] = None,
    highlight_all: bool = False,
    base_time_baseline: Optional[float] = None,
    header_title: Optional[str] = None,
    machine_display: Optional[str] = None,
    header_once: bool = False,
    header_suffix: Optional[str] = None,
) -> go.Figure:
    daily = agg.daily.copy()

    fig = go.Figure()
    color_idx = 0
    palette = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ]

    def _variant_trace_color(column_name: str, names: Optional[Dict[str, str]]) -> Optional[str]:
        display_name = (names.get(column_name) if names else column_name) or ""
        key = display_name.strip().lower()
        if key == "motion time max":
            return "#d62728"
        if key == "motion time average":
            return "#1f77b4"
        if key == "motion time min":
            return "#2ca02c"
        return None

    for idx_variant, variant in enumerate(variants):
        fixed_color = _variant_trace_color(variant, label_map)
        if machine_label_column and machine_label_column in daily.columns:
            for machine in sorted(daily[machine_label_column].unique()):
                sub = daily[daily[machine_label_column] == machine]
                variant_label = (label_map.get(variant) if label_map else variant)
                if header_suffix:
                    header_text = f"{(header_title or title)} / {header_suffix}"
                else:
                    header_text = f"{(header_title or title)} / {variant_label}" if (header_title or title) else str(variant_label)
                customdata = [[header_text, str(machine), str(variant_label)] for _ in range(len(sub))]
                if header_once and idx_variant > 0:
                    hover_tmpl = (
                        "<b>%{customdata[2]}</b>"
                        "<br><b>Date:</b> %{x}"
                        "<br><b>Value:</b> %{y:.0f}"
                        "<extra></extra>"
                    )
                else:
                    hover_tmpl = (
                        "<span style='font-size:16px'><b>%{customdata[0]}</b></span>"
                        "<br><span style='font-size:14px'><b>Machine:</b> %{customdata[1]}</span>"
                        "<br><br><b>%{customdata[2]}</b>"
                        "<br><b>Date:</b> %{x}"
                        "<br><b>Value:</b> %{y:.0f}"
                        "<extra></extra>"
                    )
                fig.add_trace(
                    go.Scatter(
                        x=sub.index,
                        y=sub[variant],
                        mode="lines+markers",
                        name=f"{(label_map.get(variant) if label_map else variant)} ({machine})",
                        line=dict(color=(fixed_color or palette[color_idx % len(palette)])),
                        marker=dict(size=6, symbol="circle"),
                        customdata=customdata,
                        hovertemplate=hover_tmpl,
                    )
                )
                color_idx += 1
        else:
            variant_label = (label_map.get(variant) if label_map else variant)
            custom_machine = str(machine_display) if machine_display is not None else ""
            if header_suffix:
                header_text = f"{(header_title or title)} / {header_suffix}"
            else:
                header_text = f"{(header_title or title)} / {variant_label}" if (header_title or title) else str(variant_label)
            customdata = [[header_text, custom_machine, str(variant_label)] for _ in range(len(daily))]
            if header_once and idx_variant > 0:
                hover_tmpl = (
                    "<b>%{customdata[2]}</b>"
                    "<br><b>Date:</b> %{x}"
                    "<br><b>Value:</b> %{y:.0f}"
                    "<extra></extra>"
                )
            else:
                hover_tmpl = (
                    "<span style='font-size:16px'><b>%{customdata[0]}</b></span>"
                    "<br><span style='font-size:14px'><b>Machine:</b> %{customdata[1]}</span>"
                    "<br><br><b>%{customdata[2]}</b>"
                    "<br><b>Date:</b> %{x}"
                    "<br><b>Value:</b> %{y:.0f}"
                    "<extra></extra>"
                )
            fig.add_trace(
                go.Scatter(
                    x=daily.index,
                    y=daily[variant],
                    mode="lines+markers",
                    name=(label_map.get(variant) if label_map else variant),
                    line=dict(color=(fixed_color or palette[color_idx % len(palette)])),
                    marker=dict(size=6, symbol="circle"),
                    customdata=customdata,
                    hovertemplate=hover_tmpl,
                )
            )
            color_idx += 1

        if highlight_all or (highlight_variant_column and variant == highlight_variant_column):
            baseline = agg.baselines.get(variant, None)
            if base_time_baseline is not None and label_map is not None:
                name = label_map.get(variant, "")
                if "time" in name.lower():
                    baseline = base_time_baseline
            if baseline is not None:
                max_thr = baseline * (1 + max_threshold_pct / 100.0)
                min_thr = baseline * (1 - min_threshold_pct / 100.0)
                x0 = daily.index.min()
                x1 = daily.index.max()
                fig.add_shape(
                    type="rect",
                    xref="x",
                    yref="y",
                    x0=x0,
                    x1=x1,
                    y0=min_thr,
                    y1=max_thr,
                    line=dict(width=0),
                    fillcolor="rgba(44, 160, 44, 0.12)",
                )
                fig.add_hline(
                    y=max_thr,
                    line=dict(color="#d62728", dash="dot"),
                    annotation_text=f"Max {max_thr:.0f}",
                    annotation_position="top right",
                )
                fig.add_hline(
                    y=min_thr,
                    line=dict(color="#2ca02c", dash="dot"),
                    annotation_text=f"Min {min_thr:.0f}",
                    annotation_position="bottom right",
                )

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Value",
        showlegend=False,
        hovermode="x unified",
        paper_bgcolor="rgba(12, 26, 48, 0.30)",
        plot_bgcolor="rgba(15, 32, 58, 0.24)",
        font=dict(color="#EAF6FF"),
        hoverlabel=dict(
            bgcolor="rgba(7,16,32,0.92)",
            bordercolor="rgba(92,197,205,0.55)",
            font=dict(size=12, color="#EAF6FF"),
        ),
    )
    fig.update_xaxes(
        tickformat="%Y-%m-%d",
        showgrid=False,
        zeroline=False,
        linecolor="rgba(92, 197, 205, 0.35)",
        tickfont=dict(color="#D8ECFF"),
        title_font=dict(color="#D8ECFF"),
    )
    fig.update_yaxes(
        showgrid=False,
        zeroline=False,
        linecolor="rgba(92, 197, 205, 0.35)",
        tickfont=dict(color="#D8ECFF"),
        title_font=dict(color="#D8ECFF"),
    )
    return fig
