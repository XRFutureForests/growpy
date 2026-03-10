import json, sys
from pathlib import Path

presets_dir = Path("d:/Git/growpy/src/the_grove_23/presets")
species = [
    "Fagaceae - European oak", "Oleaceae - Ash", "Betulaceae - Silver birch",
    "Sapindaceae - Maple", "Pinaceae - Scots pine", "Pinaceae - Grand fir",
    "Fagaceae - Beech", "Pinaceae - Fir",
]
keywords = ["thicken", "bark", "mass", "diameter", "radius", "girth", "taper"]

for name in species:
    path = presets_dir / f"{name}.seed.json"
    with open(path) as f:
        d = json.load(f)
    params = {k: v for k, v in d.items() if any(x in k for x in keywords)}
    print(f"=== {name} ===")
    for k, v in sorted(params.items()):
        print(f"  {k}: {v}")
    print()
