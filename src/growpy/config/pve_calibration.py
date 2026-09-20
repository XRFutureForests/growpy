"""Read the tracked PVE foliage calibration (``config/pve_calibration.toml``).

Each density in that file cost an Export click in the live editor, so the file
is tracked and this module is the only supported way to read it. Nothing here
touches ``data/tmp/``.

The loader exists as much for what it *refuses* as for what it returns. Three
ways of using this data are wrong in ways the engine does not complain about:

* **Building from ``solved_density``.** It is the solver's recommendation, not a
  measurement, and is not guaranteed to have been computed against the growth
  JSON the history was measured on. For the fir h05 trees it was computed at a
  different decimation fraction, and near the distributor's ``max(loops, 1)``
  floor the instance response is a staircase, so a stale recommendation landed
  +47 % out. :meth:`TreeCalibration.resolve_density` never reads it.

* **Reusing a history across ``relative_start``.** A non-zero ``relative_start``
  keeps the branch-root sample that 0.0 discards, adding exactly one instance
  per branch, so a density solved at one value is wrong at the other. Beech runs
  at 0.4 with a history measured at 0.0; every beech tree therefore carries an
  explicit ``build_density``. Falling back to a mismatched history raises.

* **Reconstructing a growth-JSON filename from the fraction.** Beech spells 0.06
  ``_f006`` and fir spells it ``_f060``, and a glob on the tree id alone matches
  four files for fir ``r05_h05m``. Each tree names its file, and
  :meth:`SpeciesCalibration.resolve_growth_json` joins it to a caller-supplied
  root rather than guessing.
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "CompoundSpec",
    "DensityLaw",
    "LadderSpec",
    "PVECalibration",
    "ResolvedDensity",
    "SpeciesCalibration",
    "TreeCalibration",
    "TwigJitter",
    "TwigPose",
    "WindPresets",
    "load_pve_calibration",
]

SCHEMA_VERSION = 1

_BUILD_SOURCES = frozenset({"measured", "offline"})


@dataclass(frozen=True)
class DensityLaw:
    """Fitted instances-per-tree law, used only to seed a solve."""

    slope_per_s: float
    floor_per_branch: float
    fitted_on: str


@dataclass(frozen=True)
class ResolvedDensity:
    """A build density and where it came from, so provenance survives a log."""

    density: int
    source: str
    instances: int | None = None

    def __int__(self) -> int:
        return self.density


@dataclass(frozen=True)
class TreeCalibration:
    """One calibrated tree."""

    tree_id: str
    growth_json: str
    fraction: float
    branches: int
    points: int
    target_m2: float
    target_instances: int
    history: tuple[tuple[int, int], ...]
    history_relative_start: float
    solved_density: int | None = None
    build_density: int | None = None
    build_instances: int | None = None
    build_density_source: str | None = None
    dbh_cm: float | None = None
    s_ratio: float | None = None
    source_height_m: float | None = None
    generations: int | None = None
    # Share of use_as_mask palette entries the tree builds with (XRFF-462).
    # A history pair is an UNMASKED measurement, so a masked tree must carry
    # an explicit build_density / build_instances of its own.
    mask_fraction: float = 0.0
    # Scale-graded ladder (XRFF-412): the Scale attribute each palette
    # prototype advertises, in ascending prototype-leaf-area order, solved as
    # quantiles of the tree's own placement radii so every tier is used about
    # equally. None = the palette is flat (uniform pick, no condition).
    scale_targets: tuple[float, ...] | None = None
    # Expected leaf area per spawned instance under that grading, m2; None =
    # the species' flat prototype mean applies.
    instance_leaf_area_m2: float | None = None

    def __post_init__(self) -> None:
        if not self.growth_json:
            raise ValueError(f"tree {self.tree_id!r} names no growth JSON")
        if self.build_density is not None and self.build_density < 1:
            raise ValueError(
                f"tree {self.tree_id!r} build_density must be >= 1, "
                f"got {self.build_density}"
            )
        if self.build_density_source not in (None, *_BUILD_SOURCES):
            raise ValueError(
                f"tree {self.tree_id!r} build_density_source must be one of "
                f"{sorted(_BUILD_SOURCES)}, got {self.build_density_source!r}"
            )
        for density, instances in self.history:
            if density < 1 or instances < 0:
                raise ValueError(
                    f"tree {self.tree_id!r} has a nonsensical history entry "
                    f"({density}, {instances})"
                )
        if not 0.0 <= self.mask_fraction < 1.0:
            raise ValueError(
                f"tree {self.tree_id!r} mask_fraction must be in [0, 1), "
                f"got {self.mask_fraction}"
            )
        if self.mask_fraction > 0.0 and self.build_density is None:
            raise ValueError(
                f"tree {self.tree_id!r} builds with mask_fraction "
                f"{self.mask_fraction} but names no build_density; its history "
                f"was measured unmasked and cannot stand in"
            )
        if self.scale_targets is not None:
            if not self.scale_targets or any(
                not 0.0 <= t <= 1.0 for t in self.scale_targets
            ):
                raise ValueError(
                    f"tree {self.tree_id!r} scale_targets must be non-empty "
                    f"values in [0, 1], got {self.scale_targets}"
                )
            if self.build_density is None:
                raise ValueError(
                    f"tree {self.tree_id!r} carries scale_targets but no "
                    f"build_density; a graded palette changes the leaf area per "
                    f"instance, so its history was solved for a flat one"
                )
        if self.instance_leaf_area_m2 is not None and self.instance_leaf_area_m2 <= 0:
            raise ValueError(
                f"tree {self.tree_id!r} instance_leaf_area_m2 must be positive"
            )

    def resolve_density(self, relative_start: float) -> ResolvedDensity:
        """The density to build this tree at, or a refusal explaining why not.

        ``build_density`` wins when present -- it is the value solved for the
        configuration actually being built. Otherwise the last measured history
        pair is used, but only if it was measured at the same ``relative_start``
        as the build, since the two are not interchangeable.

        ``solved_density`` is deliberately not consulted.
        """
        if self.build_density is not None:
            return ResolvedDensity(
                density=self.build_density,
                source=self.build_density_source or "offline",
                instances=self.build_instances,
            )
        if not self.history:
            raise ValueError(
                f"tree {self.tree_id!r} has neither a build_density nor a "
                f"measurement history, so there is nothing to build it from "
                f"(solved_density is a recommendation and is not usable)"
            )
        if abs(self.history_relative_start - relative_start) > 1e-9:
            raise ValueError(
                f"tree {self.tree_id!r} has no build_density and its history "
                f"was measured at relative_start="
                f"{self.history_relative_start}, but the build runs at "
                f"{relative_start}. A non-zero relative_start keeps the "
                f"branch-root sample that 0.0 discards, so it adds one "
                f"instance per branch and the densities are not "
                f"interchangeable -- re-solve, do not reuse"
            )
        density, instances = self.history[-1]
        return ResolvedDensity(density=density, source="measured", instances=instances)


@dataclass(frozen=True)
class TwigJitter:
    """One random RollPitchYaw entry of a twig pose, half-range in degrees."""

    mode: str
    degrees: float
    seed: int = 123456

    def __post_init__(self) -> None:
        if self.mode not in ("ROLL", "PITCH", "YAW"):
            raise ValueError(
                f"jitter mode must be ROLL, PITCH or YAW, got {self.mode!r}"
            )
        if not 0.0 < self.degrees <= 180.0:
            raise ValueError(f"jitter degrees must be in (0, 180], got {self.degrees}")


@dataclass(frozen=True)
class TwigPose:
    """How a species' twigs sit on their branches (XRFF-438, 2026-09-14).

    None of this changes instance COUNTS -- a pose is a rotation -- so the
    densities of a species stay valid whatever its pose says. The default is
    the measured silver-fir pose: sprays on the sides, tilted ``axil_angle``
    degrees toward the tip (0 = perpendicular), flattened, faces up; a leader
    keeps pointing up. Beech adds jitter, because its leaves incline ~20-30 deg
    in life rather than lying perfectly flat.

    The three variance knobs below are the exception to "nothing here changes
    anything but rotation" (XRFF-467, 2026-09-16). Without them every spray on
    a branch is the same size at the same angle in the same rhythm -- the
    caterpillar the 110-tree catalog was judged on.

    * ``randomize_scale`` is a uniform multiplier on each instance's scale. It
      changes no count, but leaf area goes as scale squared, so the offline
      solve corrects the density by ``E[scale^2]`` and a species' MEASURED
      densities are only valid at the range they were measured under.
    * ``randomize_axil_angle`` adds degrees to the axil angle per instance;
      rotation only, counts and area untouched.
    * ``spacing_ramp`` reshapes where along a branch the samples land. PVE
      evaluates it on the even loop value before the relative remap, so the
      count is untouched but the metronome rhythm is not.
    """

    reset_phyllotaxy: bool = True
    axil_angle: float = 30.0
    jitter: tuple[TwigJitter, ...] = ()
    randomize_scale: tuple[float, float] = (1.0, 1.0)
    randomize_axil_angle: tuple[float, float] = (0.0, 0.0)
    spacing_ramp: tuple[tuple[float, float], ...] | None = None
    # How successive instances advance around the branch. SPIRAL with the
    # species' formation is the shipped arrangement; WHORLED reads node_buds
    # and places that many at one node, which is the only random COUNT the
    # distributor has. phyllotaxy_additional_angle is added to the formation
    # angle, so under a PARASTICHOUS formation (base 0) it IS the advance --
    # 137.5 is the golden angle.
    phyllotaxy_type: str = "SPIRAL"
    node_buds: tuple[int, int] = (1, 1)
    phyllotaxy_additional_angle: float = 0.0

    def __post_init__(self) -> None:
        if not -90.0 <= self.axil_angle <= 90.0:
            raise ValueError(f"axil_angle must be in [-90, 90], got {self.axil_angle}")


@dataclass(frozen=True)
class WindPresets:
    """Which ``PVWindSettings`` asset a species' Export nodes carry, per tier.

    ``None`` means the plugin preset for that tier (the plan supplies it):
    ``DefaultSaplingWindSettings`` for the h05 tier, ``DefaultTreeWindSettings``
    above. A species that needs its own asset (XRFF-235) names it here; the
    tier split stays. Wind is a post-export annotation -- it changes no
    placement, so densities are unaffected.
    """

    tree: str | None = None
    sapling: str | None = None

    def __post_init__(self) -> None:
        for tier, value in (("tree", self.tree), ("sapling", self.sapling)):
            if value is not None and not value.startswith("/"):
                raise ValueError(
                    f"wind.{tier} must be a package path such as "
                    f"/Game/PVE/Wind/WS_x, got {value!r}"
                )


@dataclass(frozen=True)
class LadderSpec:
    """How a species' size ladder is graded onto its branches (XRFF-412).

    Epic's conifers give every palette entry a ``Scale`` target and activate
    the Scale condition, so thick limbs take large parts and thin tips small
    ones; the leader gets one large part from a dedicated apex layer gated to
    generation 1, and the main layer starts at generation 2 so the trunk is
    not sprayed along its whole length. The per-tree targets live on
    :class:`TreeCalibration` because the normalised radius distribution is
    the tree's own.

    The picker min-max normalises each entry's distance to the sample across
    the palette and keeps every entry under ``cutoff_threshold``. With
    targets set at the tree's radius quantiles, the small tiers sit within a
    few thousandths of one another while the two big sprays sit at 0.03 and
    0.08, so a wide cutoff (Epic's 0.3 with two candidates) draws six or
    seven candidates for most samples and the grading dissolves. 0.1 with a
    single candidate picks the big sprays crisply by radius and still draws
    among the near-equal small tiers at random -- measured on the six fir
    r08/r16 trees, 2026-09-15.

    ``tip_tier`` (2026-09-16) names one prototype, by name suffix, to sit at
    the END of every branch the main layer covers, as a density-1 cap layer
    like the compound layout's. Two reasons the main layer cannot do this on
    its own: the Scale picker hands a branch tip the SMALLEST tier, because
    the tip is the thinnest point (on the fir that is a single 0.005 m2
    shoot); and a branch shorter than ``2 x L_max / density`` gets one loop,
    which at ``relative_start = 0`` lands on the root and is discarded, so
    the short branches at the top of a conifer carry nothing at all. A cap
    at density 1 places at ``along = 1.0`` on every branch, both included.
    The solve counts its area, so the main density lands the total on target.
    None keeps the ladder as it was.
    """

    scale_weight: float = 1.0
    minimum_candidates: int = 1
    cutoff_threshold: float = 0.1
    apex: bool = True
    main_generation_start: int = 2
    tip_tier: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 < self.scale_weight <= 1.0:
            raise ValueError(f"scale_weight must be in (0, 1], got {self.scale_weight}")
        if not 1 <= self.minimum_candidates <= 10:
            raise ValueError(
                f"minimum_candidates must be in [1, 10], got {self.minimum_candidates}"
            )
        if not 0.0 <= self.cutoff_threshold <= 1.0:
            raise ValueError(
                f"cutoff_threshold must be in [0, 1], got {self.cutoff_threshold}"
            )
        if self.main_generation_start < 1:
            raise ValueError("main_generation_start is 1-based (trunk = 1)")


@dataclass(frozen=True)
class CompoundSpec:
    """How a species' compound (foliated-branch) palette is laid out (XRFF-463).

    Epic's shape, read off the MegaPlants library (2026-09-15): a FILL layer
    places parts along every branch above the trunk over the outer span, big
    parts near the base and small ones toward the tip (Scale-graded), at a
    spacing expressed against the trunk (PVE's loop count is
    ``int(density * L / L_max)`` with ``L_max`` the longest branch); a TIP CAP
    layer puts one small part on every branch end; an APEX layer puts one
    mid-size part on the leader. Tiers are named by the bake's ``pNN`` suffix,
    ascending in span.
    """

    fill_relative_start: float = 0.15
    fill_relative_end: float = 0.90
    fill_spacing_m: float = 0.4
    fill_generation_start: int = 2
    fill_tiers: tuple[str, ...] = ("p00", "p01", "p02")
    cap_tier: str | None = "p00"
    apex_tier: str | None = "p02"
    scale_weight: float = 1.0
    minimum_candidates: int = 1
    cutoff_threshold: float = 0.1

    def __post_init__(self) -> None:
        if not 0.0 <= self.fill_relative_start < self.fill_relative_end <= 1.0:
            raise ValueError(
                "compound fill needs 0 <= fill_relative_start < fill_relative_end "
                f"<= 1, got {self.fill_relative_start} / {self.fill_relative_end}"
            )
        if self.fill_spacing_m <= 0.0:
            raise ValueError("compound fill_spacing_m must be positive")
        if self.fill_generation_start < 1:
            raise ValueError("compound fill_generation_start is 1-based (trunk = 1)")
        if not self.fill_tiers:
            raise ValueError("compound fill_tiers must name at least one tier")
        if not 0.0 < self.scale_weight <= 1.0:
            raise ValueError(f"scale_weight must be in (0, 1], got {self.scale_weight}")
        if not 1 <= self.minimum_candidates <= 10:
            raise ValueError(
                f"minimum_candidates must be in [1, 10], got {self.minimum_candidates}"
            )
        if not 0.0 <= self.cutoff_threshold <= 1.0:
            raise ValueError(
                f"cutoff_threshold must be in [0, 1], got {self.cutoff_threshold}"
            )


@dataclass(frozen=True)
class SpeciesCalibration:
    """Every calibrated tree of one species, plus the settings they share.

    ``trees`` may be empty: a species with no measured rows is built entirely
    from the offline distributor model (see the plan). ``prototype_leaf_area_m2``
    and ``palette_flat_mean_triangles`` may be None for the same reason -- the
    plan derives them from the converted prototypes when the file does not
    record them.
    """

    species: str
    relative_start: float
    fraction: float
    prototype_leaf_area_m2: float | None
    palette_flat_mean_triangles: float | None
    history_relative_start: float
    trees: dict[str, TreeCalibration]
    phyllotaxy_formation: str = "OCTASTICHOUS"
    bark_y_scale: float | None = None
    prototype_area_per_triangle_m2: float | None = None
    forrester_model_id: str | None = None
    law: DensityLaw | None = None
    pose: TwigPose = TwigPose()
    wind: WindPresets = WindPresets()
    ladder: LadderSpec | None = None
    # Which prototype set the palette is built from (XRFF-463): "twigs" = the
    # per-object twig prototypes, "compound" = branch parts baked from a Grove
    # tree with its twigs welded on. Compound parts carry 0.1-0.7 m2 each, so a
    # density solved for one set is meaningless for the other.
    palette: str = "twigs"
    # Multiplier on the Forrester leaf-area target when a tree's density is
    # solved offline (owner direction 2026-09-15: optics first -- the
    # Forrester-calibrated fir read as a skeleton, x4 as a conifer). Leaf area
    # is reported beside every tree; this is where it is steered.
    fullness: float = 1.0
    # Share of foliage samples that spawn nothing (XRFF-462's palette masks,
    # lifted to the species). The offline solve raises the density to keep
    # the same expected count and leaf area; what changes is the rhythm --
    # the samples still sit on the distributor's even grid, but a random
    # 1 in n of them is missing, which is the one irregularity PVE offers
    # along a branch (spacing itself cannot be randomised). Owner, 2026-09-16:
    # beech rosettes toward the branch ends "placed in close and regular
    # succession". Must be a ratio the palette can spell (mask_entries_for);
    # a graded ladder cannot take it.
    mask_fraction: float = 0.0
    compound: CompoundSpec | None = None
    # "measured": a tree with a row builds from it; "offline": every tree is
    # solved by the plan and the rows stay as the record of what was measured
    # (the 2026-09-15 direction: leaf area is reported, not held).
    build_from: str = "measured"
    # True when synthesised from [pve_calibration.defaults] rather than read
    # from a species block of its own.
    derived: bool = False
    # Per-tree start keyed on TREE HEIGHT (XRFF-475, 2026-09-17): a piecewise-
    # linear ramp of ``[[height_m, relative_start], ...]`` evaluated at the
    # tree's own height and held flat outside the keys. ``relative_start`` is
    # a fraction of EACH branch's length, so one value cannot be right for a
    # 0.7 m h10 twig and a 2 m h25 limb. None keeps the flat value. Only the
    # offline-built trees read it; a measured row was measured at one start
    # and stays valid only there.
    relative_start_by_height: tuple[tuple[float, float], ...] | None = None
    # Ceiling on the instance base scale the plan may spend to close a leaf-
    # area gap the instance cap leaves (XRFF-474): a capped tree gets
    # ``min(max_base_scale, sqrt(target / area_at_cap))``, an uncapped one
    # stays at 1.0. Area goes as scale squared; leaves grow with it.
    max_base_scale: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.relative_start < 1.0:
            raise ValueError(
                f"species {self.species!r} relative_start must be in [0, 1), "
                f"got {self.relative_start}"
            )
        area = self.prototype_leaf_area_m2
        if area is not None and area <= 0.0:
            raise ValueError(
                f"species {self.species!r} prototype_leaf_area_m2 must be "
                f"positive, got {self.prototype_leaf_area_m2}"
            )
        if self.palette not in ("twigs", "compound"):
            raise ValueError(
                f"species {self.species!r} palette must be 'twigs' or "
                f"'compound', got {self.palette!r}"
            )
        if not 0.0 <= self.mask_fraction < 1.0:
            raise ValueError(
                f"species {self.species!r} mask_fraction must be in [0, 1), "
                f"got {self.mask_fraction}"
            )
        if self.fullness <= 0.0:
            raise ValueError(
                f"species {self.species!r} fullness must be positive, "
                f"got {self.fullness}"
            )
        if self.build_from not in _BUILD_SOURCES:
            raise ValueError(
                f"species {self.species!r} build_from must be one of "
                f"{sorted(_BUILD_SOURCES)}, got {self.build_from!r}"
            )
        if self.palette == "compound" and self.compound is None:
            object.__setattr__(self, "compound", CompoundSpec())
        ramp = self.relative_start_by_height
        if ramp is not None:
            if len(ramp) < 2 or any(
                b[0] <= a[0] for a, b in zip(ramp, ramp[1:], strict=False)
            ):
                raise ValueError(
                    f"species {self.species!r} relative_start_by_height needs >= 2 "
                    f"keys with strictly ascending heights, got {ramp}"
                )
            if any(not 0.0 <= v < 1.0 for _, v in ramp):
                raise ValueError(
                    f"species {self.species!r} relative_start_by_height values "
                    f"must be in [0, 1), got {ramp}"
                )
        if self.max_base_scale < 1.0:
            raise ValueError(
                f"species {self.species!r} max_base_scale must be >= 1.0, "
                f"got {self.max_base_scale}"
            )

    def relative_start_for(self, height_m: float) -> float:
        """``relative_start`` for a tree of ``height_m`` (the species' flat
        value when no height ramp is configured)."""
        if self.relative_start_by_height is None:
            return self.relative_start
        return _interp(self.relative_start_by_height, height_m)

    def builds_from_row(self, tree_id: str) -> bool:
        """Whether ``tree_id`` builds from its measured row rather than offline."""
        return self.build_from == "measured" and tree_id in self.trees

    def tree(self, tree_id: str) -> TreeCalibration:
        try:
            return self.trees[tree_id]
        except KeyError:
            raise KeyError(
                f"species {self.species!r} has no calibrated tree {tree_id!r}; "
                f"known: {sorted(self.trees)}"
            ) from None

    def resolve_density(self, tree_id: str) -> ResolvedDensity:
        """Build density for one tree, checked against this species' settings."""
        return self.tree(tree_id).resolve_density(self.relative_start)

    def resolve_growth_json(self, root: Path | str, tree_id: str) -> Path:
        """Locate a tree's growth JSON under ``root`` by its recorded name.

        The name is recorded rather than derived: the two species encode the
        same decimation fraction differently (beech ``_f006``, fir ``_f060``)
        and a tree id alone can match several files.
        """
        path = Path(root) / self.tree(tree_id).growth_json
        if not path.is_file():
            raise FileNotFoundError(
                f"growth JSON for {self.species} {tree_id} not found at {path}"
            )
        return path

    def leaf_area_m2(self, tree_id: str) -> float | None:
        """Leaf area the build density places, or None if it was never counted.

        Valid only for a flat scale ramp at 1.0, which is what the shipped
        graphs use. A non-flat ramp scales area by ``mean(scale ** 2)`` and this
        would overstate it -- see XRFF-443.
        """
        resolved = self.resolve_density(tree_id)
        if resolved.instances is None:
            return None
        per_instance = self.tree(tree_id).instance_leaf_area_m2
        if per_instance is None:
            per_instance = self.prototype_leaf_area_m2
        if per_instance is None:
            return None
        return resolved.instances * per_instance


@dataclass(frozen=True)
class PVECalibration:
    """The whole tracked calibration.

    ``defaults`` is the raw ``[pve_calibration.defaults]`` table: the settings
    a species with no block of its own is built with, optionally refined by a
    ``conifer`` / ``broadleaf`` sub-table. Kept raw so :meth:`for_species` can
    synthesise a :class:`SpeciesCalibration` per habit without pre-declaring
    every species in the file.
    """

    schema_version: int
    profile_mean: float
    profile_pin: str
    species: dict[str, SpeciesCalibration]
    defaults: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"pve_calibration schema_version {self.schema_version} is not "
                f"the {SCHEMA_VERSION} this loader understands"
            )

    def has_species(self, species: str) -> bool:
        return species in self.species

    def for_species(
        self, species: str, habit: str | None = None
    ) -> SpeciesCalibration:
        """The species' own block, or one synthesised from ``defaults``.

        A synthesised calibration carries no trees (every tree of the species
        is then solved offline by the plan) and marks itself ``derived`` so a
        log can say which trees were built on measured rows and which were not.

        Raises:
            KeyError: If the species has no block and there are no defaults.
        """
        try:
            return self.species[species]
        except KeyError:
            if not self.defaults:
                raise KeyError(
                    f"no PVE calibration for species {species!r} and no "
                    f"[pve_calibration.defaults] to build it from; "
                    f"calibrated: {sorted(self.species)}"
                ) from None
        data = dict(_merge_defaults(self.defaults, habit))
        data.pop("trees", None)
        if "fraction" not in data:
            raise KeyError(
                f"[pve_calibration.defaults] names no `fraction`, so a derived "
                f"calibration for {species!r} cannot record what decimation its "
                f"growth JSONs carry"
            )
        return _species(species, data, derived=True)


