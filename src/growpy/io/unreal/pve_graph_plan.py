"""Turn a finished forest export into runnable PVE graph scripts.

This is the join between the four pieces that already exist separately: the
growth JSONs a forest export emits, the densities tracked in
``config/pve_calibration.toml``, the palette and bark paths
:mod:`growpy.io.unreal.pve_asset_script` resolves, and the graph authoring in
:mod:`growpy.io.unreal.pve_graph_builder`. Until XRFF-442 nothing called the
builder at all -- the pipeline still called ``pve_graph_script``, which wires
the Preset Loader node that UE 5.8 deprecated to a no-op, so it could not build
a working graph on the engine we ship on.

WHAT THIS REFUSES TO GUESS
--------------------------

A density is a measurement. Where a tree has none, this reports it and leaves
the tree out, rather than authoring a chain at a plausible-looking number: a
graph built at the wrong density looks entirely normal and exports a tree
carrying the wrong leaf area, which is only visible by measuring it.

The same applies to the tree id. It is read from the export's own directory and
filename tokens -- ``<species>/<r05>/<...>_h15m_<...>_growth_data.json`` -- and
a file those tokens cannot be read from is reported, never matched by position
or by sorting.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from growpy.io.unreal.pve_graph_builder import (
    DEFAULT_SAPLING_WIND_SETTINGS,
    DEFAULT_TREE_WIND_SETTINGS,
    ConditionInfluence,
    ConditionSpec,
    DistributorSpec,
    FoliageLayer,
    FoliageVectorSpec,
    JitterSpec,
    PaletteAttributes,
    PaletteEntry,
    PVEGraphSpec,
    TreeChainSpec,
    generate_pve_graph_builder_script,
    generate_pve_retune_script,
    masked_palette,
    split_by_triangles,
    write_coverage_manifest,
)

if TYPE_CHECKING:
    from growpy.config.pve_calibration import SpeciesCalibration, WindPresets
    from growpy.io.unreal.pve_asset_script import SpeciesAssetSpec

logger = logging.getLogger(__name__)

__all__ = [
    "GrowthJson",
    "PVEGraphPlanResult",
    "discover_growth_jsons",
    "mask_entries_for",
    "plan_pve_graphs",
    "prototype_leaf_areas",
    "tree_id_for",
    "wind_settings_for",
]

_RADIUS = re.compile(r"^r\d+$")
_HEIGHT = re.compile(r"_(h\d+m)_")
_TREE_ID_HEIGHT = re.compile(r"_h(\d+)m$")

# The h05 tier ships the sapling wind preset (no trunk group -- the whole
# plant sways), everything taller the tree preset. Epic's own split is per
# graph, not per height: its sapling graphs top out at 5.7 m and its beech
# C/D (5.7 / 7.9 m) also take the sapling preset, while its 5 m aspen D takes
# the tree one. A height cut is the nearest rule a per-tree pipeline can
# apply; XRFF-235 can move it per species through the calibration.
SAPLING_MAX_HEIGHT_M = 5

GROWTH_JSON_SUFFIX = "_growth_data.json"


@dataclass(frozen=True)
class GrowthJson:
    """One emitted skeleton, and the calibration tree it corresponds to."""

    path: Path
    species: str
    tree_id: str


@dataclass(frozen=True)
class PVEGraphPlanResult:
    """What was planned, and everything that was deliberately left out.

    ``asset_script`` imports the twig palette and builds the bark material;
    ``script`` authors the graphs that name both by path. They must be run in
    that order, and the graph script's own preflight refuses to build anything
    if they were not.
    """

    graphs: tuple[PVEGraphSpec, ...] = ()
    asset_script: Path | None = None
    script: Path | None = None
    manifest: Path | None = None
    retune_script: Path | None = None
    skipped: tuple[str, ...] = field(default=())

    @property
    def chain_count(self) -> int:
        return sum(len(g.chains) for g in self.graphs)


def tree_id_for(path: Path) -> str | None:
    """Calibration tree id for one growth JSON, or None if it cannot be read.

    The pipeline writes a dataset tree to
    ``<species>/<radius_label>/<Prefix>_<h##m>_<d##cm>_<density>_growth_data.json``
    and the calibration keys trees ``<radius_label>_<h##m>`` -- the same two
    tokens. The radius comes from the parent directory rather than the filename
    because the directory is that one token exactly, while the filename embeds
    it among several.

    Returns None rather than a best guess: a tree matched to the wrong
    calibration row builds at the wrong density and looks entirely normal.
    """
    radius = path.parent.name
    if not _RADIUS.match(radius):
        return None
    height = _HEIGHT.search(path.name)
    if not height:
        return None
    return f"{radius}_{height.group(1)}"


def discover_growth_jsons(forest_root: Path) -> dict[str, list[GrowthJson]]:
    """Find every growth JSON under a forest export, keyed by species.

    Species is the top-level directory name the pipeline exports into, which is
    the standardized name the calibration and the asset resolver both use.
    """
    found: dict[str, list[GrowthJson]] = {}
    if not forest_root.is_dir():
        return found

    for path in sorted(forest_root.rglob(f"*{GROWTH_JSON_SUFFIX}")):
        try:
            species = path.relative_to(forest_root).parts[0]
        except (ValueError, IndexError):
            continue
        tree_id = tree_id_for(path)
        if tree_id is None:
            logger.debug("no tree id readable from %s", path)
            continue
        found.setdefault(species, []).append(
            GrowthJson(path=path, species=species, tree_id=tree_id)
        )
    return found


def wind_settings_for(tree_id: str, presets: WindPresets | None = None) -> str:
    """The ``PVWindSettings`` asset a tree's Export node carries.

    Reads the height tier off the tree id (``r08_h05m`` -> 5 m). A species
    override in ``presets`` replaces the plugin preset of its tier; the tier
    rule itself is not overridable, because wind is a per-tree annotation and
    a 15 m tree on the sapling preset would sway from the root.

    Raises:
        ValueError: If the tree id carries no readable height token.
    """
    match = _TREE_ID_HEIGHT.search(tree_id)
    if not match:
        raise ValueError(f"tree id {tree_id!r} carries no height token to tier by")
    sapling = int(match.group(1)) <= SAPLING_MAX_HEIGHT_M
    override = None
    if presets is not None:
        override = presets.sapling if sapling else presets.tree
    if override:
        return override
    return DEFAULT_SAPLING_WIND_SETTINGS if sapling else DEFAULT_TREE_WIND_SETTINGS


# Real entries may be repeated up to this many times to reach a mask
# fraction the palette size alone cannot express (f = m / (r * k + m)).
MAX_PALETTE_REPEATS = 4
_MASK_TOLERANCE = 1e-6


def mask_entries_for(mask_fraction: float, palette_size: int) -> tuple[int, int]:
    """``(repeats, masks)`` that realise ``mask_fraction`` over ``palette_size``.

    The picker is uniform over entries, so the fraction is a ratio of whole
    entries and only some values exist. Returns the smallest ``repeats`` that
    hits the fraction exactly; raises otherwise, naming the nearest values a
    caller could ask for instead, because a fraction the palette cannot spell
    would silently build at the wrong count.
    """
    if not 0.0 <= mask_fraction < 1.0:
        raise ValueError(f"mask_fraction must be in [0, 1), got {mask_fraction}")
    if palette_size < 1:
        raise ValueError(f"palette_size must be >= 1, got {palette_size}")
    if mask_fraction == 0.0:
        return 1, 0
    candidates: list[tuple[float, int, int]] = []
    for repeats in range(1, MAX_PALETTE_REPEATS + 1):
        real = repeats * palette_size
        # f = m / (real + m)  ->  m = f * real / (1 - f)
        masks_exact = mask_fraction * real / (1.0 - mask_fraction)
        masks = round(masks_exact)
        if masks >= 1 and abs(masks - masks_exact) < _MASK_TOLERANCE * real:
            return repeats, masks
        for m in (max(1, int(masks_exact)), int(masks_exact) + 1):
            candidates.append((m / (real + m), repeats, m))
    nearest = sorted(candidates, key=lambda c: abs(c[0] - mask_fraction))[:3]
    spelled = ", ".join(f"{f:.4f} (repeats {r}, masks {m})" for f, r, m in nearest)
    raise ValueError(
        f"mask_fraction {mask_fraction} is not a ratio of whole palette entries "
        f"over {palette_size} meshes with up to {MAX_PALETTE_REPEATS} repeats; "
        f"nearest: {spelled}"
    )


def prototype_leaf_areas(assets: SpeciesAssetSpec) -> tuple[float, ...]:
    """Leaf area (m2) of every palette prototype, in ``palette_meshes`` order.

    Read from the ``<name>_leaf_area_geom.json`` sidecar beside each
    ``_static.usda`` -- the wood-corrected one, which is what the species'
    ``prototype_leaf_area_m2`` averages; the plain ``_leaf_area.json`` counts
    the woody shoot as leaf (XRFF-274). Raises rather than guessing: a ladder
    graded on the wrong areas lands the tree on the wrong leaf area while
    every count looks right.
    """
    areas = []
    for proto in assets.prototypes:
        sidecar = Path(proto.source).parent / f"{proto.name}_leaf_area_geom.json"
        if not sidecar.is_file():
            raise FileNotFoundError(
                f"{assets.species}: no leaf-area sidecar for prototype "
                f"{proto.name!r} at {sidecar}"
            )
        areas.append(float(json.loads(sidecar.read_text())["leaf_area_m2"]))
    return tuple(areas)


def graded_palette(
    meshes: Sequence[str],
    areas: Sequence[float],
    scale_targets: Sequence[float],
) -> tuple[PaletteEntry, ...]:
    """Each prototype with its Scale target, targets assigned by area rank.

    ``scale_targets`` are in ascending prototype-leaf-area order (the way the
    solver writes them); the k-th smallest prototype gets the k-th target.
    """
    if len(meshes) != len(areas):
        raise ValueError("meshes and areas must pair up")
    if len(scale_targets) != len(meshes):
        raise ValueError(
            f"scale_targets has {len(scale_targets)} entries for a palette of "
            f"{len(meshes)} prototypes"
        )
    by_area = sorted(range(len(meshes)), key=lambda i: areas[i])
    target_of = {i: scale_targets[rank] for rank, i in enumerate(by_area)}
    return tuple(
        PaletteEntry(mesh=m, attributes=PaletteAttributes(scale=target_of[i]))
        for i, m in enumerate(meshes)
    )


def _pose_distributor(
    calibration: SpeciesCalibration,
    density: int,
    *,
    conditions: ConditionSpec | None = None,
    generation_band: tuple[int | None, int | None] | None = None,
) -> DistributorSpec:
    """The species' measured twig pose at ``density`` (XRFF-438, 2026-09-14).

    Restated here so a change to the builder's defaults cannot silently change
    what a pipeline run emits. None of it changes instance counts -- but
    ``randomize_scale`` does change leaf AREA (as scale squared), which is why
    the offline solve reads it off this same spec (XRFF-467).
    """
    return DistributorSpec(
        branch_density=density,
        relative_start=calibration.relative_start,
        phyllotaxy_formation=calibration.phyllotaxy_formation,
        reset_phyllotaxy=calibration.pose.reset_phyllotaxy,
        axil_angle=calibration.pose.axil_angle,
        axil_angle_ramp=(1.0, 1.0),  # constant; the engine default ramps it 0->1
        single_bud_tip=True,
        scale_ramp=(1.0, 1.0),
        randomize_scale=calibration.pose.randomize_scale,
        randomize_axil_angle=calibration.pose.randomize_axil_angle,
        spacing_ramp=calibration.pose.spacing_ramp,
        phyllotaxy_type=calibration.pose.phyllotaxy_type,
        node_buds=calibration.pose.node_buds,
        phyllotaxy_additional_angle=calibration.pose.phyllotaxy_additional_angle,
        # Tip Up = Apical first, then the aim entry flattens it -- except a
        # leader, which the WorldUpDot blend leaves pointing up.
        auto_align_end=True,
        aim=FoliageVectorSpec(
            kind="aim",
            vector1="AXIS_FLATTEN",
            vector2="AXIS_AIM",
            dual=True,
            affect_tip=True,
            blend_attribute="WORLD_UP_DOT",
            ramp=((0.0, 0.0), (0.9, 0.0), (1.0, 1.0)),
        ),
        face=FoliageVectorSpec(kind="face", vector2="AXIS_AIM", affect_tip=True),
        jitter=tuple(
            JitterSpec(mode=j.mode, degrees=j.degrees, seed=j.seed)
            for j in calibration.pose.jitter
        ),
        conditions=conditions,
        generation_band=generation_band,
    )


def _chain_for(
    entry: GrowthJson,
    calibration: SpeciesCalibration,
    mesh_prefix: str,
    palette_meshes: Sequence[str] = (),
    palette_areas: Sequence[float] | None = None,
) -> TreeChainSpec:
    """A chain from a MEASURED calibration row (the tree must have one)."""
    resolved = calibration.resolve_density(entry.tree_id)
    tree = calibration.tree(entry.tree_id)
    ladder = calibration.ladder
    palette = None
    conditions = None
    generation_band = None
    layers: tuple[FoliageLayer, ...] = ()
    if tree.mask_fraction > 0.0:
        # Thinning below the one-per-branch floor (XRFF-462): the chain gets
        # a palette of its own with masks beside the shared meshes.
        repeats, masks = mask_entries_for(tree.mask_fraction, len(palette_meshes))
        palette = masked_palette(palette_meshes, masks, repeats=repeats)
    if ladder is not None and tree.scale_targets is not None:
        # Scale-graded ladder (XRFF-412): each prototype advertises a Scale
        # target and the Scale condition picks the tiers nearest a point's
        # normalised radius; the main layer starts above the trunk and one
        # apex part goes on the leader. A tree without scale_targets stays
        # flat -- the legacy radii were solved that way and still build.
        if tree.mask_fraction > 0.0:
            raise ValueError(
                f"{entry.tree_id}: a masked and a graded palette cannot be "
                f"combined -- the mask would need the same Scale target"
            )
        if palette_areas is None:
            raise ValueError(
                f"{entry.tree_id}: the ladder needs the prototype leaf areas"
            )
        palette = graded_palette(palette_meshes, palette_areas, tree.scale_targets)
        conditions = ConditionSpec(
            scale=ConditionInfluence(weight=ladder.scale_weight),
            minimum_candidates=ladder.minimum_candidates,
            cutoff_threshold=ladder.cutoff_threshold,
        )
        if ladder.apex:
            generation_band = (ladder.main_generation_start, None)

    distributor = _pose_distributor(
        calibration,
        resolved.density,
        conditions=conditions,
        generation_band=generation_band,
    )
    if ladder is not None and ladder.apex and tree.scale_targets is not None:
        layers = (_apex_layer(distributor, palette_meshes, palette_areas),)
    return TreeChainSpec(
        growth_json=entry.path,
        mesh_name=f"{mesh_prefix}_{entry.tree_id}",
        wind_settings=wind_settings_for(entry.tree_id, calibration.wind),
        palette=palette,
        distributor=distributor,
        layers=layers,
    )


def _apex_layer(
    distributor: DistributorSpec,
    palette_meshes: Sequence[str],
    palette_areas: Sequence[float],
) -> FoliageLayer:
    """One largest-tier part at the leader tip.

    Density 1 places a single sample at the end of the only generation-1
    branch.
    """
    largest = max(range(len(palette_meshes)), key=lambda i: palette_areas[i])
    return FoliageLayer(
        distributor=dataclasses.replace(
            distributor,
            branch_density=1,
            generation_band=(1, 1),
            conditions=None,
        ),
        palette=(PaletteEntry(mesh=palette_meshes[largest]),),
    )


@dataclass(frozen=True)
class PlannedTree:
    """One chain plus what it was built from, for the manifest."""

    chain: TreeChainSpec
    instances: int
    detail: dict


def _offline_chain(
    entry: GrowthJson,
    calibration: SpeciesCalibration,
    mesh_prefix: str,
    assets: SpeciesAssetSpec,
    palette_areas: Sequence[float],
    profile_mean: float,
    max_instances: int | None = None,
) -> PlannedTree:
    """A chain for a tree with no measured row, from the offline model."""
    from growpy.io.unreal.pve_offline_solve import (
        compound_layout,
        forrester_target,
        solve_flat,
        solve_graded,
        tree_stats,
    )

    stats = tree_stats(entry.path, profile_mean)
    forrester_m2, model_id, extrapolated = forrester_target(entry.species, stats.dbh_cm)
    target_m2 = forrester_m2 * calibration.fullness
    meshes = assets.palette_meshes
    names = [p.name for p in assets.prototypes]
    base = _pose_distributor(calibration, 1)
    detail = {
        "species": entry.species,
        "tree_id": entry.tree_id,
        "density_source": "offline",
        "palette": calibration.palette,
        "dbh_cm": round(stats.dbh_cm, 2),
        "height_m": round(stats.height_m, 2),
        "branches": stats.branches,
        "points": stats.points,
        "forrester_m2": round(forrester_m2, 2),
        "forrester_model": model_id,
        "forrester_extrapolated": extrapolated,
        "fullness": calibration.fullness,
        "target_m2": round(target_m2, 2),
    }

    if calibration.palette == "compound":
        layout = compound_layout(
            entry.path,
            base,
            names,
            meshes,
            palette_areas,
            calibration.compound,
            stats.longest_branch_m,
        )
        chain = TreeChainSpec(
            growth_json=entry.path,
            mesh_name=f"{mesh_prefix}_{entry.tree_id}",
            wind_settings=wind_settings_for(entry.tree_id, calibration.wind),
            palette=layout.palette,
            distributor=layout.distributor,
            layers=layout.layers,
        )
        detail.update(
            layout="compound",
            fill_density=layout.distributor.branch_density,
            fill_instances=layout.fill_instances,
            cap_instances=layout.cap_instances,
            apex_instances=layout.apex_instances,
            predicted_instances=layout.instances,
            predicted_m2=round(layout.area_m2, 2),
        )
        return PlannedTree(chain=chain, instances=layout.instances, detail=detail)

    ladder = calibration.ladder
    if ladder is not None:
        solved = solve_graded(
            entry.path,
            base,
            meshes,
            palette_areas,
            ladder,
            target_m2,
            max_instances=max_instances,
        )
        conditions = ConditionSpec(
            scale=ConditionInfluence(weight=ladder.scale_weight),
            minimum_candidates=ladder.minimum_candidates,
            cutoff_threshold=ladder.cutoff_threshold,
        )
        distributor = _pose_distributor(
            calibration,
            solved.density,
            conditions=conditions,
            generation_band=(
                (ladder.main_generation_start, None) if ladder.apex else None
            ),
        )
        palette = graded_palette(meshes, palette_areas, solved.scale_targets)
        layers = ()
        if ladder.apex:
            layers = (_apex_layer(distributor, meshes, palette_areas),)
        detail["layout"] = "graded"
        detail["scale_targets"] = [round(t, 6) for t in solved.scale_targets]
    else:
        mean_area = sum(palette_areas) / len(palette_areas)
        solved = solve_flat(
            entry.path, base, mean_area, target_m2, max_instances=max_instances
        )
        distributor = _pose_distributor(calibration, solved.density)
        palette = None
        layers = ()
        detail["layout"] = "flat"
    detail.update(
        density=solved.density,
        predicted_instances=solved.instances,
        predicted_m2=round(solved.area_m2, 2),
        predicted_error=round(solved.error, 4),
        capped=solved.capped,
        max_instances=max_instances,
        # The cheap metric for XRFF-466: 177 instances strung along one of
        # ash's 196 branches is a caterpillar whatever the pose says.
        instances_per_branch=(
            round(solved.instances / stats.branches, 1) if stats.branches else None
        ),
    )
    chain = TreeChainSpec(
        growth_json=entry.path,
        mesh_name=f"{mesh_prefix}_{entry.tree_id}",
        wind_settings=wind_settings_for(entry.tree_id, calibration.wind),
        palette=palette,
        distributor=distributor,
        layers=layers,
    )
    return PlannedTree(chain=chain, instances=solved.instances, detail=detail)


def _measured_tree(
    entry: GrowthJson,
    calibration: SpeciesCalibration,
    mesh_prefix: str,
    assets: SpeciesAssetSpec,
    palette_areas: Sequence[float],
) -> PlannedTree:
    chain = _chain_for(
        entry, calibration, mesh_prefix, assets.palette_meshes, palette_areas
    )
    resolved = calibration.resolve_density(entry.tree_id)
    if resolved.instances is None:
        raise ValueError(
            f"density {resolved.density} has no recorded instance count, so "
            f"its click cannot be sized"
        )
    tree = calibration.tree(entry.tree_id)
    detail = {
        "species": entry.species,
        "tree_id": entry.tree_id,
        "density_source": resolved.source,
        "palette": calibration.palette,
        "layout": "graded" if tree.scale_targets is not None else "flat",
        "dbh_cm": tree.dbh_cm,
        "target_m2": tree.target_m2,
        "density": resolved.density,
        "predicted_instances": resolved.instances,
        "predicted_m2": calibration.leaf_area_m2(entry.tree_id),
        "branches": tree.branches,
        "instances_per_branch": (
            round(resolved.instances / tree.branches, 1) if tree.branches else None
        ),
    }
    return PlannedTree(chain=chain, instances=resolved.instances, detail=detail)


def plan_pve_graphs(
    output_dir: Path,
    forest_root: Path,
    *,
    content_root: str = "/Game/PVE",
    graph_folder: str = "/Game/PVE/Graphs",
    triangle_cap: float = 120e6,
    nanite_shape_preservation: str = "PRESERVE_AREA",
    collision_generation: str = "ALL_GENERATIONS",
    import_all_palettes: bool = True,
    calibration_path: Path | None = None,
    species: Sequence[str] | None = None,
    max_assembly_instances: int = 60_000,
    tree_triangle_cap: float = 400e6,
) -> PVEGraphPlanResult:
    """Author graph scripts for every species in a finished forest export.

    A tree with a measured calibration row builds at that density; every
    other tree is solved offline against Forrester x the species' ``fullness``
    (see :mod:`~growpy.io.unreal.pve_offline_solve`), and a species with no
    calibration block at all is built from ``[pve_calibration.defaults]``. The
    manifest records which was which, per tree.

    Args:
        output_dir: Where to write the scripts and the manifest.
        forest_root: The export root the growth JSONs live under.
        content_root: UE package path the palette and bark live under, matching
            what ``growpy-pve-assets`` imported.
        graph_folder: Where the graph assets are created.
        triangle_cap: Predicted-triangle ceiling per graph, i.e. per Export
            click. One click is one failure unit -- see
            :func:`~growpy.io.unreal.pve_graph_builder.split_by_triangles`.
        nanite_shape_preservation: ``PRESERVE_AREA`` by default. ``VOXELIZE``
            was the default (and the owner's ask, 2026-09-15) until the
            production run showed what it does to card foliage: the export
            node has no voxel-size knob, the voxels are coarser than a leaf or
            a needle spray, and every one of the 110 Voxelize exports rendered
            as a bare, pale skeleton with a few dots along the branches -- the
            same beech h05 exported with ``PRESERVE_AREA`` beside it was a
            green tree (probe 2026-09-16 04:40). Voxelize also cost ~80x the
            export time. Pass ``NONE`` while iterating on densities or wiring,
            where only the instance count matters.
        collision_generation: ``ALL_GENERATIONS`` by default (owner,
            2026-09-15) -- trunk and branches collide in VR.
        import_all_palettes: Stage every baked palette tier of each species
            in the asset script, not only the one its graphs name.
        calibration_path: Override for the tracked calibration file.
        species: Standardized names to plan; None plans every species found.
        max_assembly_instances: Ceiling on the instances an offline solve may
            ask for -- 65,000 is Epic's Nanite assembly cap and an assembly
            past it fails to build; 60,000 leaves room for the tip cap and
            apex layers. A capped tree lands short of its leaf area and says
            so in the manifest (``capped``).
        tree_triangle_cap: Ceiling on one tree's predicted foliage triangles;
            an ash r16_h25m solved to 806 M on 2026-09-15, which no click
            should carry. Divided by the species' mean triangles per instance
            it is the other bound on ``max_instances``.

    Returns:
        What was planned, including a ``skipped`` line per tree left out.
    """
    from growpy.config.paths import get_species_growth_habit
    from growpy.config.pve_calibration import load_pve_calibration
    from growpy.io.unreal.pve_asset_script import (
        PALETTE_SOURCES,
        PVEAssetPlan,
        build_species_asset_spec,
        generate_pve_asset_script,
    )
    from growpy.io.unreal.pve_offline_solve import mean_triangles_per_prototype

    discovered = discover_growth_jsons(forest_root)
    if species is not None:
        wanted = set(species)
        unknown = wanted - set(discovered)
        if unknown:
            logger.warning(
                "no growth JSONs under %s for %s", forest_root, sorted(unknown)
            )
        discovered = {k: v for k, v in discovered.items() if k in wanted}
    if not discovered:
        logger.info("No growth JSONs under %s -- nothing to author", forest_root)
        return PVEGraphPlanResult()

    calibration = load_pve_calibration(calibration_path)

    graphs: list[PVEGraphSpec] = []
    asset_specs = []
    skipped: list[str] = []
    details: dict[str, dict] = {}

    for species, entries in sorted(discovered.items()):
        try:
            species_cal = calibration.for_species(
                species, habit=get_species_growth_habit(species)
            )
        except KeyError as err:
            skipped.append(f"{species}: {err} ({len(entries)} tree(s) skipped)")
            continue
        try:
            assets = build_species_asset_spec(
                species, content_root=content_root, palette=species_cal.palette
            )
            palette_areas = prototype_leaf_areas(assets)
        except FileNotFoundError as err:
            skipped.append(f"{species}: {err}")
            continue

        # The graph names only the chosen palette's parts, but the import
        # stages every tier the pipeline baked for the species, so switching
        # a species to its other palette is a plan change and a click, not a
        # re-import.
        import_spec = assets
        if import_all_palettes:
            for other in PALETTE_SOURCES:
                if other == species_cal.palette:
                    continue
                try:
                    extra = build_species_asset_spec(
                        species, content_root=content_root, palette=other
                    )
                except FileNotFoundError as err:
                    logger.info("%s: no %s palette to stage (%s)", species, other, err)
                    continue
                import_spec = dataclasses.replace(
                    import_spec, prototypes=import_spec.prototypes + extra.prototypes
                )
        asset_specs.append(import_spec)
        mesh_prefix = f"SK_{assets.content_folder.rsplit('/', 1)[-1]}"
        triangles = species_cal.palette_flat_mean_triangles
        if triangles is None:
            triangles = mean_triangles_per_prototype(
                [p.source for p in assets.prototypes]
            )
        logger.info(
            "%s: palette %s (%d prototypes, mean %.4f m2, ~%.0f tris), %s calibration, "
            "build from %s, fullness x%.2f",
            species,
            species_cal.palette,
            len(palette_areas),
            sum(palette_areas) / len(palette_areas),
            triangles,
            "derived" if species_cal.derived else "tracked",
            species_cal.build_from,
            species_cal.fullness,
        )
        chains: list[TreeChainSpec] = []
        instances: dict[str, int] = {}
        for entry in entries:
            try:
                if species_cal.builds_from_row(entry.tree_id):
                    planned = _measured_tree(
                        entry, species_cal, mesh_prefix, assets, palette_areas
                    )
                else:
                    planned = _offline_chain(
                        entry,
                        species_cal,
                        mesh_prefix,
                        assets,
                        palette_areas,
                        calibration.profile_mean,
                        max_instances=min(
                            max_assembly_instances,
                            int(tree_triangle_cap / triangles),
                        ),
                    )
            except (KeyError, ValueError, FileNotFoundError) as err:
                skipped.append(f"{species} {entry.tree_id}: {err}")
                continue
            chains.append(planned.chain)
            instances[planned.chain.mesh_name] = planned.instances
            details[planned.chain.mesh_name] = planned.detail
            logger.info(
                "  %s: %s %s density %s -> %d instances, %s m2 (target %s)",
                entry.tree_id,
                planned.detail.get("density_source"),
                planned.detail.get("layout"),
                planned.detail.get("density", planned.detail.get("fill_density")),
                planned.instances,
                planned.detail.get("predicted_m2"),
                planned.detail.get("target_m2"),
            )

        if not chains:
            continue

        logger.info("%s: %d chain(s)", species, len(chains))
        groups = split_by_triangles(
            chains,
            # Bound explicitly rather than closed over: this species' counts,
            # even if the call is ever deferred past the loop.
            lambda c, counts=instances: counts[c.mesh_name],
            triangles,
            triangle_cap,
        )
        label = assets.content_folder.rsplit("/", 1)[-1]
        for index, group in enumerate(groups, 1):
            suffix = "" if len(groups) == 1 else f"_{index}"
            graphs.append(
                PVEGraphSpec(
                    graph_name=f"PVG_{label}{suffix}",
                    chains=group,
                    palette_meshes=assets.palette_meshes,
                    bark_material=assets.bark_material,
                    bark_y_scale=species_cal.bark_y_scale,
                    export_folder=f"{content_root}/Exported/{label}",
                    graph_folder=graph_folder,
                    profile_pin=calibration.profile_pin,
                    nanite_shape_preservation=nanite_shape_preservation,
                    collision_generation=collision_generation,
                )
            )

    for line in skipped:
        logger.warning("PVE graph plan skipped %s", line)

    if not graphs:
        return PVEGraphPlanResult(skipped=tuple(skipped))

    # Emitted beside the graph script and for exactly the species the run
    # produced, rather than for every calibrated species: the palette a graph
    # names is the palette that graph needs.
    asset_script = generate_pve_asset_script(
        output_dir, PVEAssetPlan(species=tuple(asset_specs))
    )

    return PVEGraphPlanResult(
        graphs=tuple(graphs),
        asset_script=asset_script,
        script=generate_pve_graph_builder_script(output_dir, graphs),
        manifest=write_coverage_manifest(output_dir, graphs, details=details),
        retune_script=generate_pve_retune_script(output_dir, graphs),
        skipped=tuple(skipped),
    )
