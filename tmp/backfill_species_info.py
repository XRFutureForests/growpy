"""Backfill species_info.json for species that were processed before XRFF-134 step 2."""
import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
LOOKUP = ROOT / "src/growpy/config/templates/tree_asset_lookup.csv"
FOREST_OUT = ROOT / "data/output/forest"

df = pd.read_csv(LOOKUP)

for species_dir in sorted(FOREST_OUT.iterdir()):
    if not species_dir.is_dir():
        continue
    species_clean = species_dir.name
    if species_clean in ("Instances", "unreal_scripts"):
        continue
    info_path = species_dir / "species_info.json"
    if info_path.exists():
        print(f"  skip (exists): {species_clean}")
        continue

    row = df[df["Standardized Name"].str.lower() == species_clean.replace("_", " ").lower()]
    if row.empty:
        row = df[df["Standardized Name"] == species_clean]
    if row.empty:
        print(f"  WARN: no row for {species_clean}")
        continue

    r = row.iloc[0]
    gbif_key = r.get("GBIF Key")
    if gbif_key and not (isinstance(gbif_key, float) and math.isnan(gbif_key)):
        gbif_key = int(gbif_key)
    else:
        gbif_key = None

    info = {
        "common_name": r.get("Common Name", species_clean),
        "standardized_name": species_clean,
        "scientific_name": r.get("Scientific Name", ""),
        "gbif_taxon_key": gbif_key,
    }
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)
    print(f"  wrote: {info_path.relative_to(ROOT)} -> gbif_key={gbif_key}")