_HABITS = ("conifer", "broadleaf")


def _law(data: dict[str, Any] | None) -> DensityLaw | None:
    if not data:
        return None
    return DensityLaw(
        slope_per_s=float(data["slope_per_s"]),
        floor_per_branch=float(data["floor_per_branch"]),
        fitted_on=str(data.get("fitted_on", "")),
    )


def _tree(tree_id: str, data: dict[str, Any], history_relative_start: float):
    history = tuple((int(d), int(n)) for d, n in data.get("history", []))
    return TreeCalibration(
        tree_id=tree_id,
        growth_json=str(data.get("growth_json", "")),
        fraction=float(data["fraction"]),
        branches=int(data["branches"]),
        points=int(data["points"]),
        target_m2=float(data["target_m2"]),
        target_instances=int(data["target_instances"]),
        history=history,
        history_relative_start=history_relative_start,
        solved_density=_opt_int(data.get("solved_density")),
        build_density=_opt_int(data.get("build_density")),
        build_instances=_opt_int(data.get("build_instances")),
        build_density_source=data.get("build_density_source"),
        dbh_cm=_opt_float(data.get("dbh_cm")),
        s_ratio=_opt_float(data.get("s_ratio")),
        source_height_m=_opt_float(data.get("source_height_m")),
        generations=_opt_int(data.get("generations")),
        mask_fraction=float(data.get("mask_fraction", 0.0)),
        scale_targets=(
            tuple(float(t) for t in data["scale_targets"])
            if data.get("scale_targets") is not None
            else None
        ),
        instance_leaf_area_m2=_opt_float(data.get("instance_leaf_area_m2")),
    )


