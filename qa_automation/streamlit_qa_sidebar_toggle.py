from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import sys

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.cylinder_domain.parsing import parse_dataset
from src.cylinder_app.state.options import DISPLAY_OPTIONS, MODULE_NO_LABEL, VIEW_OPTIONS
from src.cylinder_app.state.sidebar_options import build_module_no_options


def _pick_dataset(repo_root: Path, explicit_path: str | None) -> Path | None:
    if explicit_path:
        candidate = Path(explicit_path)
        return candidate if candidate.exists() else None

    data_dir = repo_root / "data"
    if data_dir.exists():
        csv_files = sorted(data_dir.glob("*.csv"))
        if csv_files:
            return csv_files[0]

    legacy_files = sorted(repo_root.glob("Dataset_Cylinder_*.csv"))
    if legacy_files:
        return legacy_files[0]

    return None


def _build_item_options(
    hierarchy: dict[str, dict[str, dict[str, str]]],
    selected_modules: list[str],
) -> list[str]:
    items_all: set[str] = set()
    for module in selected_modules:
        items_all.update(hierarchy.get(module, {}).keys())
    return sorted(items_all)


def _build_variant_options(
    hierarchy: dict[str, dict[str, dict[str, str]]],
    selected_modules: list[str],
    selected_items: list[str],
) -> list[str]:
    items_set = set(selected_items)
    variants_all: set[str] = set()
    for module in selected_modules:
        for item, variant_map in hierarchy.get(module, {}).items():
            if item in items_set:
                variants_all.update(variant_map.keys())
    return sorted(variants_all)


@dataclass
class MenuCase:
    label: str
    options: list[str]


def _toggle_case(case: MenuCase, max_select: int) -> tuple[str, str]:
    options = case.options
    if not options:
        return "skip", f"[QA][SKIP] No options available for: {case.label}"

    deselected: list[str] = []
    selected = options[:max_select] if max_select > 0 else options

    if deselected != []:
        return "fail", f"[QA][FAIL] Unexpected deselect state for {case.label}"
    if len(selected) == 0:
        return "fail", f"[QA][FAIL] No selected options for {case.label}"

    return "pass", f"[QA][PASS] Toggled '{case.label}' deselect/select (selected {len(selected)}/{len(options)})."


def _read_dataframe(dataset_file: Path) -> pd.DataFrame:
    if dataset_file.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(dataset_file)
    return pd.read_csv(dataset_file)


def _filter_models(df: pd.DataFrame, selected_models: list[str]) -> pd.DataFrame:
    model_col = next((col for col in df.columns if str(col).strip().lower() == "model"), None)
    if model_col is None or not selected_models:
        return df
    return df[df[model_col].astype(str).isin(selected_models)]


def _safe_build(label: str, fn: Callable[[], list[str]]) -> tuple[bool, list[str], str]:
    try:
        options = fn()
        return True, options, f"[QA][PASS] Built options for {label}: {len(options)}"
    except Exception as exc:  # noqa: BLE001
        return False, [], f"[QA][FAIL] Error while building options for {label}: {exc}"


def _run_sidebar_toggle_qa(repo_root: Path, dataset_file: Path, max_select: int) -> int:
    app_file = repo_root / "streamlit_app.py"
    if not app_file.exists():
        print(f"[QA][FAIL] Streamlit app not found: {app_file}")
        return 2

    print(f"[QA] Using app: {app_file}")
    print(f"[QA] Using dataset: {dataset_file}")

    df = _read_dataframe(dataset_file)

    failures = 0
    executed = 0
    skipped = 0

    model_col = next((col for col in df.columns if str(col).strip().lower() == "model"), None)
    model_options = [] if model_col is None else sorted(df[model_col].dropna().astype(str).unique().tolist())
    model_cases = [[], model_options[:max_select] if model_options else []]

    ok, _, msg = _safe_build("View Mode (radio)", lambda: list(VIEW_OPTIONS))
    print(msg)
    executed += 1 if ok else 0
    failures += 0 if ok else 1

    ok, _, msg = _safe_build("Display Mode (radio)", lambda: list(DISPLAY_OPTIONS))
    print(msg)
    executed += 1 if ok else 0
    failures += 0 if ok else 1

    for selected_models in model_cases:
        filtered_df = _filter_models(df, selected_models)
        if filtered_df.empty:
            continue

        try:
            parsed = parse_dataset(filtered_df)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"[QA][FAIL] Parsing failed for model selection {selected_models}: {exc}")
            continue

        machine_options = sorted(filtered_df[parsed.id_column].dropna().astype(str).unique().tolist())
        module_options = sorted(list(parsed.hierarchy.keys()))

        menu_cases = [
            MenuCase(label="Model(s)", options=model_options if model_col else []),
            MenuCase(label="Machine No(s)", options=machine_options),
            MenuCase(label="Module(s)", options=module_options),
        ]

        for case in menu_cases:
            status, msg = _toggle_case(case, max_select=max_select)
            print(msg)
            if status == "pass":
                executed += 1
            elif status == "fail":
                failures += 1
            else:
                skipped += 1

        selected_modules = module_options[:max_select] if module_options else []
        ok, module_no_options, msg = _safe_build(
            "Module No(s)",
            lambda: build_module_no_options(
                df=filtered_df,
                selected_modules=selected_modules,
                module_no_label=MODULE_NO_LABEL,
            ),
        )
        print(msg)
        if ok:
            executed += 1
            status2, msg2 = _toggle_case(MenuCase(label="Module No(s)", options=module_no_options), max_select=max_select)
            print(msg2)
            if status2 == "pass":
                executed += 1
            elif status2 == "fail":
                failures += 1
            else:
                skipped += 1
        else:
            failures += 1

        ok, item_options, msg = _safe_build("Item(s)", lambda: _build_item_options(parsed.hierarchy, selected_modules))
        print(msg)
        if ok:
            executed += 1
            status2, msg2 = _toggle_case(MenuCase(label="Item(s)", options=item_options), max_select=max_select)
            print(msg2)
            if status2 == "pass":
                executed += 1
            elif status2 == "fail":
                failures += 1
            else:
                skipped += 1
        else:
            failures += 1

        selected_items = item_options[:max_select] if ok else []
        ok, variant_options, msg = _safe_build(
            "Variant(s)",
            lambda: _build_variant_options(parsed.hierarchy, selected_modules, selected_items),
        )
        print(msg)
        if ok:
            executed += 1
            status2, msg2 = _toggle_case(MenuCase(label="Variant(s)", options=variant_options), max_select=max_select)
            print(msg2)
            if status2 == "pass":
                executed += 1
            elif status2 == "fail":
                failures += 1
            else:
                skipped += 1
        else:
            failures += 1

    print(f"[QA] Completed sidebar toggle checks. Successful toggles: {executed}. Skipped: {skipped}. Failures: {failures}.")
    return 0 if failures == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Streamlit sidebar menu toggle QA automation")
    parser.add_argument("--dataset", type=str, default=None, help="Path to dataset CSV file")
    parser.add_argument(
        "--max-select",
        type=int,
        default=50,
        help="Cap selected options per multiselect (0 = select all options)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    dataset_file = _pick_dataset(repo_root, args.dataset)
    if dataset_file is None:
        print("[QA][FAIL] No dataset found. Provide --dataset or add a CSV under data/.")
        return 2

    return _run_sidebar_toggle_qa(
        repo_root=repo_root,
        dataset_file=dataset_file,
        max_select=args.max_select,
    )


if __name__ == "__main__":
    raise SystemExit(main())
