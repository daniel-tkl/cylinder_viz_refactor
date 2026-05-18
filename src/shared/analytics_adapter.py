from __future__ import annotations

try:
    # Prefer local vendored copy so UI/package tweaks in this repo take effect.
    from lib.streamlit_analytics2 import main as _streamlit_analytics
except Exception:  # noqa: BLE001
    try:
        import streamlit_analytics2 as _streamlit_analytics
    except Exception:  # noqa: BLE001
        _streamlit_analytics = None


def start_usage_tracking(load_from_json: str) -> None:
    """Start streamlit_analytics2 tracking when available."""
    if _streamlit_analytics is None:
        return
    _streamlit_analytics.start_tracking(load_from_json=load_from_json)


def stop_usage_tracking(save_to_json: str) -> None:
    """Stop streamlit_analytics2 tracking when available."""
    if _streamlit_analytics is None:
        return
    _streamlit_analytics.stop_tracking(save_to_json=save_to_json)