def _opt_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _opt_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _pair(value: Any, default: tuple[float, float]) -> tuple[float, float]:
    """A two-float (min, max) from TOML, or ``default`` when absent."""
    if value is None:
        return default
    lo, hi = value
    return (float(lo), float(hi))


def _ramp(value: Any) -> tuple[tuple[float, float], ...] | None:
    """A ``[[x, y], ...]`` ramp from TOML, or None when absent."""
    if value is None:
        return None
    return tuple((float(x), float(y)) for x, y in value)


def _interp(keys: tuple[tuple[float, float], ...], x: float) -> float:
    """Piecewise-linear ``y`` at ``x``, held flat outside the first/last key."""
    if x <= keys[0][0]:
        return keys[0][1]
    if x >= keys[-1][0]:
        return keys[-1][1]
    for (x0, y0), (x1, y1) in zip(keys, keys[1:], strict=False):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return keys[-1][1]


def _pose(data: dict[str, Any] | None) -> TwigPose:
    if not data:
        return TwigPose()
    jitter = tuple(
        TwigJitter(
            mode=str(j["mode"]).upper(),
            degrees=float(j["degrees"]),
            seed=int(j.get("seed", 123456)),
        )
        for j in data.get("jitter", [])
    )
    ramp = data.get("spacing_ramp")
    return TwigPose(
        reset_phyllotaxy=bool(data.get("reset_phyllotaxy", True)),
        axil_angle=float(data.get("axil_angle", 30.0)),
        jitter=jitter,
        randomize_scale=_pair(data.get("randomize_scale"), (1.0, 1.0)),
        randomize_axil_angle=_pair(data.get("randomize_axil_angle"), (0.0, 0.0)),
        spacing_ramp=(
            None
            if ramp is None
            else tuple((float(t), float(v)) for t, v in ramp)
        ),
        phyllotaxy_type=str(data.get("phyllotaxy_type", "SPIRAL")).upper(),
        node_buds=(
            (1, 1)
            if data.get("node_buds") is None
            else (int(data["node_buds"][0]), int(data["node_buds"][1]))
        ),
        phyllotaxy_additional_angle=float(
            data.get("phyllotaxy_additional_angle", 0.0)
        ),
    )


