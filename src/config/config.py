from dataclasses import dataclass

@dataclass(frozen=True)
class DefaultConfigs:
    """
    Centralized defaults for the app's sidebar controls.
    Update these values to adjust default behavior globally.
    """
    max_threshold_pct: float = 20.0
    min_threshold_pct: float = 20.0
    display_mode: str = "Over-threshold only"
    view_mode: str = "Table"
    select_all_models: bool = True
    select_all_machines: bool = True
    select_all_modules: bool = True
    select_all_items: bool = True
    prefer_motion_time_triplet: bool = True
    enable_perf_logging: bool = True