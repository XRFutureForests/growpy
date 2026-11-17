"""Twig catalog (XRFF-684): one entry per species x part kind, shaped like the material intake.

    growpy-twig-catalog seed european_beech [norway_spruce ...]   # entries from today's palettes
    growpy-twig-catalog build                                     # check every entry, write catalog.toml
    growpy-twig-catalog check
    growpy-twig-catalog palette european_beech                    # sized compounds -> one PVE palette

An entry is a folder ``data/input/twigs/<id>/`` with a small tracked ``twig.toml``:

* ``species`` (the species that wears it), ``part_kind`` (one of :data:`PART_KINDS`),
* ``size_bin`` (``S``/``M``/``L`` or ``-``) and ``cut_diameter_mm`` = ``[lo, hi]``: the branch
  diameter at the skeleton cut this part fits, so its base matches the branch it sits on
  (owner 2026-11-15). ``[]`` = not sized yet; ``check`` reports it,
* ``source`` (``grove`` twig, ``compound`` part harvested from our own Grove growth, or ``own``)
  and ``source_ref`` (the asset file under ``data/assets/``), ``licence``,
* ``leaf_area_m2`` and ``faces`` of one instance, optional ``placement`` overrides and ``preview``.

``catalog.toml`` is generated from the entries; the manifest (``growpy-tree-catalog``) names a tree's
entries. Bins per species live in :data:`SIZE_BINS_MM` (beech fixed 2026-11-16 after the 20 m cut
sheet; the others are set when their compounds are cut).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path

from growpy.tools.material_intake import _toml_value

ROOT = Path("data/input/twigs")
CATALOG = ROOT / "catalog.toml"
ASSETS = Path("data/assets")
PART_KINDS = ("leader", "lateral", "twig", "compound", "bare", "spray")
REQUIRED = ("id", "species", "part_kind", "size_bin", "cut_diameter_mm", "source",
            "source_ref", "licence")  # fmt: skip
SOURCES = {
    "grove": "The Grove 2.3 twig library (licensed to the lab; not redistributed)",
    "compound": "own: harvested from the lab's Grove growth (growpy harvest_compound_parts)",
    "own": "own",
}
# cut-diameter bins in mm (XRFF-684): beech owner-fixed 2026-11-16 (export cut 0.07 x trunk
# base radius, bounded at 25 mm); a species not listed has no bins yet
_SML = {"S": (0.0, 6.0), "M": (6.0, 12.0), "L": (12.0, 25.0)}
# conifers since XRFF-686 (owner 2026-11-17, conifer twig pass for 1.2)
SIZE_BINS_MM = {
    sp: _SML
    for sp in ("european_beech", "norway_spruce", "silver_fir", "douglas_fir", "scots_pine")
}


def read_entry(folder: Path) -> dict:
    with (folder / "twig.toml").open("rb") as fh:
        return tomllib.load(fh)


def check_entry(entry: dict, assets: Path = ASSETS) -> list[str]:
    """Problems with one entry; an empty list means it is usable."""
    out = [f"no {k}" for k in REQUIRED if k not in entry]
    if out:
        return out
    if entry["part_kind"] not in PART_KINDS:
        out.append(f"part_kind {entry['part_kind']!r} not in {PART_KINDS}")
    if entry["source"] not in SOURCES:
        out.append(f"source {entry['source']!r} not in {tuple(SOURCES)}")
    if not (assets / entry["source_ref"]).is_file():
        out.append(f"source_ref {entry['source_ref']} missing under {assets}")
    cut = entry["cut_diameter_mm"]
    bins = SIZE_BINS_MM.get(entry["species"], {})
    if not cut:
        out.append("not sized (cut_diameter_mm empty)")
    elif len(cut) != 2 or not 0 <= cut[0] < cut[1]:
        out.append(f"cut_diameter_mm {cut} is not [lo, hi]")
    elif entry["size_bin"] in bins:
        lo, hi = bins[entry["size_bin"]]
        if cut[0] < lo or cut[1] > hi:
            out.append(f"cut {cut} mm outside bin {entry['size_bin']} {lo}-{hi} mm")
    return out


def write_entry(entry: dict, root: Path = ROOT, header: str = "") -> Path:
    folder = root / entry["id"]
    folder.mkdir(parents=True, exist_ok=True)
    lines = [f"# {ln}" for ln in header.splitlines()]
    lines += [f"{k} = {_toml_value(v)}" for k, v in entry.items()]
    path = folder / "twig.toml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _leaf_area(path: Path) -> tuple[float | None, int | None]:
    meta = path.with_name(path.name.replace("_static.usda", "_leaf_area.json"))
    if not meta.is_file():
        return None, None
    d = json.loads(meta.read_text(encoding="utf-8"))
    return d.get("leaf_area_m2"), d.get("total_faces")


def seed_entries(species: str, assets: Path = ASSETS) -> list[dict]:
    """Entries for the parts a species wears today: its Grove twig prototypes (palette "twigs")
    and its harvested compound parts (palette "compound"). Twigs are unsized (their base has not
    been measured against a cut); a compound part carries the cut its harvest used as upper bound."""
    from growpy.config.paths import get_twig_files_by_type

    out = []
    for files in get_twig_files_by_type(species).values():
        for f in files:
            if not f.name.endswith("_static.usda"):
                continue
            name = f.name.removesuffix("_static.usda")
            area, faces = _leaf_area(f)
            out.append({
                "id": f"{species}__{name}", "species": species, "part_kind": "twig",
                "size_bin": "-", "cut_diameter_mm": [], "source": "grove",
                "source_ref": f.resolve().relative_to(assets.resolve()).as_posix(),
                "licence": SOURCES["grove"], "leaf_area_m2": area, "faces": faces,
            })  # fmt: skip
    palette = assets / "compound_parts" / f"{species}_pve_palette.json"
    if palette.is_file():
        d = json.loads(palette.read_text(encoding="utf-8"))
        cut_mm = round(1000 * float(d.get("cut_diameter_m", 0.0)), 1)
        for p in d.get("prototypes", []):
            out.append({
                "id": f"{species}__{p['name']}", "species": species, "part_kind": "compound",
                "size_bin": "-", "cut_diameter_mm": [0.0, cut_mm] if cut_mm else [],
                "source": "compound", "source_ref": f"compound_parts/{p['file']}",
                "licence": SOURCES["compound"], "leaf_area_m2": p.get("leaf_area_m2"),
                "faces": p.get("faces"), "span_m": p.get("span_m"),
            })  # fmt: skip
    return [{k: v for k, v in e.items() if v is not None} for e in out]


def build(
    root: Path = ROOT, catalog: Path = CATALOG, assets: Path = ASSETS
) -> tuple[dict, dict]:
    """Write catalog.toml from every entry; returns (entries by id, problems by id)."""
    entries, problems = {}, {}
    for folder in sorted(p for p in root.iterdir() if (p / "twig.toml").is_file()):
        e = read_entry(folder)
        entries[e.get("id", folder.name)] = e
        if issues := check_entry(e, assets):
            problems[e.get("id", folder.name)] = issues
    lines = [
        "# GENERATED by growpy-twig-catalog build -- do not edit; edit the entry's",
        "# twig.toml under data/input/twigs/ and rebuild. One entry per twig part (XRFF-684).",
        "",
    ]
    for tid, e in entries.items():
        lines.append(f"[twigs.{tid}]")
        lines += [f"{k} = {_toml_value(v)}" for k, v in e.items() if k != "id"]
        lines.append("")
    catalog.write_text("\n".join(lines), encoding="utf-8")
    return entries, problems


def entries_for(species: str, palette: str, catalog: Path = CATALOG) -> list[str]:
    """Catalog ids a tree of this species wears with this PVE palette ("twigs" or "compound")."""
    if not catalog.is_file():
        return []
    with catalog.open("rb") as fh:
        twigs = tomllib.load(fh).get("twigs", {})
    source = {"twigs": "grove", "compound": "compound"}.get(palette)
    return sorted(
        t
        for t, e in twigs.items()
        if e.get("species") == species and e.get("source") == source
    )


def merge_palette(species: str, root: Path = ROOT, assets: Path = ASSETS) -> Path:
    """Write ``compound_parts/<species>_pve_palette.json`` from the catalog's sized compounds.

    Every compound entry with a size bin of :data:`SIZE_BINS_MM` is copied in as
    ``<species>_compound_<bin>_pNN`` (static, skeletal and leaf-area files), so one PVE palette
    holds all bins and the plan's ``size_bins_mm`` fill picks one per host branch (XRFF-685).
    The manifest it replaces, if unbinned, is kept beside it as ``*.unbinned.json``.
    """
    import shutil

    bins = SIZE_BINS_MM[species]
    out_dir = assets / "compound_parts"
    picked = []
    for folder in sorted(root.iterdir()):
        if not (folder / "twig.toml").is_file():
            continue
        e = read_entry(folder)
        if e.get("species") == species and e.get("part_kind") == "compound" and e.get("size_bin") in bins:
            picked.append(e)  # fmt: skip
    if not picked:
        raise FileNotFoundError(f"no sized compound entries for {species} under {root}")
    prototypes = []
    for e in sorted(picked, key=lambda e: (list(bins).index(e["size_bin"]), e["source_ref"])):
        src = assets / e["source_ref"]
        tier = src.name.removeprefix(f"{species}_compound_").removesuffix("_static.usda")
        bake = json.loads((src.parent / f"{species}_pve_palette.json").read_text(encoding="utf-8"))
        proto = next(p for p in bake["prototypes"] if Path(p["file"]).name == src.name)
        name = f"{species}_compound_{e['size_bin']}_{tier}"
        for suffix in ("_static.usda", "_skeletal.usda", "_leaf_area_geom.json"):
            part = src.parent / f"{species}_compound_{tier}{suffix}"
            if part.suffix == ".usda" and part.is_file():
                # UE's USD import names the mesh after the prim, so the prims take the binned name too
                text = part.read_text(encoding="utf-8")
                old = f"{species}_compound_{tier}"
                (out_dir / f"{name}{suffix}").write_text(text.replace(old, name), encoding="utf-8")
            elif part.is_file():
                shutil.copy2(part, out_dir / f"{name}{suffix}")
        prototypes.append({
            **proto, "name": name, "file": f"{name}_static.usda",
            "skeletal_file": f"{name}_skeletal.usda", "size_bin": e["size_bin"],
            "cut_diameter_mm": list(bins[e["size_bin"]]), "catalog_id": e["id"],
        })  # fmt: skip
    manifest = out_dir / f"{species}_pve_palette.json"
    if manifest.is_file() and "size_bins_mm" not in json.loads(manifest.read_text(encoding="utf-8")):
        shutil.copy2(manifest, manifest.with_suffix(".unbinned.json"))
    manifest.write_text(json.dumps({
        "schema": 1, "species": species, "size_bins_mm": {k: list(v) for k, v in bins.items()},
        "merged_by": "growpy-twig-catalog palette", "prototypes": prototypes,
    }, indent=1), encoding="utf-8")  # fmt: skip
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("seed", help="entries from the parts a species wears today")
    s.add_argument("species", nargs="+", help="standardized names, e.g. european_beech")
    sub.add_parser("build", help="check every entry and write catalog.toml")
    sub.add_parser("check", help="list entry problems")
    p = sub.add_parser("palette", help="merge a species' sized compounds into its PVE palette")
    p.add_argument("species", help="a species of SIZE_BINS_MM, e.g. european_beech")
    args = parser.parse_args(argv)
    if args.command == "palette":
        print(merge_palette(args.species))
        return 0
    if args.command == "seed":
        for sp in args.species:
            made = 0
            for e in seed_entries(sp):
                if (ROOT / e["id"] / "twig.toml").is_file():
                    continue  # a seeded entry may have been edited since; never overwrite
                write_entry(
                    e, header="Seeded by growpy-twig-catalog seed from today's palette."
                )
                made += 1
            print(f"{sp}: {made} new entries")
        return 0
    entries, problems = (
        build() if args.command == "build" else build(catalog=Path(os.devnull))
    )
    for tid, issues in problems.items():
        print(f"{tid}: {'; '.join(issues)}")
    print(f"{len(entries)} entries, {len(problems)} with problems")
    return 0


if __name__ == "__main__":
    sys.exit(main())