def _wind(data: dict[str, Any] | None) -> WindPresets:
    if not data:
        return WindPresets()
    return WindPresets(
        tree=None if data.get("tree") is None else str(data["tree"]),
        sapling=None if data.get("sapling") is None else str(data["sapling"]),
    )


def _ladder(data: dict[str, Any] | None) -> LadderSpec | None:
    if data is None:
        return None
    return LadderSpec(
        scale_weight=float(data.get("scale_weight", 1.0)),
        minimum_candidates=int(data.get("minimum_candidates", 1)),
        cutoff_threshold=float(data.get("cutoff_threshold", 0.1)),
        apex=bool(data.get("apex", True)),
        main_generation_start=int(data.get("main_generation_start", 2)),
        tip_tier=(
            None if data.get("tip_tier") in ("", None) else str(data["tip_tier"])
        ),
    )


def _compound(data: dict[str, Any] | None) -> CompoundSpec | None:
    if data is None:
        return None
    kwargs: dict[str, Any] = {}
    for key in (
        "fill_relative_start",
        "fill_relative_end",
        "fill_spacing_m",
        "scale_weight",
        "cutoff_threshold",
    ):
        if key in data:
            kwargs[key] = float(data[key])
    for key in ("fill_generation_start", "minimum_candidates"):
        if key in data:
            kwargs[key] = int(data[key])
    if "fill_tiers" in data:
        kwargs["fill_tiers"] = tuple(str(t) for t in data["fill_tiers"])
    for key in ("cap_tier", "apex_tier"):
        if key in data:
            kwargs[key] = None if data[key] in ("", None) else str(data[key])
    return CompoundSpec(**kwargs)


