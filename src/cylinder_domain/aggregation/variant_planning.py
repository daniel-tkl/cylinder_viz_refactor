from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from .aggregation import AggregationMethod
from .thresholds import variant_family_label

GroupedVariants = Dict[str, List[tuple[str, str]]]


@dataclass(frozen=True)
class VariantGroupPlan:
    groups: GroupedVariants
    all_variant_columns: List[str]
    method_map: Dict[str, AggregationMethod]
    base_time_col: str | None


@dataclass(frozen=True)
class MotionTimeColumns:
    min_col: str | None
    avg_col: str | None
    max_col: str | None


def infer_method_for_variant(variant_name: str) -> AggregationMethod:
    value = variant_name.strip().lower()
    if "max" in value:
        return "max"
    if "min" in value:
        return "min"
    if "average" in value:
        return "average"
    if "width" in value or "range" in value:
        return "range"
    return "average"


def build_variant_group_plan(
    variants_map: Dict[str, str],
    selected_variants: Iterable[str] | None,
) -> VariantGroupPlan:
    selected_variants_set = set(selected_variants or [])

    groups: GroupedVariants = {}
    for variant_name, col_name in variants_map.items():
        if selected_variants_set and variant_name not in selected_variants_set:
            continue
        family_label = variant_family_label(variant_name)
        groups.setdefault(family_label, []).append((variant_name, col_name))

    all_variant_columns: List[str] = []
    method_map: Dict[str, AggregationMethod] = {}
    for items_in_group in groups.values():
        for variant_name, col_name in items_in_group:
            all_variant_columns.append(col_name)
            method_map[col_name] = infer_method_for_variant(variant_name)

    base_time_col = next(
        (col_name for variant_name, col_name in variants_map.items() if variant_name.strip().lower() == "base time"),
        None,
    )
    if base_time_col is not None and base_time_col not in method_map:
        all_variant_columns.append(base_time_col)
        method_map[base_time_col] = "average"

    return VariantGroupPlan(
        groups=groups,
        all_variant_columns=all_variant_columns,
        method_map=method_map,
        base_time_col=base_time_col,
    )


def resolve_motion_time_columns(variants_map: Dict[str, str]) -> MotionTimeColumns:
    normalized = {variant_name.strip().lower(): col_name for variant_name, col_name in variants_map.items()}
    return MotionTimeColumns(
        min_col=normalized.get("motion time min"),
        avg_col=normalized.get("motion time average"),
        max_col=normalized.get("motion time max"),
    )
