"""Bark material intake (XRFF-679): one folder per material, one command.

Every bark material -- a Grove bark, a Fab/Megascans surface, later a student
scan -- comes in as one folder (owner design 2026-11-12, hub
``04-LOGIC-TIER/tree-catalog-architecture-2026-11``, "Intake folder")::

    data/input/materials/<id>/
      material.toml                 tracked: catalog key, size, licence, origin
      albedo.png  normal.png  roughness.png  [ao.png]  [height.png]
      <id>_pve_nah.png              written by ``build`` (regenerable)

Only ``material.toml`` is tracked. A Fab set's maps are rebuilt from the
launcher cache (``source_ref`` names the Megascans id); a scan has no such
source, so its maps belong on the backup share.

Commands::

    growpy-material-intake fab <megascans set dir> --species douglas_fir
    growpy-material-intake grove fir_70 --species silver_fir
    growpy-material-intake set <dir> --species beech --id scan_x --tile-size-m 1 1
        --licence "CC-BY-4.0" --source-ref <capture id>
    growpy-material-intake build data/input/materials/<id> [--run]

``fab`` and ``grove`` write an intake folder from a source; ``build`` is the
one command of the design: it checks the folder, packs the PVE ``_NAH`` map
(normal R/G, AO B, height A), writes the UE script that imports the maps and
creates ``MI_<id>`` on the plain bark master, and regenerates
``data/input/materials/catalog.toml`` from every intake folder. ``--run`` sends the
script to the running editor. The species' ``bark_source_per_species`` entry
in ``config/pve_calibration.toml`` then points at the instance (``tiled =
true``: a seamless tile, the default).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import tomllib
from pathlib import Path

logger = logging.getLogger(__name__)

INTAKE_ROOT = Path("data/input/materials")
# Beside the intake folders, not in config/: growpy merges every config/*.toml.
CATALOG = INTAKE_ROOT / "catalog.toml"
UE_FOLDER = "/Game/00_XRFF/30_Forest/Materials/Bark"
# The plain master every MegaPlants bark instance sits on; bark_source_per_species
# copies a source's textures and values onto the species' trunk-DBH instance.
SOURCE_MASTER = (
    "/ProceduralVegetationEditor/SampleAssets/Materials/MasterMaterials/"
    "MA_Foliage_Trees"
)
STAGES = ("young", "mature", "old")
# Which branch generations a bark is for (owner 2026-11-13: a trunk tile for
# generation 0 and a smoother branch tile for 1+ instead of a strip atlas).
PARTS = ("trunk", "branch")
SOURCES = ("grove", "megaplants", "fab", "scan")
CONVENTIONS = ("opengl", "directx")
REQUIRED_MAPS = ("albedo", "normal", "roughness")
OPTIONAL_MAPS = ("ao", "height")
MAP_SUFFIXES = (".png", ".tif", ".tiff", ".exr", ".jpg", ".jpeg")
# Megascans map types -> intake names (Displacement is the scan's height).
MEGASCANS_MAPS = {
    "BaseColor": "albedo",
    "Albedo": "albedo",
    "Normal": "normal",
    "Roughness": "roughness",
    "AO": "ao",
    "Displacement": "height",
}
FAB_LICENCE = "Fab Standard License"
GROVE_LICENCE = "The Grove 2.3 bundled bark texture (thegrove3d.com licence)"
# Grove barks have no physical size: growpy wraps them 3x around the trunk
# (bark_wraps_by_generation), whatever its girth.
GROVE_TILE = "grove-wraps"
DEFAULT_SIZE = 2048


# --------------------------------------------------------------------- folder


def find_map(folder: Path, name: str) -> Path | None:
    """``<folder>/<name>.<ext>`` for the first supported extension, or None."""
    for suffix in MAP_SUFFIXES:
        path = folder / f"{name}{suffix}"
        if path.is_file():
            return path
    return None


def read_material(folder: Path) -> dict:
    with (folder / "material.toml").open("rb") as fh:
        return tomllib.load(fh)


def normal_convention_by_curl(normal) -> str:
    """``opengl`` or ``directx``: the green sign whose gradient field has no curl.

    p = dh/dcol = -nx/nz; q = dh/drow = +ny/nz if green points up (OpenGL),
    -ny/nz if down (DirectX). A real height field is integrable, so the right
    sign gives the smaller curl relative to the divergence (2026-11-11 test
    that found the Grove and MegaPlants sources to be OpenGL).
    """
    import numpy as np
    from scipy.ndimage import gaussian_filter

    n = np.asarray(normal.convert("RGB"), dtype=np.float64) / 127.5 - 1.0
    n = gaussian_filter(n, (1.5, 1.5, 0))
    x, y = n[..., 0], n[..., 1]
    z = np.sqrt(np.clip(1.0 - x * x - y * y, 0.04, 1.0))
    p = -x / z
    ratio = {}
    for name, q in (("opengl", y / z), ("directx", -y / z)):
        curl = np.gradient(p, axis=0) - np.gradient(q, axis=1)
        div = np.gradient(p, axis=0) + np.gradient(q, axis=1)
        ratio[name] = float(np.sqrt((curl**2).mean() / ((div**2).mean() + 1e-12)))
    return min(ratio, key=ratio.get)


def check(folder: Path) -> list[str]:
    """Problems that stop ``build``; empty if the folder is complete."""
    from PIL import Image

    if not (folder / "material.toml").is_file():
        return [f"{folder}: no material.toml"]
    try:
        m = read_material(folder)
    except tomllib.TOMLDecodeError as exc:
        return [f"{folder}/material.toml: {exc}"]
    problems = []
    for key in (
        "id",
        "species",
        "bark_stage",
        "dbh_cm",
        "tile_size_m",
        "normal_convention",
        "source",
        "source_ref",
        "licence",
        "redistributable",
    ):
        if key not in m:
            problems.append(f"missing key {key!r}")
    if problems:
        return problems
    if m["id"] != folder.name:
        problems.append(f"id {m['id']!r} is not the folder name {folder.name!r}")
    if not re.fullmatch(r"[a-z0-9_]+", str(m["id"])):
        problems.append(f"id {m['id']!r}: lowercase letters, digits and _ only")
    if m["bark_stage"] not in STAGES:
        problems.append(f"bark_stage {m['bark_stage']!r} not in {STAGES}")
    if m.get("part", "trunk") not in PARTS:
        problems.append(f"part {m['part']!r} not in {PARTS}")
    dbh = m["dbh_cm"]
    if not (isinstance(dbh, list) and len(dbh) == 2 and 0 <= dbh[0] < dbh[1]):
        problems.append(f"dbh_cm {dbh!r} must be [low, high] with 0 <= low < high")
    tile = m["tile_size_m"]
    if tile != GROVE_TILE and not (
        isinstance(tile, list) and len(tile) == 2 and all(v > 0 for v in tile)
    ):
        problems.append(f"tile_size_m {tile!r} must be [width, height] in m")
    if m["normal_convention"] not in CONVENTIONS:
        problems.append(
            f"normal_convention {m['normal_convention']!r} not in {CONVENTIONS}"
        )
    if m["source"] not in SOURCES:
        problems.append(f"source {m['source']!r} not in {SOURCES}")
    if not str(m["licence"]).strip():
        problems.append("licence is empty: it is required")
    if not isinstance(m["redistributable"], bool):
        problems.append("redistributable must be true or false")

    maps = {name: find_map(folder, name) for name in REQUIRED_MAPS + OPTIONAL_MAPS}
    for name in REQUIRED_MAPS:
        # Grove ships no roughness; the trunk master takes roughness from values.
        if maps[name] is None and not (name == "roughness" and m["source"] == "grove"):
            problems.append(f"map {name} missing")
    if maps["albedo"] is None or maps["normal"] is None:
        return problems
    with Image.open(maps["albedo"]) as albedo:
        size = albedo.size
    for name, path in maps.items():
        if path is not None and name != "albedo":
            with Image.open(path) as image:
                if image.size != size:
                    problems.append(f"map {name} is {image.size}, albedo {size}")
    if isinstance(tile, list) and len(tile) == 2 and all(v > 0 for v in tile):
        if abs(size[0] / size[1] - tile[0] / tile[1]) > 0.05 * tile[0] / tile[1]:
            problems.append(f"albedo aspect {size} does not match tile_size_m {tile}")
    with Image.open(maps["normal"]) as normal:
        found = normal_convention_by_curl(normal)
    if found != m["normal_convention"]:
        problems.append(
            f"normal_convention says {m['normal_convention']}, the map reads {found}"
        )
    return problems


# --------------------------------------------------------------------- sources


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    if isinstance(value, dict):
        return (
            "{ " + ", ".join(f"{k} = {_toml_value(v)}" for k, v in value.items()) + " }"
        )
    return json.dumps(str(value), ensure_ascii=False)


def write_material_toml(folder: Path, material: dict, header: str = "") -> Path:
    lines = [f"# {line}" for line in header.splitlines()] + [
        f"{key} = {_toml_value(value)}" for key, value in material.items()
    ]
    path = folder / "material.toml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _resize(image, width: int):
    from PIL import Image

    if image.width <= width:
        return image
    height = round(image.height * width / image.width)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def _megascans_json(set_dir: Path) -> tuple[Path, dict]:
    hits = [
        p
        for p in set_dir.rglob("*.json")
        if "maps" in p.read_text(encoding="utf-8", errors="ignore")[:200000]
    ]
    for path in hits:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "maps" in data and "physicalSize" in data:
            return path, data
    raise FileNotFoundError(f"{set_dir}: no Megascans JSON with maps and physicalSize")


def _physical_size(scan: dict, meta: dict) -> tuple[float, float]:
    """Tile size in m: the scan's ``physicalSize``, else a map's, else ``scanArea``.

    Some sets leave the top-level field null and carry "1x2" per map only.
    """
    candidates = [scan.get("physicalSize")]
    candidates += [
        m.get("physicalSize") for m in scan.get("maps", []) if isinstance(m, dict)
    ]
    candidates.append(meta.get("scanArea"))
    for value in candidates:
        hit = re.fullmatch(
            r"\s*([\d.]+)\s*x\s*([\d.]+)\s*(m)?\s*", str(value or "").lower()
        )
        if hit:
            return float(hit.group(1)), float(hit.group(2))
    raise ValueError(
        "Megascans JSON carries no physical size (physicalSize / scanArea)"
    )


def prepare_fab(
    set_dir: Path,
    species: str,
    *,
    material_id: str | None = None,
    bark_stage: str = "mature",
    dbh_cm=(0, 200),
    size: int = DEFAULT_SIZE,
    normal_convention: str | None = None,
    root: Path = INTAKE_ROOT,
) -> Path:
    """Intake folder from a Megascans surface in the Fab launcher cache.

    Reads the scan's JSON (``physicalSize`` -> ``tile_size_m``, ``id`` ->
    ``source_ref``), takes the highest-resolution JPEG/PNG of each map type
    and scales it to ``size`` px wide. The normal convention is measured
    (curl test) unless given.
    """
    from PIL import Image

    json_path, scan = _megascans_json(set_dir)
    name = scan.get("name") or json_path.stem
    material_id = material_id or re.sub(
        r"[^a-z0-9]+", "_", f"fab_{name}".lower()
    ).strip("_")
    folder = root / material_id
    folder.mkdir(parents=True, exist_ok=True)
    files = [
        p
        for p in json_path.parent.iterdir()
        if p.suffix.lower() in (".jpg", ".jpeg", ".png")
    ]
    written = {}
    for path in sorted(files, key=lambda p: p.stat().st_size, reverse=True):
        kind = path.stem.rsplit("_", 1)[-1]
        target = MEGASCANS_MAPS.get(kind)
        if target is None or target in written:
            continue
        with Image.open(path) as image:
            image.load()
            mode = "L" if target in ("roughness", "ao", "height") else "RGB"
            _resize(image.convert(mode), size).save(folder / f"{target}.png")
        written[target] = path.name
    meta = {
        m.get("key"): m.get("value")
        for m in scan.get("meta", [])
        if isinstance(m, dict)
    }
    w, h = _physical_size(scan, meta)
    if normal_convention is None:
        with Image.open(folder / "normal.png") as normal:
            normal_convention = normal_convention_by_curl(normal)
    material = {
        "id": material_id,
        "species": species,
        "bark_stage": bark_stage,
        "dbh_cm": list(dbh_cm),
        "tile_size_m": [w, h],
        "normal_convention": normal_convention,
        "source": "fab",
        "source_ref": f"megascans:{scan.get('id', '')}",
        "licence": FAB_LICENCE,
        "redistributable": False,
        "capture": {
            "place": "",
            "date": str(scan.get("process_date", "")),
            "note": f"Quixel Megascans '{name}', scan area {meta.get('scanArea', '')}, "
            f"relief {meta.get('height', '')}",
        },
        "maps_from": dict(written),
    }
    write_material_toml(
        folder,
        material,
        header=f"Intake: Fab/Megascans '{name}' (growpy-material-intake fab).\n"
        f"Maps rebuilt from the Fab launcher cache; only this file is tracked.",
    )
    logger.info("%s: %s maps %s", folder, material_id, sorted(written))
    return folder


# Generic texture sets (Substance, photo-to-material tools, our own scans):
# a map is recognised by a token of its file name, split at _ - . and spaces.
SET_TOKENS = {
    "albedo": {"basecolor", "albedo", "diffuse", "diff", "color", "colour", "col"},
    "normal": {"normal", "normals", "nrm", "nor", "normalgl", "normaldx"},
    "roughness": {"roughness", "rough", "rgh"},
    "gloss": {"gloss", "glossiness"},
    "ao": {"ao", "ambientocclusion", "occlusion"},
    "height": {"height", "displacement", "disp", "heightmap"},
}
SET_SUFFIXES = (".png", ".tif", ".tiff", ".jpg", ".jpeg")  # what PIL reads


def classify_map(path: Path) -> str | None:
    """Map kind of a texture file from its name tokens; None if none or ambiguous."""
    tokens = {t for t in re.split(r"[_\-.\s]+", path.stem.lower()) if t}
    found = [kind for kind, names in SET_TOKENS.items() if tokens & names]
    return found[0] if len(found) == 1 else None


def _to_grey(image):
    """8-bit grey from any PIL mode; 16/32-bit maps are min-max rescaled."""
    import numpy as np
    from PIL import Image

    if image.mode in ("I", "I;16", "I;16B", "I;16L", "F"):
        a = np.asarray(image, dtype=np.float64)
        lo, hi = float(a.min()), float(a.max())
        a = (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)
        return Image.fromarray((a * 255).round().astype(np.uint8))
    return image.convert("L")


def prepare_set(
    src_dir: Path,
    species: str,
    *,
    material_id: str,
    tile_size_m: tuple[float, float],
    licence: str,
    source_ref: str,
    source: str = "scan",
    redistributable: bool = False,
    bark_stage: str = "mature",
    dbh_cm=(0, 200),
    size: int = DEFAULT_SIZE,
    normal_convention: str | None = None,
    capture_place: str = "",
    capture_date: str = "",
    root: Path = INTAKE_ROOT,
) -> Path:
    """Intake folder from any folder of texture maps (custom sets, scans).

    Each file is recognised by its name (``classify_map``); a gloss map stands
    in, inverted, for a missing roughness map. Maps are scaled to ``size`` px
    wide. Tile size, licence and source reference cannot be read from plain
    image files, so they are arguments; the normal convention is measured
    unless given.
    """
    from PIL import Image, ImageOps

    if source not in SOURCES:
        raise ValueError(f"source {source!r} not in {SOURCES}")
    found: dict[str, list[Path]] = {}
    for path in sorted(src_dir.iterdir()):
        kind = classify_map(path) if path.suffix.lower() in SET_SUFFIXES else None
        if kind:
            found.setdefault(kind, []).append(path)
    gloss = found.pop("gloss", None)
    if "roughness" not in found and gloss:
        found["roughness"] = gloss
    missing = [m for m in ("albedo", "normal") if m not in found]
    if missing:
        raise FileNotFoundError(f"{src_dir}: no {', '.join(missing)} map recognised")
    folder = root / material_id
    folder.mkdir(parents=True, exist_ok=True)
    written = {}
    for kind, paths in found.items():
        path = max(paths, key=lambda p: p.stat().st_size)  # highest resolution
        with Image.open(path) as image:
            image.load()
            if kind in ("albedo", "normal"):
                out = image.convert("RGB")
            else:
                out = _to_grey(image)
                if classify_map(path) == "gloss":
                    out = ImageOps.invert(out)
            _resize(out, size).save(folder / f"{kind}.png")
        written[kind] = path.name
    if normal_convention is None:
        with Image.open(folder / "normal.png") as normal:
            normal_convention = normal_convention_by_curl(normal)
    write_material_toml(
        folder,
        {
            "id": material_id,
            "species": species,
            "bark_stage": bark_stage,
            "dbh_cm": list(dbh_cm),
            "tile_size_m": [float(v) for v in tile_size_m],
            "normal_convention": normal_convention,
            "source": source,
            "source_ref": source_ref,
            "licence": licence,
            "redistributable": redistributable,
            "capture": {"place": capture_place, "date": capture_date, "note": ""},
            "maps_from": written,
        },
        header=f"Intake: texture set {src_dir.name} (growpy-material-intake set).\n"
        "A scan's maps have no other source: keep a copy on the backup share.",
    )
    logger.info("%s: %s maps %s", folder, material_id, sorted(written))
    return folder


def prepare_grove(
    stem: str,
    species: str,
    *,
    textures: Path = Path("data/assets/textures"),
    material_id: str | None = None,
    bark_stage: str = "mature",
    dbh_cm=(0, 200),
    root: Path = INTAKE_ROOT,
) -> Path:
    """Intake folder from a Grove bark (``<stem>_bark.jpg`` + ``_bark_normal``)."""
    from PIL import Image

    material_id = material_id or f"grove_{stem}"
    folder = root / material_id
    folder.mkdir(parents=True, exist_ok=True)
    for src, target, mode in (
        (f"{stem}_bark", "albedo", "RGB"),
        (f"{stem}_bark_normal", "normal", "RGB"),
    ):
        path = find_map(textures, src)
        if path is None:
            raise FileNotFoundError(f"{textures}/{src}.*")
        with Image.open(path) as image:
            image.convert(mode).save(folder / f"{target}.png")
    with Image.open(folder / "normal.png") as normal:
        convention = normal_convention_by_curl(normal)
    write_material_toml(
        folder,
        {
            "id": material_id,
            "species": species,
            "bark_stage": bark_stage,
            "dbh_cm": list(dbh_cm),
            "tile_size_m": GROVE_TILE,
            "normal_convention": convention,
            "source": "grove",
            "source_ref": f"grove:{stem}_bark",
            "licence": GROVE_LICENCE,
            "redistributable": False,
            "capture": {"place": "", "date": "", "note": "The Grove 2.3 bark library"},
        },
        header=f"Intake: Grove bark {stem} (growpy-material-intake grove).\n"
        "No AO or height: build derives both from the normal.",
    )
    return folder


# --------------------------------------------------------------------- build

NAH_SUFFIX = "_pve_nah.png"


def pack(folder: Path) -> Path:
    """``<id>_pve_nah.png``: normal R/G, AO B, height A (measured if present)."""
    from PIL import Image

    from growpy.tools.pack_pve_textures import pack_bark_normal

    m = read_material(folder)
    opened = {}
    for name in ("normal", "ao", "height"):
        path = find_map(folder, name)
        opened[name] = Image.open(path) if path else None
    try:
        nah = pack_bark_normal(
            opened["normal"], ao_map=opened["ao"], height_map=opened["height"]
        )
    finally:
        for image in opened.values():
            if image is not None:
                image.close()
    target = folder / f"{m['id']}{NAH_SUFFIX}"
    nah.save(target)
    return target


UE_SCRIPT = '''\
"""Generated by growpy-material-intake build: bark maps and source instances."""
import unreal

eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
ENTRIES = {entries!r}
MASTER = {master!r}


def imp(source, folder, name):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", source)
    task.set_editor_property("destination_path", folder)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", False)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    return eal.load_asset(folder + "/" + name)


failures = []
for e in ENTRIES:
    folder = e["folder"]
    albedo = imp(e["albedo"], folder, "T_" + e["id"] + "_C")
    nah = imp(e["nah"], folder, "T_" + e["id"] + "_NAH")
    if albedo is None or nah is None:
        failures.append(e["id"] + ": import failed")
        continue
    albedo.set_editor_property("srgb", True)
    # Masks, not BC5: the trunk function reads AO from B and height from A.
    nah.set_editor_property(
        "compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
    nah.set_editor_property("srgb", False)
    nah.set_editor_property("flip_green_channel", e["flip_green"])
    for tex in (albedo, nah):
        # MA_Foliage_Trees samples virtual textures; a plain one renders magenta.
        tex.set_editor_property("virtual_texture_streaming", True)
        eal.save_loaded_asset(tex)
    path = folder + "/MI_" + e["id"]
    mi = eal.load_asset(path) if eal.does_asset_exist(path) else \\
        unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "MI_" + e["id"], folder, unreal.MaterialInstanceConstant,
            unreal.MaterialInstanceConstantFactoryNew())
    mi.set_editor_property("parent", eal.load_asset(MASTER))
    mel.set_material_instance_texture_parameter_value(mi, "Base Color", albedo)
    mel.set_material_instance_texture_parameter_value(mi, "Normal", nah)
    mel.update_material_instance(mi)
    eal.save_loaded_asset(mi)
    got = mel.get_material_instance_texture_parameter_value(mi, "Normal")
    if got is None or got.get_name() != nah.get_name():
        failures.append(e["id"] + ": Normal not set on " + path)
    print("INTAKE_MI", path)
print("INTAKE_FAILURES", failures)
'''


def ue_entry(folder: Path) -> dict:
    m = read_material(folder)
    mid = m["id"]
    return {
        "id": mid,
        "folder": f"{UE_FOLDER}/{mid}",
        "albedo": str(find_map(folder, "albedo").resolve()),
        "nah": str((folder / f"{mid}{NAH_SUFFIX}").resolve()),
        # UE expects DirectX (green down): OpenGL maps import flipped.
        "flip_green": m["normal_convention"] == "opengl",
    }


def instance_path(material_id: str) -> str:
    return f"{UE_FOLDER}/{material_id}/MI_{material_id}"


def write_catalog(root: Path = INTAKE_ROOT, catalog: Path = CATALOG) -> Path:
    """Regenerate the material catalog from every intake folder under ``root``."""
    lines = [
        "# GENERATED by growpy-material-intake build -- do not edit; edit the",
        f"# intake folder's material.toml under {root.as_posix()}/ and rebuild.",
        "# One entry per bark material (XRFF-679). redistributable = false",
        "# entries stay inside the UE project and are left out of any",
        "# published catalog.",
        "",
    ]
    for folder in sorted(p for p in root.iterdir() if (p / "material.toml").is_file()):
        m = read_material(folder)
        lines.append(f"[materials.{m['id']}]")
        for key in (
            "species",
            "bark_stage",
            "dbh_cm",
            "tile_size_m",
            "normal_convention",
            "source",
            "source_ref",
            "licence",
            "redistributable",
        ):
            lines.append(f"{key} = {_toml_value(m[key])}")
        lines.append(f"part = {_toml_value(m.get('part', 'trunk'))}")
        lines.append(f"instance = {_toml_value(instance_path(m['id']))}")
        lines.append("")
    catalog.parent.mkdir(parents=True, exist_ok=True)
    catalog.write_text("\n".join(lines), encoding="utf-8")
    return catalog


def build(
    folders: list[Path],
    script: Path,
    *,
    root: Path = INTAKE_ROOT,
    catalog: Path = CATALOG,
) -> list[str]:
    """Check, pack, write the UE script and the catalog. Returns the problems."""
    problems = []
    good = []
    for folder in folders:
        found = check(folder)
        problems += [f"{folder.name}: {p}" for p in found]
        if not found:
            logger.info("%s: packed %s", folder.name, pack(folder).name)
            good.append(folder)
    if problems:
        return problems
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        UE_SCRIPT.format(entries=[ue_entry(f) for f in good], master=SOURCE_MASTER),
        encoding="utf-8",
    )
    write_catalog(root, catalog)
    return []


# --------------------------------------------------------------------- CLI


def set_part(folder: Path, part: str) -> None:
    """Record which generations the bark is for (absent means trunk)."""
    if part not in PARTS:
        raise ValueError(f"part {part!r} not in {PARTS}")
    path = folder / "material.toml"
    text = re.sub(r"(?m)^part = .*\n", "", path.read_text(encoding="utf-8"))
    path.write_text(text + f'part = "{part}"\n', encoding="utf-8")


def _finish_prepare(folder: Path, part: str) -> int:
    set_part(folder, part)
    print(folder)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def key_args(p):
        p.add_argument("--species", required=True)
        p.add_argument("--id", dest="material_id")
        p.add_argument("--bark-stage", default="mature", choices=STAGES)
        p.add_argument(
            "--dbh-cm", nargs=2, type=float, default=(0, 200), metavar=("LOW", "HIGH")
        )
        p.add_argument(
            "--part",
            default="trunk",
            choices=PARTS,
            help="trunk (generation 0) or branch (generations 1+) bark",
        )
        p.add_argument("--root", type=Path, default=INTAKE_ROOT)

    fab = sub.add_parser("fab", help="intake folder from a Megascans set (Fab cache)")
    fab.add_argument("set_dir", type=Path)
    fab.add_argument("--size", type=int, default=DEFAULT_SIZE, help="map width in px")
    key_args(fab)
    tset = sub.add_parser("set", help="intake folder from any folder of texture maps")
    tset.add_argument("src_dir", type=Path)
    tset.add_argument(
        "--tile-size-m",
        nargs=2,
        type=float,
        required=True,
        metavar=("WIDTH", "HEIGHT"),
        help="physical size of one tile",
    )
    tset.add_argument("--licence", required=True)
    tset.add_argument("--source-ref", required=True, help="URL or capture id")
    tset.add_argument("--source", default="scan", choices=SOURCES)
    tset.add_argument("--redistributable", action="store_true")
    tset.add_argument(
        "--normal-convention",
        choices=CONVENTIONS,
        help="default: measured from the normal map",
    )
    tset.add_argument("--capture-place", default="")
    tset.add_argument("--capture-date", default="")
    tset.add_argument("--size", type=int, default=DEFAULT_SIZE, help="map width in px")
    key_args(tset)
    grove = sub.add_parser("grove", help="intake folder from a Grove bark")
    grove.add_argument("stem", help="e.g. fir_70 for fir_70_bark.jpg")
    grove.add_argument("--textures", type=Path, default=Path("data/assets/textures"))
    key_args(grove)
    b = sub.add_parser("build", help="check, pack, UE script, catalog")
    b.add_argument("folders", nargs="+", type=Path)
    b.add_argument(
        "--script",
        type=Path,
        default=Path("data/output/unreal_scripts/growpy_material_intake.py"),
    )
    b.add_argument("--root", type=Path, default=INTAKE_ROOT)
    b.add_argument("--catalog", type=Path, default=CATALOG)
    b.add_argument(
        "--run", action="store_true", help="send the script to the running editor"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.command == "fab":
        folder = prepare_fab(
            args.set_dir,
            args.species,
            material_id=args.material_id,
            bark_stage=args.bark_stage,
            dbh_cm=args.dbh_cm,
            size=args.size,
            root=args.root,
        )
        return _finish_prepare(folder, args.part)
    if args.command == "set":
        if not args.material_id:
            parser.error("set needs --id")
        folder = prepare_set(
            args.src_dir,
            args.species,
            material_id=args.material_id,
            tile_size_m=tuple(args.tile_size_m),
            licence=args.licence,
            source_ref=args.source_ref,
            source=args.source,
            redistributable=args.redistributable,
            bark_stage=args.bark_stage,
            dbh_cm=args.dbh_cm,
            size=args.size,
            normal_convention=args.normal_convention,
            capture_place=args.capture_place,
            capture_date=args.capture_date,
            root=args.root,
        )
        return _finish_prepare(folder, args.part)
    if args.command == "grove":
        folder = prepare_grove(
            args.stem,
            args.species,
            textures=args.textures,
            material_id=args.material_id,
            bark_stage=args.bark_stage,
            dbh_cm=args.dbh_cm,
            root=args.root,
        )
        return _finish_prepare(folder, args.part)
    problems = build(args.folders, args.script, root=args.root, catalog=args.catalog)
    for p in problems:
        print("PROBLEM", p)
    if problems:
        return 1
    print(f"script {args.script}\ncatalog {args.catalog}")
    if args.run:
        import subprocess

        return subprocess.call(
            [
                sys.executable,
                "-m",
                "growpy.tools.ue_exec",
                str(args.script),
                "--restart-ram-limit",
                "0",
                "--timeout",
                "1800",
            ]
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