def _species(
    name: str, data: dict[str, Any], *, derived: bool = False
) -> SpeciesCalibration:
    relative_start = float(data.get("relative_start", 0.0))
    # Defaults to the species' own relative_start: a history with no recorded
    # measurement configuration is assumed to have been measured under the one
    # in force, which is the only reading that cannot silently invent a
    # mismatch.
    history_relative_start = float(data.get("history_relative_start", relative_start))
    trees = {
        tree_id: _tree(tree_id, tree_data, history_relative_start)
        for tree_id, tree_data in sorted(data.get("trees", {}).items())
    }
    return SpeciesCalibration(
        species=name,
        relative_start=relative_start,
        fraction=float(data["fraction"]),
        prototype_leaf_area_m2=_opt_float(data.get("prototype_leaf_area_m2")),
        palette_flat_mean_triangles=_opt_float(data.get("palette_flat_mean_triangles")),
        history_relative_start=history_relative_start,
        trees=trees,
        phyllotaxy_formation=str(data.get("phyllotaxy_formation", "OCTASTICHOUS")),
        bark_y_scale=_opt_float(data.get("bark_y_scale")),
        prototype_area_per_triangle_m2=_opt_float(
            data.get("prototype_area_per_triangle_m2")
        ),
        forrester_model_id=data.get("forrester_model_id"),
        law=_law(data.get("law")),
        pose=_pose(data.get("pose")),
        wind=_wind(data.get("wind")),
        ladder=_ladder(data.get("ladder")),
        palette=str(data.get("palette", "twigs")),
        fullness=float(data.get("fullness", 1.0)),
        mask_fraction=float(data.get("mask_fraction", 0.0)),
        compound=_compound(data.get("compound")),
        relative_start_by_height=_ramp(data.get("relative_start_by_height")),
        max_base_scale=float(data.get("max_base_scale", 1.0)),
        build_from=str(data.get("build_from", "measured")),
        derived=derived,
    )


