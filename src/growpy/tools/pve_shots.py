"""Render every exported PVE tree from fixed framings, for the visual pass.

The acceptance metric for the catalog is optical (owner direction, 2026-09-15):
a tree is judged by looking at it, beside its siblings. This spawns the
exported skeletal meshes of a run in a row in the open level, then takes one
viewport ``HighResShot`` per (tree, framing) and collects the PNGs under one
directory, plus a contact sheet per species so eleven species x ten variants
can be reviewed on one screen each.

Two facts the loop is built around (sessions 7 and 9): a ``SceneCapture2D``
does not render Nanite-assembly foliage, so the shots go through the level
viewport, which needs the editor in front (``t.IdleWhenNotForeground 0`` is
set so it keeps ticking otherwise); and a Voxelize export streams in over
~10-20 s after the camera moves, so every framing is set, left to settle, and
only then shot -- shooting on the same tick catches voxel blocks.

Usage::

    growpy-pve-shots data/output/forest/unreal_scripts/pve_export_manifest.json
    growpy-pve-shots <manifest> --framings outside crown_edge --settle 15
    growpy-pve-shots <manifest> --species silver_fir --out data/tmp/shots
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

logger = logging.getLogger("growpy.pve_shots")

DEFAULT_FRAMINGS = ("outside", "crown_edge", "low_back")
ROW_SPACING_CM = 3000.0

SPAWN_SCRIPT = """\
import json
import unreal

ROW = {row!r}
OUT = {actors_json!r}
eal = unreal.EditorAssetLibrary
els = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for a in els.get_all_level_actors():
    if a.get_actor_label().startswith("PVESHOT_"):
        els.destroy_actor(a)
actors = {{}}
for j, (key, path) in enumerate(ROW):
    if not eal.does_asset_exist(path):
        unreal.log_warning("PVESHOTS missing %s" % path)
        continue
    mesh = eal.load_asset(path)
    base = unreal.Vector(0.0, j * {spacing!r}, 0.0)
    act = els.spawn_actor_from_object(
        mesh, base, unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)
    )
    act.set_actor_label("PVESHOT_" + key)
    origin, extent = act.get_actor_bounds(False)
    actors[key] = dict(
        x=base.x, y=base.y, oz=origin.z, h=extent.z * 2.0, r=max(extent.x, extent.y)
    )
with open(OUT, "w") as fh:
    json.dump(actors, fh, indent=1)
unreal.SystemLibrary.execute_console_command(None, "t.IdleWhenNotForeground 0")
unreal.log("PVESHOTS spawned %d" % len(actors))
"""

CAMERA_SCRIPT = """\
import unreal

a = {actor!r}
base = unreal.Vector(a["x"], a["y"], 0.0)
h, r, oz = a["h"], a["r"], a["oz"]


def _rot(pitch=0.0, yaw=0.0):
    return unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw)


framings = {{
    "outside": (base + unreal.Vector(-(r + max(400.0, 0.9 * h)), 0.0, oz), _rot()),
    "outside_far": (base + unreal.Vector(-(r + 1.6 * h), 0.0, oz), _rot()),
    "crown_edge": (base + unreal.Vector(-(r + 60.0), 0.0, oz + 0.1 * h), _rot()),
    "low_back": (base + unreal.Vector(120.0, 0.0, min(250.0, oz)), _rot(8.0, 180.0)),
    "inside_up": (
        base + unreal.Vector(150.0, 0.0, max(150.0, oz - 0.3 * h)),
        _rot(35.0, 0.0),
    ),
    "edge_low": (base + unreal.Vector(-(r + 200.0), 0.0, 300.0), _rot()),
}}
loc, rot = framings[{framing!r}]
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
ues.set_level_viewport_camera_info(loc, rot)
if {shoot!r}:
    unreal.AutomationLibrary.take_high_res_screenshot({width!r}, {height!r}, {name!r})
    unreal.log("PVESHOTS issued %s" % {name!r})
else:
    unreal.log("PVESHOTS camera %s" % {name!r})
