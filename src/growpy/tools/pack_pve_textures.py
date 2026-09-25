#!/usr/bin/env python3
"""Pack twig textures into the two maps Epic's PVE tree material expects.

`MA_Foliage_Trees` -- the master every MegaPlants tree material instances,
shipped by the ProceduralVegetationEditor plugin -- exposes exactly TWO texture
parameters:

    Base Color   colour in RGB, opacity in A
    Normal       normal X/Y in R/G, translucency in B

That is the whole texture contract, and it is why MegaPlants ships `_CA`
(colour+alpha) and `_NT` (normal+translucency) pairs rather than separate maps.
growpy's twig assets carry the same information spread across up to four files
-- diffuse, alpha, normal, translucent -- so nothing new has to be authored,
only combined.

The `_NT` layout is read off the plugin's own graph (2026-09-25):
`MF_TwoSided_Leaves` rebuilds the normal from R/G alone (`MF_ReconstructZ`) and
sends the Normal sample's B channel to `MF_generateTranslucency`, which
multiplies the leaf colour by it into the Two Sided Foliage subsurface colour --
the light that comes through a backlit leaf. The plugin's sample `_NT` maps are
RGB. Until then this packer wrote a full normal to RGB and translucency to A, so
the material read normal Z (~0.95 over the whole leaf) as translucency and the
real translucency maps were never sampled.

Translucency level and contrast follow the plugin's sample leaves, measured
inside the leaf cutout (`TRANSLUCENCY_TARGETS`); only the pattern comes from the
twig. Where it ships a translucency map (beech, ash and linden, measured
2026-09-25) that map is the pattern -- as authored it sits at 0.14-0.21 of full
scale, which would make those three the dimmest leaves in the set. Otherwise the
leaf's own brightness is: inverted for broadleaves, whose sample transmits least
through its pale veins (r = -0.93 against brightness), direct for conifers
(r = +0.51).

Relief: a twig without a real normal map (cherry, fir, birch, pine and maple ship
none; the fir and pine `_foliage_normal` files the conversion leaves are flat)
gets one from its own colour, the way The Grove renders cherry and sycamore
maple -- a Bump node whose height is the colour texture (Strength 1, Distance
0.5 mm, read off the twig .blend files 2026-09-25). Oak's dedicated bump map
(Distance 1.5 mm) is converted in step 1 at strength 40, so the colour bump uses
the same strength per millimetre. The Grove bumps neither fir, birch nor pine;
they get the same colour bump here.

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

# Translucency inside the leaf cutout of the plugin's sample `_NT` maps, 0-255:
# mean, standard deviation, and the sign of its correlation with leaf brightness
# (T_LeafTree_01_Foliage_NT / T_Conifer_Foliage_01_NT, 2026-09-25).
TRANSLUCENCY_TARGETS = {
    "broadleaf": (186.0, 42.0, -1.0),
    "conifer": (155.0, 33.0, 1.0),
}

# Normal-map strength for a relief derived from the leaf colour: oak's bump map
# (Grove Distance 1.5 mm) converts at 40 in step 1; The Grove's colour bumps use
# 0.5 mm (see the module docstring).
COLOUR_BUMP_STRENGTH = 40.0 * 0.5 / 1.5
# A normal map whose X/Y vary less than this (0-255) carries no relief.
FLAT_NORMAL_SPREAD = 1.0


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


def _foliage_maps(twig_dir: Path) -> dict[str, Path]:
    """The `<name>_foliage_diffuse` / `_foliage_normal` pair, when present.

    These are the maps the skeletal twig USD binds, i.e. the ones the foliage
    prototype actually renders with. The sibling `<name>_twig_*` atlas belongs
    to the woody shoot.
    """
    found: dict[str, Path] = {}
    textures = twig_dir / "textures"
    if not textures.is_dir():
        return found
    # Rank: an asset can ship _diffuse_top and _diffuse_bottom for the two
    # sides of a leaf. The USD binds the _top one, so prefer it; plain
    # _diffuse next; _bottom only as a last resort.
    ranked: dict[str, tuple[int, Path]] = {}
    # "fall" in the twig's own name (sycamore_maple_fall_twig) names the set,
    # not an autumn variant of it: matched on the name that follows it, or the
    # maple's top and bottom both counted as autumn and its leaves lost their
    # underside tint (2026-09-25).
    twig = twig_dir.name.lower().removesuffix("_twig").replace("_", "")
    for path in sorted(textures.iterdir()):
        if not path.is_file() or "_pve_" in path.name:
            continue
        stem = path.stem.lower()
        flat = stem.replace("_", "")
        variant = flat[len(twig) :] if flat.startswith(twig) else flat
        if "_foliage_normal" in stem:
            role, rank = "normal", 0
        elif "fall" in variant and ("top" in stem or "_diffuse" in stem):
            # Autumn variant: no texture slot for it, but its average colour
            # drives the master's Season Color parameters.
            role, rank = "fall", 0
        elif "_foliage_diffuse_top" in stem:
            role, rank = "diffuse", 0
        elif "_foliage_diffuse_bottom" in stem:
            # The leaf underside. The master has no second texture slot, but
            # BaseColor Tint Leaf Backside takes its average colour.
            role, rank = "bottom", 0
        elif "_foliage_diffuse" in stem:
            role, rank = "diffuse", 1
        else:
            continue
        current = ranked.get(role)
        if current is None or rank < current[0]:
            ranked[role] = (rank, path)
    return {role: path for role, (_, path) in ranked.items()}


def _mean_colour(path: Path) -> list[float] | None:
    """Average linear-ish RGB of a map's opaque pixels, 0-1.

    Used for the parameters the master exposes but has no texture slot for --
    the leaf underside and the autumn variant. Transparent pixels are excluded
    or the surrounding empty atlas would wash the average out.
    """
    try:
        import numpy as np
        from PIL import Image

        im = Image.open(path)
        rgb = np.asarray(im.convert("RGB"), dtype=float) / 255.0
        if im.mode in ("RGBA", "LA") or "transparency" in im.info:
            a = np.asarray(im.convert("RGBA").getchannel("A"), dtype=float) / 255.0
            mask = a > 0.5
            if mask.sum() < 64:
                return None
            rgb = rgb[mask]
        else:
            rgb = rgb.reshape(-1, 3)
        return [round(float(v), 4) for v in rgb.mean(axis=0)]
    except Exception as exc:  # noqa: BLE001
        logger.warning("mean colour failed for %s: %s", path.name, exc)
        return None


def twig_growth_habit(twig_name: str) -> str:
    """The growth habit, conifer or broadleaf, of the species using a twig asset.

    Read off the Twig and Competition Group columns of tree_asset_lookup.csv;
    every twig there serves one habit. A twig no species names is broadleaf.
    """
    from growpy.config.paths import _get_lookup_table
    from growpy.utils.naming import camel_to_snake

    table = _get_lookup_table()
    habits = set()
    for twig, group in zip(table["Twig"], table["Competition Group"], strict=True):
        if not isinstance(twig, str):
            continue
        std = camel_to_snake(twig.strip())
        if twig_name in (std, f"{std}_twig"):
            conifer = isinstance(group, str) and "conifer" in group.lower()
            habits.add("conifer" if conifer else "broadleaf")
    return "conifer" if habits == {"conifer"} else "broadleaf"


def translucency_channel(diffuse, alpha, habit: str, source=None):
    """The Normal map's B channel: how much light a backlit leaf lets through.

    Inside the leaf cutout (`alpha` > 128) the result has the plugin sample's
    mean and spread for `habit`, patterned by `source` (a translucency map) or,
    without one, by the leaf's brightness in `diffuse` (see the module
    docstring). Outside the cutout it holds the mean, so mip levels do not
    darken the leaf edge. Returns an L image the size of `diffuse`.
    """
    import numpy as np
    from PIL import Image

    mean, spread, sign = TRANSLUCENCY_TARGETS[habit]
    if source is not None:
        source = source.convert("L")
        if source.size != diffuse.size:
            source = source.resize(diffuse.size)
        pattern = np.asarray(source, dtype=np.float32)
    else:
        rgb = np.asarray(diffuse.convert("RGB"), dtype=np.float32)
        brightness = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        pattern = sign * brightness
    inside = np.asarray(alpha.convert("L"), dtype=np.uint8) > 128
    if inside.sum() < 64:
        inside = np.ones_like(inside)
    values = pattern[inside]
    sd = float(values.std())
    if sd > 1e-3:
        z = (pattern - float(values.mean())) / sd
    else:
        z = np.zeros_like(pattern)
    out = np.where(inside, mean + spread * z, mean)
    return Image.fromarray(np.clip(np.rint(out), 0, 255).astype(np.uint8))


def pack_normal_map(normal, translucency):
    """The `_NT` map: normal X/Y in R/G, `translucency` in B, no alpha."""
    from PIL import Image

    if translucency.size != normal.size:
        translucency = translucency.resize(normal.size)
    red, green, _ = normal.convert("RGB").split()
    return Image.merge("RGB", (red, green, translucency.convert("L")))


def is_flat_normal(normal) -> bool:
    """True for a normal map without relief, like the placeholders the twig
    conversion writes where The Grove ships no map."""
    import numpy as np

    xy = np.asarray(normal.convert("RGB"), dtype=np.float32)[..., :2]
    return bool(xy.reshape(-1, 2).std(axis=0).max() < FLAT_NORMAL_SPREAD)


def relief_from_colour(diffuse, alpha, strength: float = COLOUR_BUMP_STRENGTH):
    """A tangent-space normal from the leaf's own colour, as The Grove bumps it.

    Height is the colour's brightness inside the leaf cutout; outside it holds
    the cutout's mean, so the transparent atlas does not raise a cliff along
    every leaf edge.
    """
    import numpy as np
    from PIL import Image

    from growpy.io.usd.texture_utils import height_to_normal

    rgb = np.asarray(diffuse.convert("RGB"), dtype=np.float32) / 255.0
    height = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    inside = np.asarray(alpha.convert("L"), dtype=np.uint8) > 128
    if inside.any():
        height = np.where(inside, height, float(height[inside].mean()))
    return Image.fromarray(height_to_normal(height, strength))


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

    # Prefer the FOLIAGE maps over whatever the generic ranking picked. A twig
    # asset ships two atlases -- <name>_twig_* for the woody shoot and
    # <name>_foliage_* for the leaves -- and _gather_texture_candidates ranks
    # the twig one first, so the packed Base Color carried the bark image and
    # leaves rendered with branch texture on them. The skeletal twig USD, which
    # is what becomes the foliage prototype in UE, binds only the foliage pair:
    #     european_beech_foliage_diffuse.png
    #     european_beech_foliage_normal.png
    # so that is the pair this map has to carry.
    foliage = _foliage_maps(twig_dir)
    diffuse_src = foliage.get("diffuse", candidates["diffuse"])
    if diffuse_src is not candidates["diffuse"]:
        logger.info("%s: packing foliage diffuse %s", name, diffuse_src.name)

    diffuse = _load(diffuse_src).convert("RGB")
    alpha = _alpha_channel(candidates, diffuse.size)
    base = Image.merge("RGBA", (*diffuse.split(), alpha))
    base_path = textures / f"{stem}{BASECOLOR_SUFFIX}"
    if not dry_run:
        base.save(base_path)
    result["basecolor"] = base_path.name

    # Bump maps are already converted to normals upstream, in
    # process_twig_textures during asset preparation, so there is nothing extra
    # to do for the 9 assets that ship bump instead of normal.
    normal_src = foliage.get("normal", candidates.get("normal"))
    normal = _load(normal_src).convert("RGB") if normal_src is not None else None
    if normal is not None and not is_flat_normal(normal):
        result["relief"] = "map"
    else:
        # No normal map, or a flat placeholder. Never leave the slot empty:
        # the PVE material instances are cloned from a MegaPlants reference, so
        # a missing Normal leaves the reference species' map in the slot (a
        # violet fir crown lit by spruce normals).
        normal = relief_from_colour(diffuse, alpha)
        result["relief"] = "colour"
    source = None
    if "translucent" in candidates:
        source = _load(candidates["translucent"])
    habit = twig_growth_habit(name)
    packed = pack_normal_map(
        normal, translucency_channel(diffuse, alpha, habit, source)
    )
    normal_path = textures / f"{stem}{NORMAL_SUFFIX}"
    if not dry_run:
        packed.save(normal_path)
    result["normal"] = normal_path.name
    result["translucency"] = "map" if source is not None else "derived"
    result["habit"] = habit

    # Parameters the master exposes but has no texture slot for. Written as a
    # sidecar so the material pass can wire them without re-opening the images.
    params: dict[str, object] = {}
    if foliage.get("bottom") is not None:
        c = _mean_colour(foliage["bottom"])
        if c:
            params["BaseColor Tint Leaf Backside"] = c
    if foliage.get("fall") is not None:
        c = _mean_colour(foliage["fall"])
        if c:
            params["Season Color 1"] = c
            params["Season Color 2"] = c
    if params and not dry_run:
        import json

        (textures / f"{stem}_pve_params.json").write_text(
            json.dumps(params, indent=2), encoding="utf-8")
    result["params"] = params
    return result


def pack_twig_assets(
    twigs_root: Path, species: str | None = None, dry_run: bool = False
) -> list[dict[str, object]]:
    """Pack every twig asset directory under `twigs_root`.

    The shared entry point for the CLI and for `growpy-convert-twigs`, which
    calls this at the end of the conversion so a dataset run needs no separate
    packing step.
    """
    if not twigs_root.is_dir():
        logger.warning("no such twigs root: %s", twigs_root)
        return []
    dirs = [p for p in sorted(twigs_root.iterdir()) if p.is_dir()]
    if species:
        dirs = [p for p in dirs if species.lower() in p.name.lower()]
    return [pack_asset(twig_dir, dry_run) for twig_dir in dirs]


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
    packed = with_normal = with_translucency = with_relief = 0
    for twig_dir in dirs:
        row = pack_asset(twig_dir, args.dry_run)
        if row["basecolor"]:
            packed += 1
        if row["normal"]:
            with_normal += 1
        if row.get("translucency") == "map":
            with_translucency += 1
        if row.get("relief") == "map":
            with_relief += 1
        logger.info(
            "%-30s %-34s %s",
            row["asset"],
            row["basecolor"] or "-",
            row["normal"] or "(no normal map in the source asset)",
        )
    logger.info(
        "\n%d/%d assets have a Base Color; %d have a Normal, %d of those with "
        "a relief map and %d with a translucency map (the rest derive them "
        "from the leaf colour).%s",
        packed,
        len(dirs),
        with_normal,
        with_relief,
        with_translucency,
        " Nothing written (--dry-run)." if args.dry_run else "",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
