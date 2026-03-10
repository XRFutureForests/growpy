import json
from pathlib import Path

models_dir = Path("d:/Git/growpy/data/assets/growth_models")
presets_dir = Path("d:/Git/growpy/data/assets/presets")

print(f"{'Species':<20} {'Height':>8} {'DBH(cm)':>8} {'thicken_tips':>13} {'thicken_reduce':>15} {'base_scale':>11} {'base_buttress':>14}")
print("-" * 100)

for sp_dir in sorted(models_dir.iterdir()):
    if not sp_dir.is_dir():
        continue
    hc_path = sp_dir / "height_curve.json"
    if not hc_path.exists():
        continue
    with open(hc_path) as f:
        data = json.load(f)
    meta = data.get("metadata", {})
    species = data["species"]
    final_h = meta.get("final_height", data["height_curve"][-1])
    final_dbh = meta.get("final_dbh", 0) * 100  # m -> cm

    # Load preset params
    preset_path = presets_dir / f"{species}.seed.json"
    tt = tr = bs = bb = "?"
    if preset_path.exists():
        with open(preset_path) as f:
            p = json.load(f)
        tt = p.get("thicken_tips", "?")
        tr = p.get("thicken_tips_reduce", "?")
        bs = p.get("thicken_base_scale", "?")
        bb = p.get("thicken_base_buttress", "?")

    print(f"{species:<20} {final_h:>7.1f}m {final_dbh:>7.1f} {tt:>13} {tr:>15} {bs:>11} {bb:>14}")
