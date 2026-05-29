from __future__ import annotations

from pathlib import Path
import sys
import logging

import pandas as pd

# Ensure project root is on path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.cylinder_domain.aggregation import aggregate_daily
from src.cylinder_domain.parsing import parse_dataset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    data_dir = root / "data"
    csv_candidates = sorted(data_dir.glob("*.csv")) if data_dir.exists() else []
    data_file = csv_candidates[0] if csv_candidates else None
    if data_file is None:
        legacy_candidates = sorted(root.glob("Dataset_Cylinder_*.csv"))
        data_file = legacy_candidates[0] if legacy_candidates else None
    if data_file is None or not data_file.exists():
        logger.error("Dataset file not found in %s or repo root", data_dir)
        sys.exit(1)
    df = pd.read_csv(data_file)
    parsed = parse_dataset(df)
    # Take first module/item group and aggregate
    for module, items in parsed.hierarchy.items():
        for item, variants in items.items():
            cols = list(variants.values())
            if cols:
                agg = aggregate_daily(
                    df=df,
                    id_column=parsed.id_column,
                    datetime_column=parsed.datetime_column,
                    selected_columns=cols,
                    method="average",
                )
                print("Aggregated rows:", len(agg.daily))
                print("Baselines:", agg.baselines)
                return
    logger.warning("No measurement columns found to aggregate.")


if __name__ == "__main__":
    main()
