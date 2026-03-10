"""Test the refactored calibrate_growth.py CLI."""
import sys
from pathlib import Path

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path / "the_grove_23" / "modules"))
sys.path.insert(0, str(src_path))

# Reset calibrations first
import json
import glob
for f in glob.glob("data/assets/presets/*.seed.json"):
    d = json.load(open(f))
    if "_yield_table_calibration" in d:
        del d["_yield_table_calibration"]
        with open(f, "w") as fh:
            json.dump(d, fh, indent=4)

# Step 1: Generate clean growth models
print("=" * 60)
print("  Step 1: Generating growth models")
print("=" * 60)
from growpy.cli.create_growth_models import main as gm_main
sys.argv = ["create_growth_models", "--csv", "data/input/test.csv", "--cycles", "50", "--timeout", "600"]
gm_main()

# Step 2: Calibrate against yield tables
print("\n" + "=" * 60)
print("  Step 2: Calibrating against yield tables")
print("=" * 60)
from growpy.cli.calibrate_growth import main as cal_main
sys.argv = ["calibrate_growth", "--no-plot"]
result = cal_main()
print(f"\nCalibration exit code: {result}")

# Check results
print("\n" + "=" * 60)
print("  Results: seed.json calibration data")
print("=" * 60)
for f in sorted(glob.glob("data/assets/presets/*.seed.json")):
    d = json.load(open(f))
    name = Path(f).stem
    cal = d.get("_yield_table_calibration", {})
    if cal:
        gl = cal.get("grow_length_per_cycle", [])
        tt = cal.get("thicken_tips_per_cycle", [])
        so = cal.get("static_overrides", {})
        print(f"{name}: GL[{len(gl)}], TT[{len(tt)}], static={so}")
    else:
        print(f"{name}: no calibration")
