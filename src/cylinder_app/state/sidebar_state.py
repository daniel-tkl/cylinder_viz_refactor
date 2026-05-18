from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ViewMode = Literal["Table", "Chart"]
DisplayMode = Literal["Over-threshold only", "All charts"]


@dataclass(frozen=True)
class ThresholdState:
    max_threshold_pct: float
    min_threshold_pct: float


@dataclass(frozen=True)
class ViewState:
    view_mode: ViewMode
    display_mode: DisplayMode
    machines_per_row: int
    matrix_page: int
    total_pages: int


@dataclass(frozen=True)
class SelectionState:
    selected_models: list[str]
    selected_machines: list[str]
    selected_modules: list[str]
    selected_module_nos: list[str]
    selected_items: list[str]
    selected_variants: list[str]
    variant_highlight: str


@dataclass(frozen=True)
class SidebarState:
    threshold: ThresholdState
    view: ViewState
    selection: SelectionState