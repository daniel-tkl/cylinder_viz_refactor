from __future__ import annotations

import logging
from collections import defaultdict
from time import perf_counter

import pandas as pd
import streamlit as st


_SESSION_KEY = "perf_metrics"
_RUN_START_KEY = "perf_run_start_ts"


def start_timer() -> float:
    return perf_counter()


def log_duration(
    logger: logging.Logger,
    label: str,
    start_ts: float,
    enabled: bool,
    *,
    extra: str | None = None,
) -> None:
    if not enabled:
        return
    duration_ms = (perf_counter() - start_ts) * 1000.0
    suffix = f" | {extra}" if extra else ""
    logger.info("PERF %s: %.2f ms%s", label, duration_ms, suffix)
    metrics = st.session_state.get(_SESSION_KEY, [])
    metrics.append({"label": label, "duration_ms": duration_ms, "extra": (extra or "")})
    st.session_state[_SESSION_KEY] = metrics


def reset_perf_metrics(enabled: bool) -> None:
    if not enabled:
        st.session_state.pop(_SESSION_KEY, None)
        st.session_state.pop(_RUN_START_KEY, None)
        return
    st.session_state[_SESSION_KEY] = []
    st.session_state[_RUN_START_KEY] = perf_counter()


def render_perf_panel(enabled: bool) -> None:
    if not enabled:
        return

    run_start_ts = st.session_state.get(_RUN_START_KEY)
    elapsed_ms = (perf_counter() - float(run_start_ts)) * 1000.0 if run_start_ts is not None else None

    metrics = st.session_state.get(_SESSION_KEY, [])
    if not metrics:
        with st.sidebar.expander("Performance Metrics", expanded=False):
            st.caption("No measurements collected in this run.")
            if elapsed_ms is not None:
                st.caption(f"Actual elapsed: {elapsed_ms:,.2f} ms")
        return

    grouped: dict[str, list[float]] = defaultdict(list)
    for item in metrics:
        grouped[str(item["label"])].append(float(item["duration_ms"]))

    rows: list[dict[str, str | int | float]] = []
    for label, values in sorted(grouped.items()):
        count = len(values)
        total = sum(values)
        avg = total / count
        max_v = max(values)
        rows.append(
            {
                "metric": label,
                "count": count,
                "avg_ms": round(avg, 2),
                "max_ms": round(max_v, 2),
                "total_ms": round(total, 2),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        with st.sidebar.expander("Performance Metrics", expanded=False):
            st.caption("No measurements collected in this run.")
        return

    df = df.sort_values(by="total_ms", ascending=False, ignore_index=True)
    total_events = int(df["count"].sum())
    total_runtime_ms = float(df["total_ms"].sum())
    slowest_metric = str(df.loc[0, "metric"])

    display_df = df.rename(
        columns={
            "metric": "Metric",
            "count": "Calls",
            "avg_ms": "Avg (ms)",
            "max_ms": "Max (ms)",
            "total_ms": "Total (ms)",
        }
    )

    for col in ["Avg (ms)", "Max (ms)", "Total (ms)"]:
        display_df[col] = display_df[col].map(lambda value: f"{float(value):,.2f}")

    with st.sidebar.expander("Performance Metrics", expanded=False):
        st.caption("Current rerun summary")
        st.metric("Events", f"{total_events}")
        st.metric("Summed (ms)", f"{total_runtime_ms:,.2f}")
        if elapsed_ms is not None:
            st.metric("Actual (ms)", f"{elapsed_ms:,.2f}")
            if elapsed_ms > 0:
                coverage_pct = (total_runtime_ms / elapsed_ms) * 100.0
                st.caption(f"Summed vs actual: {coverage_pct:,.1f}%")
        st.caption(f"Slowest metric: {slowest_metric}")
        st.table(display_df)