def _merge_defaults(defaults: dict[str, Any], habit: str | None) -> dict[str, Any]:
    """The defaults block with its ``conifer`` / ``broadleaf`` sub-table folded in.

    One level deep: a sub-table under the habit (``pose``, ``ladder``,
    ``compound``) replaces the general one wholesale rather than merging
    key-by-key, so a habit that names a pose owns that pose.
    """
    merged = {k: v for k, v in defaults.items() if k not in _HABITS}
    if habit in _HABITS and isinstance(defaults.get(habit), dict):
        merged.update(defaults[habit])
    return merged


def _default_path() -> Path:
    """``config/pve_calibration.toml``, found the way the rest of growpy does.

    Deliberately a single named file rather than the merged ``config/`` dict:
    the merge is keyed on sections :class:`~growpy.config.core.GrowPyConfig`
    knows about, and calibration data has no business growing a branch there.
    """
    from growpy.config.core import _find_config_dir

    cfg_dir = _find_config_dir()
    if cfg_dir is None:
        raise FileNotFoundError(
            "no config directory found -- set GROWPY_CONFIG, or run from a "
            "directory containing config/"
        )
    return cfg_dir / "pve_calibration.toml"


def load_pve_calibration(path: Path | str | None = None) -> PVECalibration:
    """Load the tracked calibration, defaulting to ``config/pve_calibration.toml``."""
    toml_path = Path(path) if path is not None else _default_path()
    if not toml_path.is_file():
        raise FileNotFoundError(f"PVE calibration not found at {toml_path}")
    with open(toml_path, "rb") as handle:
        raw = tomllib.load(handle)
    data = raw.get("pve_calibration")
    if not data:
        raise ValueError(f"{toml_path} has no [pve_calibration] section")
    defaults = data.get("defaults") or {}
    if not isinstance(defaults, dict):
        raise ValueError(f"{toml_path}: [pve_calibration.defaults] must be a table")
    calibration = PVECalibration(
        schema_version=int(data.get("schema_version", 0)),
        profile_mean=float(data["profile_mean"]),
        profile_pin=str(data["profile_pin"]),
        species={
            name: _species(name, species_data)
            for name, species_data in sorted(data.get("species", {}).items())
        },
        defaults=defaults,
    )
    logger.debug(
        "loaded PVE calibration from %s: %d species, %d trees",
        toml_path,
        len(calibration.species),
        sum(len(s.trees) for s in calibration.species.values()),
    )
    return calibration