"""


def _run_in_editor(source: str, timeout: float = 300.0) -> list[str]:
    from growpy.io.unreal import ue_remote

    fd, path = tempfile.mkstemp(prefix="growpy_pve_shots_", suffix=".py")
    # Close the mkstemp handle before the editor opens the file: with it
    # still open the editor answered "Could not load Python file" (2026-09-16).
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(source)
    try:
        result = ue_remote.run_file(path, timeout=timeout)
    finally:
        try:
            Path(path).unlink()
        except OSError:
            pass
    lines = []
    for line in result.get("output", []):
        lines.append(line.get("output", "") if isinstance(line, dict) else str(line))
    if not result.get("success"):
        raise RuntimeError(f"editor script failed: {result.get('result')}")
    return lines


def _screenshot_dir() -> Path:
    from growpy.config.core import get_config

    uproject = None
    try:
        uproject = get_config().unreal_uproject
    except Exception:
        pass
    if not uproject:
        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Process -Filter \"Name='UnrealEditor.exe'\" | "
                "Select-Object -First 1).CommandLine",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        ).stdout
        import re

        match = re.search(r'"?([A-Za-z]:[^"]+?\.uproject)"?', out)
        uproject = match.group(1) if match else None
    if not uproject:
        raise SystemExit(
            "cannot resolve the project: start the editor or set [unreal] uproject"
        )
    return Path(uproject).parent / "Saved" / "Screenshots" / "WindowsEditor"


def _contact_sheets(out_dir: Path, keys: list[str], framing: str) -> list[Path]:
    """One sheet per species: rows = radius, columns = stage."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        logger.warning("Pillow not available; no contact sheets")
        return []
    by_species: dict[str, dict[tuple[str, str], Path]] = {}
    for key in keys:
        # key = <species>__<tree_id>
        species, tree_id = key.split("__", 1)
        radius, stage = tree_id.split("_", 1)
        png = out_dir / f"{key}_{framing}.png"
        if png.is_file():
            by_species.setdefault(species, {})[(radius, stage)] = png
    sheets = []
    for species, cells in sorted(by_species.items()):
        radii = sorted({r for r, _ in cells})
        stages = sorted({s for _, s in cells})
        thumb = (480, 270)
        sheet = Image.new(
            "RGB", (thumb[0] * len(stages), thumb[1] * len(radii) + 24), "white"
        )
        draw = ImageDraw.Draw(sheet)
        draw.text(
            (8, 4),
            f"{species} -- {framing}: rows {radii}, columns {stages}",
            fill="black",
        )
        for i, radius in enumerate(radii):
            for j, stage in enumerate(stages):
                png = cells.get((radius, stage))
                if png is None:
                    continue
                img = Image.open(png).convert("RGB")
                img.thumbnail(thumb)
                sheet.paste(img, (j * thumb[0], 24 + i * thumb[1]))
                draw.text(
                    (j * thumb[0] + 6, 24 + i * thumb[1] + 4),
                    f"{radius} {stage}",
                    fill="yellow",
                )
        path = out_dir / f"sheet_{species}_{framing}.png"
        sheet.save(path)
        sheets.append(path)
    return sheets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--out", type=Path, default=None, help="default: <manifest dir>/shots"
    )
    parser.add_argument("--framings", nargs="+", default=list(DEFAULT_FRAMINGS))
    parser.add_argument("--species", nargs="*", default=None)
    parser.add_argument(
        "--settle", type=float, default=15.0, help="seconds after a camera move"
    )
    parser.add_argument("--size", default="1600x900")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--no-sheets", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s"
    )
    width, height = (int(v) for v in args.size.lower().split("x"))

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    row = []
    for graph in manifest["graphs"]:
        for mesh in graph["meshes"]:
            species = mesh.get("species")
            if args.species and species not in args.species:
                continue
            row.append((f"{species}__{mesh['tree_id']}", mesh["asset"]))
    if not row:
        logger.error("nothing to shoot")
        return 1
    # Absolute: the spawn script writes actors.json from inside the editor,
    # whose working directory is not growpy's.
    out_dir = (args.out or args.manifest.parent / "shots").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    actors_json = out_dir / "actors.json"

    _run_in_editor(
        SPAWN_SCRIPT.format(
            row=row, actors_json=str(actors_json), spacing=ROW_SPACING_CM
        )
    )
    actors = json.loads(actors_json.read_text(encoding="utf-8"))
    logger.info("spawned %d of %d trees", len(actors), len(row))

    shots_dir = _screenshot_dir()
    keys = [k for k, _ in row if k in actors]
    for key in keys:
        for framing in args.framings:
            name = f"{key}_{framing}"
            target = out_dir / f"{name}.png"
            if args.skip_existing and target.is_file():
                continue
            spec = {
                "actor": actors[key],
                "framing": framing,
                "name": name,
                "width": width,
                "height": height,
            }
            _run_in_editor(CAMERA_SCRIPT.format(shoot=False, **spec))
            time.sleep(args.settle)
            _run_in_editor(CAMERA_SCRIPT.format(shoot=True, **spec))
            produced = shots_dir / f"{name}.png"
            deadline = time.time() + 60
            while time.time() < deadline and not produced.is_file():
                time.sleep(1.0)
            if produced.is_file():
                time.sleep(1.0)  # let the writer close it
                shutil.move(str(produced), str(target))
                logger.info("  %s", target.name)
            else:
                logger.warning("  TIMEOUT %s (is the editor in front?)", name)

    if not args.no_sheets:
        for framing in args.framings:
            for sheet in _contact_sheets(out_dir, keys, framing):
                logger.info("sheet: %s", sheet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
