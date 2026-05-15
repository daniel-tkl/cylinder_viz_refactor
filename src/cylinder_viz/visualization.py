from __future__ import annotations

from typing import Dict, Iterable, Optional

import plotly.graph_objs as go

from .aggregation import AggregationResult


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
    """Create a combined time series chart for multiple variants with thresholds.

    If `machine_label_column` is provided in `agg.daily`, lines are split per machine.

    Parameters
    - agg: Aggregation results including daily series and baselines.
    - variants: Column names to plot.
    - title: Figure title; not used in hover header.
    - max_threshold_pct: Upper threshold percentage.
    - min_threshold_pct: Lower threshold percentage.
    - machine_label_column: Optional column in `daily` distinguishing machines.
    - label_map: Optional mapping of column name to display label.
    - highlight_variant_column: Variant column to highlight threshold band for.
    - highlight_all: Whether to render threshold bands for all variants.
    - base_time_baseline: Optional baseline to use for time-related variants.
    - header_title: Optional header text (e.g., "{module} / {item}") for hover tooltip.
    - machine_display: Optional machine identifier to show in hover when `machine_label_column` is not present.
    - header_once: When True, include header & machine lines only for the first variant trace (useful for grouped triplets like Motion Time).
    - header_suffix: Optional suffix to append to the header (e.g., family label "Motion Time"). If not provided, the variant label is appended.
    """
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
        """Return a fixed color for known Motion Time variants.

        - Motion Time Max → red (same as max threshold line)
        - Motion Time Average → blue
        - Motion Time Min → green (same as min threshold line)
        Returns None if no specific color applies.
        """
        display_name = (names.get(column_name) if names else column_name) or ""
        key = display_name.strip().lower()
        if key == "motion time max":
            return "#d62728"
        if key == "motion time average":
            return "#1f77b4"
        if key == "motion time min":
            return "#2ca02c"
        return None

    # Add lines with visible data points (markers) per variant (and per machine if applicable)
    for idx_variant, variant in enumerate(variants):
        fixed_color = _variant_trace_color(variant, label_map)
        if machine_label_column and machine_label_column in daily.columns:
            # Multiple machines: create a trace per machine per variant
            for machine in sorted(daily[machine_label_column].unique()):
                sub = daily[daily[machine_label_column] == machine]
                # Build customdata for richer hover: [header_with_variant, machine, variant_label]
                variant_label = (label_map.get(variant) if label_map else variant)
                if header_suffix:
                    header_text = f"{(header_title or title)} / {header_suffix}"
                else:
                    header_text = f"{(header_title or title)} / {variant_label}" if (header_title or title) else str(variant_label)
                customdata = [[header_text, str(machine), str(variant_label)] for _ in range(len(sub))]
                # Build hovertemplate: include header & machine only once if requested
                if header_once and idx_variant > 0:
                    hover_tmpl = (
                        "<b>%{customdata[2]}</b>"  # Variant label
                        "<br><b>Date:</b> %{x}"  # Date line
                        "<br><b>Value:</b> %{y:.2f}"  # Value line
                        "<extra></extra>"
                    )
                else:
                    hover_tmpl = (
                        "<span style='font-size:16px'><b>%{customdata[0]}</b></span>"  # Header
                        "<br><span style='font-size:14px'><b>Machine:</b> %{customdata[1]}</span>"  # Machine line
                        "<br><br><b>%{customdata[2]}</b>"  # Variant label
                        "<br><b>Date:</b> %{x}"  # Date line
                        "<br><b>Value:</b> %{y:.2f}"  # Value line
                        "<extra></extra>"
                    )
                fig.add_trace(
                    go.Scatter(
                        x=sub.index,
                        y=sub[variant],
                        mode="lines+markers",  # Show both lines and dots
                        name=f"{(label_map.get(variant) if label_map else variant)} ({machine})",
                        line=dict(color=(fixed_color or palette[color_idx % len(palette)])),
                        marker=dict(size=6, symbol="circle"),
                        customdata=customdata,
                        hovertemplate=hover_tmpl,
                    )
                )
                color_idx += 1
        else:
            # Single-machine context or no explicit machine column
            variant_label = (label_map.get(variant) if label_map else variant)
            custom_machine = str(machine_display) if machine_display is not None else ""
            if header_suffix:
                header_text = f"{(header_title or title)} / {header_suffix}"
            else:
                header_text = f"{(header_title or title)} / {variant_label}" if (header_title or title) else str(variant_label)
            customdata = [[header_text, custom_machine, str(variant_label)] for _ in range(len(daily))]
            # Build hovertemplate: include header & machine only once if requested
            if header_once and idx_variant > 0:
                hover_tmpl = (
                    "<b>%{customdata[2]}</b>"  # Variant label
                    "<br><b>Date:</b> %{x}"  # Date line
                    "<br><b>Value:</b> %{y:.2f}"  # Value line
                    "<extra></extra>"
                )
            else:
                hover_tmpl = (
                    "<span style='font-size:16px'><b>%{customdata[0]}</b></span>"  # Header
                    "<br><span style='font-size:14px'><b>Machine:</b> %{customdata[1]}</span>"  # Machine line
                    "<br><br><b>%{customdata[2]}</b>"  # Variant label
                    "<br><b>Date:</b> %{x}"  # Date line
                    "<br><b>Value:</b> %{y:.2f}"  # Value line
                    "<extra></extra>"
                )
            fig.add_trace(
                go.Scatter(
                    x=daily.index,
                    y=daily[variant],
                    mode="lines+markers",  # Show both lines and dots
                    name=(label_map.get(variant) if label_map else variant),
                    line=dict(color=(fixed_color or palette[color_idx % len(palette)])),
                    marker=dict(size=6, symbol="circle"),
                    customdata=customdata,
                    hovertemplate=hover_tmpl,
                )
            )
            color_idx += 1

        # Per-variant threshold band: shaded area for selected variant only
        if highlight_all or (highlight_variant_column and variant == highlight_variant_column):
            # Use Base Time baseline for time-related variants if provided
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
                    # Light green band to represent min-max threshold area
                    fillcolor="rgba(44, 160, 44, 0.12)",
                )
                # Optional boundary lines for the band with annotations
                fig.add_hline(
                    y=max_thr,
                    line=dict(color="#d62728", dash="dot"),
                    annotation_text=f"Max {max_thr:.2f}",
                    annotation_position="top right",
                )
                fig.add_hline(
                    y=min_thr,
                    line=dict(color="#2ca02c", dash="dot"),
                    annotation_text=f"Min {min_thr:.2f}",
                    annotation_position="bottom right",
                )

    # Remove legend and set unified hover for clearer grouping
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Value",
        showlegend=False,
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="rgba(0,0,0,0.75)",
            bordercolor="#cccccc",
            font=dict(size=12),
        ),
    )
    # Note: individual trace hovertemplates are set above to include header/machine/variant lines.
    return fig
