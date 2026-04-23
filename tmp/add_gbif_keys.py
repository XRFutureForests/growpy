"""Add GBIF Key column to tree_asset_lookup.csv for all 11 dataset species."""
import csv
from pathlib import Path

LOOKUP_CSV = Path("config/tree_asset_lookup.csv")

# GBIF keys for the 11 dataset species (Scientific Name → GBIF Key)
GBIF_KEYS = {
    "Picea abies": 5284884,
    "Abies alba": 2685484,
    "Pinus sylvestris": 5285637,
    "Pseudotsuga menziesii": 2685796,
    "Fagus sylvatica": 2882316,
    "Quercus robur": 2878688,
    "Acer pseudoplatanus": 3189870,
    "Fraxinus excelsior": 3172358,
    "Betula pendula": 5331916,
    "Tilia cordata": 3152047,
    "Prunus avium": 3020791,
}

# Read existing CSV
rows = []
with open(LOOKUP_CSV, "r", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = list(reader.fieldnames) + ["GBIF Key"]
    for row in reader:
        sci = row["Scientific Name"]
        row["GBIF Key"] = str(GBIF_KEYS.get(sci, ""))
        rows.append(row)

# Write back with new column
with open(LOOKUP_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

# Report
filled = sum(1 for r in rows if r["GBIF Key"])
print(f"Updated {LOOKUP_CSV}: {filled}/{len(rows)} species have GBIF Key populated")
print("\nPopulated species:")
for r in rows:
    if r["GBIF Key"]:
        print(f"  {r['Common Name']:25s} → GBIF Key {r['GBIF Key']}")
