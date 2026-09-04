#!/usr/bin/env python3
"""Pack twig textures into the two maps Epic's PVE tree material expects.

`MA_Foliage_Trees` -- the master every MegaPlants tree material instances,
shipped by the ProceduralVegetationEditor plugin -- exposes exactly TWO texture
parameters:

    Base Color   colour in RGB, opacity in A
    Normal       normal in RGB, translucency in A

That is the whole texture contract, and it is why MegaPlants ships `_CA`
(colour+alpha) and `_NT` (normal+translucency) pairs rather than separate maps.
growpy's twig assets carry the same information spread across up to four files
-- diffuse, alpha, normal, translucent -- so nothing new has to be authored,
only combined.

What each species actually has (measured 2026-09-04 over the nine converted twig
assets): all nine have diffuse and alpha, so Base Color packs everywhere. Only
european_beech, european_oak, one_leaved_ash and small_leaved_linden ship a
normal map, and only beech, ash and linden a translucency map, so Normal packs
for four of the nine and carries translucency for three. The rest are left
without a Normal texture rather than given a flat stand-in, so the gap stays
visible instead of looking authored.

Alpha is taken from a dedicated alpha map where one exists, falling back to the
diffuse's own alpha channel. Sizes are reconciled by resampling the secondary
map to the primary's -- growpy's atlases are consistent within an asset, but a
mismatch would otherwise fail silently at the channel merge.

Usage:
    growpy-pack-pve-textures                      # every twig asset
    growpy-pack-pve-textures --twigs-root PATH
    growpy-pack-pve-textures --species silver_fir --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger("growpy.pack_pve_textures")

BASECOLOR_SUFFIX = "_pve_basecolor.png"
NORMAL_SUFFIX = "_pve_normal.png"


def _load(path: Path):
    from PIL import Image

    return Image.open(path)


def _alpha_channel(candidates: dict[str, Path], size):
    """Opacity for the Base Color alpha, as an L-mode image at `size`.

    A dedicated alpha map wins over the diffuse's embedded alpha: growpy's
    converter already treats it that way for geometry trimming, and on these
    assets the dedicated map is the one the artist authored the cutout against.
    """
    from PIL import Image

    alpha_path = candidates.get("alpha")
    if alpha_path is not None:
        alpha = _load(alpha_path).convert("L")
        return alpha.resize(size) if alpha.size != size else alpha

    diffuse = _load(candidates["diffuse"])
    if diffuse.mode in ("RGBA", "LA"):
        alpha = diffuse.getchannel("A")
        return alpha.resize(size) if alpha.size != size else alpha
    return Image.new("L", size, 255)


def pack_asset(twig_dir: Path, dry_run: bool = False) -> dict[str, object]:
    """Write the Base Color and Normal maps for one twig asset directory."""
    # `twig_export` imports bmesh at module scope, and bmesh is not importable
    # until bpy has been. Reusing its discovery is still worth the heavy import:
    # it is the same keyword ranking the converter trims geometry with, and a
    # second copy here would drift from it.
    import bpy  # noqa: F401
    from PIL import Image

    from growpy.io.usd.twig_export import _gather_texture_candidates

    name = twig_dir.name
    candidates = _gather_texture_candidates(twig_dir, name, name, {})
    result: dict[str, object] = {"asset": name, "basecolor": None, "normal": None}

    if "diffuse" not in candidates:
        logger.warning("%s: no diffuse texture, skipped", name)
        return result

    textures = twig_dir / "textures"
    textures.mkdir(parents=True, exist_ok=True)
    stem = candidates["diffuse"].stem
    for token in ("_diffuse_top", "_diffuse_bottom", "_diffuse", "_color", "_albedo"):
        if stem.lower().endswith(token):
            stem = stem[: -len(token)]
            break

    diffuse = _load(candidates["diffuse"]).convert("RGB")
    alpha = _alpha_channel(candidates, diffuse.size)
    base = Image.merge("RGBA", (*diffuse.split(), alpha))
    base_path = textures / f"{stem}{BASECOLOR_SUFFIX}"
    if not dry_run:
        base.save(base_path)
    result["basecolor"] = base_path.name

    if "normal" in candidates:
        normal = _load(candidates["normal"]).convert("RGB")
        if "translucent" in candidates:
            trans = _load(candidates["translucent"]).convert("L")
            if trans.size != normal.size:
                trans = trans.resize(normal.size)
        else:
            # No translucency map: leave the channel black rather than white, so
            # a species without the data reads as opaque instead of maximally
            # translucent if the material samples it anyway.
            trans = Image.new("L", normal.size, 0)
        packed = Image.merge("RGBA", (*normal.split(), trans))
        normal_path = textures / f"{stem}{NORMAL_SUFFIX}"
        if not dry_run:
            packed.save(normal_path)
        result["normal"] = normal_path.name
        result["translucency"] = "translucent" in candidates
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Pack twig textures into the Base Color and Normal maps Epic's "
            "MA_Foliage_Trees master expects."
        )
    )
    parser.add_argument(
        "--twigs-root",
        type=Path,
        default=Path("data/assets/twigs"),
        help="converted twig assets (default: data/assets/twigs)",
    )
    parser.add_argument(
        "--species",
        help="only this twig asset directory (substring match on its name)",
    )
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.twigs_root.is_dir():
        logger.error("no such twigs root: %s", args.twigs_root)
        return 1

    dirs = [p for p in sorted(args.twigs_root.iterdir()) if p.is_dir()]
    if args.species:
        dirs = [p for p in dirs if args.species.lower() in p.name.lower()]
    if not dirs:
        logger.error("no twig asset matched %s", args.species)
        return 1

    logger.info("%-30s %-34s %s", "twig asset", "Base Color", "Normal")
    packed = with_normal = with_translucency = 0
    for twig_dir in dirs:
        row = pack_asset(twig_dir, args.dry_run)
        if row["basecolor"]:
            packed += 1
        if row["normal"]:
            with_normal += 1
        if row.get("translucency"):
            with_translucency += 1
        logger.info(
            "%-30s %-34s %s",
            row["asset"],
            row["basecolor"] or "-",
            row["normal"] or "(no normal map in the source asset)",
        )
    logger.info(
        "\n%d/%d assets have a Base Color; %d have a Normal, %d of those "
        "carrying translucency.%s",
        packed,
        len(dirs),
        with_normal,
        with_translucency,
        " Nothing written (--dry-run)." if args.dry_run else "",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
