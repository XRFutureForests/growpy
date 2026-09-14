"""Author PVE graphs on the Growth Data JSON route (UE 5.7+).

This is the working alternative to the USD assembly path: Grove's skeleton is
exported as a growth JSON, PVE's mesher rebuilds the trunk and branches from it,
and PVE's foliage distributor places twig prototypes procedurally. Proven
end-to-end for European beech and silver fir -- height passes through exactly,
trunk radius is preserved and reshaped by the trunk profile, and the foliage
distributor's instance count is predictable to the instance.

It supersedes :mod:`growpy.io.unreal.pve_graph_script`, which wires the Preset
Loader node. That node is deprecated in UE 5.8 and produces no output, so the
older module cannot build a working graph on the engine we ship on.

Chain shape, one per tree::

    GrowthDataJsonImporter ->|In
    PlantProfileLoader     ->|Profile        MeshBuilder -> FoliageDistributor -> Export
    MeshBuilderBranchRadius->|BranchRadius                      ^
    MeshBuilderMaterialDetail->|MaterialDetails      FoliagePalette

The profile loader, palette and bark material are shared by every chain in a
graph; importer, mesher, distributor and export node are per tree.

WHAT IS ENCODED HERE, AND WHY IT IS NOT OBVIOUS
-----------------------------------------------

Several distributor settings behave in ways that cost several sessions to
establish. They are defaults here so no caller has to rediscover them.

* **A flat ``scale_ramp`` at 1.0.** The shipped default ramp is 1.0 -> 0.1 and,
  under ``ScaleRampBasis = Plant``, the lookup is the *inverted* plant gradient
  (0 at the seed, 1 at every tip). Foliage sits on outer branches whose whole
  span is near gradient 1, so the default places it at roughly a tenth of
  natural size. Leaf area goes as scale squared, and both of the obvious ways to
  measure it -- instance count times prototype area, and total foliage triangles
  times area per triangle -- are blind to scale, so a tree can measure exactly on
  target and carry about an eighth of the leaf it is credited with. A flat 1.0
  places every twig at the size Grove grew it.

* **``face.vector2``, never ``vector1``.** ``AdjustFaceVectors`` evaluates
  ``Vector1`` only when ``bDualVectors`` is set, and ``Vector2`` always.
  With duals off -- the normal case -- ``Vector1`` is dead. Writing it is a
  silent no-op, so :class:`FoliageVectorSpec` raises rather than let it happen.

* **``AXIS_AIM`` lays sprays flat; ``AXIS_FLATTEN`` stands them on edge.**
  ``AxisFlatten`` projects the spray *normal* into the plane perpendicular to the
  axis, which makes the spray plane vertical. ``AxisAim`` rotates the normal onto
  the axis, so with a world-up axis the spray lies flat -- the pectinate
  arrangement of a fir.

* **``affect_tip`` and ``auto_align_end``.** By engine default a tip instance has
  its frame overwritten by the branch frame (``bAutoAlignEnd``, default true) and
  is then skipped by every aim/face entry (``bAffectTip``, default false), so it
  ignores every orientation setting *and* the phyllotaxy. Tip instances are not a
  rounding error: they run from ~9 % of a large tree to over 60 % of a small one,
  because small trees sit near the distributor's one-instance-per-branch floor.
  Left at the engine defaults, orientation therefore bites several times harder
  on a large tree than a small one. The defaults here make every twig obey.

* **``relative_start`` is a strong lever with a hard cost.** It remaps each
  branch's placement span into ``[start, end]`` of its length, so foliage sits on
  the outer part of every branch rather than running back to the fork. On a 15 m
  beech it lifts the lowest foliage from 0.14 m to 1.60 m and keeps leaves off
  the thick inner span of primary limbs. But it is **not count-neutral against
  0.0**: ``LoopNumber = max(int(density * lengthRatio), 1)`` always yields at
  least one sample, and at 0.0 that sample lands exactly on the branch root and
  is discarded. Any non-zero value keeps it, so every branch gains one instance
  and the count acquires a floor of ``N >= branch count``. Re-solve densities
  whenever it changes, and check that floor against the leaf-area target first --
  on heavily decimated conifers it can already exceed the target at density 1.
  (This is also where the fitted density law's ``-1.039 * branches`` intercept
  comes from: it is the root-skip, not the ``max(loops, 1)`` floor.)

* **``node_buds`` is read only under Whorled phyllotaxy.** Setting it under
  Spiral is a no-op; the formation angle is what varies (Distichous 180 degrees,
  Octastichous 135, and so on).

Each Export node needs one manual click in the editor -- the export is modal --
but a graph with N chains yields N meshes per click, so a whole species costs a
handful of clicks rather than one per tree.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = [
    "FoliageVectorSpec",
    "DistributorSpec",
    "TreeChainSpec",
    "PVEGraphSpec",
    "generate_pve_graph_builder_script",
    "generate_pve_retune_script",
    "split_by_triangles",
    "write_coverage_manifest",
]

# Enum members as the UE Python API spells them.
_FACE_VECTORS = frozenset(
    {"APICAL", "BRANCH", "AXIS_FLATTEN", "AXIS_AIM", "LIGHT_OPTIMAL", "LIGHT_AVOID"}
)
_AIM_VECTORS = frozenset(
    {"BRANCH_UP_FLATTEN", "AXIS_FLATTEN", "AXIS_AIM", "LIGHT_OPTIMAL", "LIGHT_AVOID"}
)
_BASES = frozenset({"BRANCH", "PLANT"})
_PHYLLOTAXY_TYPES = frozenset(
    {"ALTERNATE", "OPPOSITE", "DECUSSATE", "WHORLED", "SPIRAL"}
)
_FORMATIONS = frozenset(
    {"DISTICHOUS", "TRISTICHOUS", "PENTASTICHOUS", "OCTASTICHOUS", "PARASTICHOUS"}
)
_NANITE_SHAPE = frozenset({"NONE", "PRESERVE_AREA", "VOXELIZE"})


@dataclass(frozen=True)
class FoliageVectorSpec:
    """One aim or face vector entry.

    ``vector2`` is the slot the distributor reads. ``vector1`` is evaluated only
    when ``dual`` is set, so naming it without ``dual`` is silently ignored by
    the engine and is rejected here instead.
    """

    vector2: str = "AXIS_AIM"
    axis: tuple[float, float, float] = (0.0, 0.0, 1.0)
    strength: float = 1.0
    affect_tip: bool = True
    flat_ramp: bool = True
    vector1: str | None = None
    dual: bool = False
    kind: str = "face"

    def __post_init__(self) -> None:
        if self.kind not in ("face", "aim"):
            raise ValueError(f"kind must be 'face' or 'aim', got {self.kind!r}")
        allowed = _FACE_VECTORS if self.kind == "face" else _AIM_VECTORS
        if self.vector2 not in allowed:
            raise ValueError(
                f"{self.kind} vector2 {self.vector2!r} is not one of {sorted(allowed)}"
            )
        if self.vector1 is not None and not self.dual:
            raise ValueError(
                "vector1 is only evaluated when dual=True; with duals off the "
                "distributor reads vector2 and writing vector1 is a silent no-op"
            )
        if self.vector1 is not None and self.vector1 not in allowed:
            raise ValueError(
                f"{self.kind} vector1 {self.vector1!r} is not one of {sorted(allowed)}"
            )
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"strength must be in [0, 1], got {self.strength}")
        if len(self.axis) != 3 or all(abs(c) < 1e-9 for c in self.axis):
            raise ValueError(f"axis must be a non-zero 3-vector, got {self.axis!r}")


@dataclass(frozen=True)
class DistributorSpec:
    """Parametric foliage distributor settings for one tree."""

    branch_density: int
    spacing_basis: str = "BRANCH"
    # Default 0.0 because a non-zero value changes the instance count, so it
    # must travel with densities solved for it. See the module docstring.
    relative_start: float = 0.0
    relative_end: float = 1.0
    phyllotaxy_type: str = "SPIRAL"
    phyllotaxy_formation: str = "OCTASTICHOUS"
    node_buds: int = 1
    reset_phyllotaxy: bool = False
    axil_angle: float = 35.0
    # The engine default is linear 0 -> 1 on the plant gradient, i.e. the
    # effective angle is axil_angle * gradient: nil at the seed, full at the
    # tips. (1.0, 1.0) makes it constant.
    axil_angle_ramp: tuple[float, float] = (0.0, 1.0)
    single_bud_tip: bool = True
    rotation: float = 0.0
    base_scale: float = 1.0
    scale_ramp_basis: str = "PLANT"
    scale_ramp: tuple[float, float] = (1.0, 1.0)
    branch_scale_impact: float = 0.0
    auto_align_end: bool = False
    face: FoliageVectorSpec | None = field(
        default_factory=lambda: FoliageVectorSpec(kind="face", vector2="AXIS_AIM")
    )
    aim: FoliageVectorSpec | None = None

    def __post_init__(self) -> None:
        if self.branch_density < 1:
            raise ValueError(f"branch_density must be >= 1, got {self.branch_density}")
        for name, value in (
            ("spacing_basis", self.spacing_basis),
            ("scale_ramp_basis", self.scale_ramp_basis),
        ):
            if value not in _BASES:
                raise ValueError(
                    f"{name} must be one of {sorted(_BASES)}, got {value!r}"
                )
        if self.phyllotaxy_type not in _PHYLLOTAXY_TYPES:
            raise ValueError(
                f"phyllotaxy_type must be one of {sorted(_PHYLLOTAXY_TYPES)}"
            )
        if self.phyllotaxy_formation not in _FORMATIONS:
            raise ValueError(
                f"phyllotaxy_formation must be one of {sorted(_FORMATIONS)}"
            )
        if not 0.0 <= self.relative_start < self.relative_end <= 1.0:
            raise ValueError(
                "require 0 <= relative_start < relative_end <= 1, got "
                f"{self.relative_start} / {self.relative_end}"
            )
        if len(self.scale_ramp) != 2 or any(v <= 0.0 for v in self.scale_ramp):
            raise ValueError(
                f"scale_ramp must be two positive values, got {self.scale_ramp!r}"
            )
        if self.face is not None and self.face.kind != "face":
            raise ValueError("face spec must be built with kind='face'")
        if self.aim is not None and self.aim.kind != "aim":
            raise ValueError("aim spec must be built with kind='aim'")


@dataclass(frozen=True)
class TreeChainSpec:
    """One tree: a growth JSON in, one exported mesh out."""

    growth_json: Path
    mesh_name: str
    distributor: DistributorSpec

    def __post_init__(self) -> None:
        if not self.mesh_name:
            raise ValueError("mesh_name must not be empty")


@dataclass(frozen=True)
class PVEGraphSpec:
    """One PVE graph asset holding one chain per tree."""

    graph_name: str
    chains: tuple[TreeChainSpec, ...]
    palette_meshes: tuple[str, ...]
    bark_material: str
    export_folder: str
    graph_folder: str = "/Game/PVE/Graphs"
    profile_asset: str = (
        "/ProceduralVegetationEditor/SampleAssets/StarterContent"
        "/Trunk_Profiles/Trunk_Profiles_01"
    )
    profile_pin: str = "plantProfile_8"
    bark_y_scale: float | None = None
    da_vinci_rule_strength: float = 0.0
    min_radius: float = 0.0
    create_nanite_foliage: bool = True
    nanite_shape_preservation: str = "VOXELIZE"

    def __post_init__(self) -> None:
        if not self.chains:
            raise ValueError(f"graph {self.graph_name!r} has no chains")
        if not self.palette_meshes:
            raise ValueError(f"graph {self.graph_name!r} has an empty foliage palette")
        if self.nanite_shape_preservation not in _NANITE_SHAPE:
            raise ValueError(
                f"nanite_shape_preservation must be one of {sorted(_NANITE_SHAPE)}"
            )
        names = [c.mesh_name for c in self.chains]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(
                f"graph {self.graph_name!r} exports duplicate mesh names: "
                f"{sorted(dupes)} -- each chain overwrites the last"
            )


def _ramp_text(start: float, end: float) -> str:
    """A two-key linear FRichCurve, as UE's native struct serialiser spells it.

    ``FPVFloatRamp::EditorCurveData`` is a plain UPROPERTY with no EditAnywhere,
    so ``set_editor_property`` cannot reach it. ``import_text`` runs the native
    serialiser and does.
    """
    return (
        "(EditorCurveData=(Keys=("
        f"(InterpMode=RCIM_Linear,Time=0.000000,Value={start:.6f}),"
        f"(InterpMode=RCIM_Linear,Time=1.000000,Value={end:.6f}))))"
    )


def _vector_payload(spec: FoliageVectorSpec | None) -> dict | None:
    if spec is None:
        return None
    return {
        "kind": spec.kind,
        "vector1": spec.vector1,
        "vector2": spec.vector2,
        "axis": list(spec.axis),
        "strength": spec.strength,
        "affect_tip": spec.affect_tip,
        "dual": spec.dual,
        "ramp": _ramp_text(1.0, 1.0) if spec.flat_ramp else None,
    }


def _graph_payload(graph: PVEGraphSpec) -> dict:
    return {
        "graph_name": graph.graph_name,
        "graph_folder": graph.graph_folder,
        "export_folder": graph.export_folder,
        "profile_asset": graph.profile_asset,
        "profile_pin": graph.profile_pin,
        "palette_meshes": list(graph.palette_meshes),
        "bark_material": graph.bark_material,
        "bark_y_scale": graph.bark_y_scale,
        "da_vinci_rule_strength": graph.da_vinci_rule_strength,
        "min_radius": graph.min_radius,
        "create_nanite_foliage": graph.create_nanite_foliage,
        "nanite_shape_preservation": graph.nanite_shape_preservation,
        "chains": [
            {
                "growth_json": str(Path(c.growth_json).resolve()).replace("\\", "/"),
                "mesh_name": c.mesh_name,
                "branch_density": c.distributor.branch_density,
                "spacing_basis": c.distributor.spacing_basis,
                "relative_start": c.distributor.relative_start,
                "relative_end": c.distributor.relative_end,
                "phyllotaxy_type": c.distributor.phyllotaxy_type,
                "phyllotaxy_formation": c.distributor.phyllotaxy_formation,
                "node_buds": c.distributor.node_buds,
                "reset_phyllotaxy": c.distributor.reset_phyllotaxy,
                "axil_angle": c.distributor.axil_angle,
                "axil_angle_ramp": _ramp_text(*c.distributor.axil_angle_ramp),
                "single_bud_tip": c.distributor.single_bud_tip,
                "rotation": c.distributor.rotation,
                "base_scale": c.distributor.base_scale,
                "scale_ramp_basis": c.distributor.scale_ramp_basis,
                "scale_ramp": _ramp_text(*c.distributor.scale_ramp),
                "branch_scale_impact": c.distributor.branch_scale_impact,
                "auto_align_end": c.distributor.auto_align_end,
                "face": _vector_payload(c.distributor.face),
                "aim": _vector_payload(c.distributor.aim),
            }
            for c in graph.chains
        ],
    }


_SCRIPT_TEMPLATE = '''\
"""GrowPy PVE graph builder -- auto-generated, do not edit.

Generated by: growpy.io.unreal.pve_graph_builder

Builds one ProceduralVegetation asset per graph spec, each holding one
importer -> mesher -> distributor -> export chain per tree. Every chain's
settings are read back after writing and the edge count is checked, so a
silently-dropped property or edge shows up in this script's own log rather
than in a render an hour later.

Each graph then needs ONE manual Export click in the editor.
"""
import unreal

GRAPHS = {graphs!r}

PV = "/Script/ProceduralVegetation."
PVE_ED = "/Script/ProceduralVegetationEditor."

eal = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
editors = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)


def setp(obj, names, value):
    """Set the first property that exists, and RAISE if none do.

    A helper that swallowed the failure is how a Vector1Axis write was lost for
    a whole session: the property exists but wants a Vector3f, and a silent
    helper turned the type error into a no-op.
    """
    if isinstance(names, str):
        names = (names,)
    for n in names:
        try:
            obj.set_editor_property(n, value)
            return n
        except Exception:
            continue
    raise RuntimeError(
        "none of %s settable on %s" % (list(names), type(obj).__name__)
    )


def pin_label(pin):
    return str(pin.get_editor_property("properties").get_editor_property("label"))


def open_graph(asset):
    inst = unreal.new_object(
        unreal.load_class(None, PV + "ProceduralVegetationInstance")
    )
    gi = inst.get_editor_property("graph_instance")
    gi.set_editor_property("procedural_vegetation", asset)
    return gi.get_mutable_pcg_graph()


def make_graph(folder, name):
    """Create the asset and return (graph, actual_name).

    get_mutable_pcg_graph() intermittently returns None on a freshly created
    asset; retrying under a suffixed name is cheaper than failing the batch.
    """
    for candidate in (name, name + "_b"):
        full = "%s/%s" % (folder, candidate)
        if eal.does_asset_exist(full):
            existing = eal.load_asset(full)
            if existing is not None:
                editors.close_all_editors_for_asset(existing)
            eal.delete_asset(full)
            unreal.SystemLibrary.collect_garbage()
        asset = tools.create_asset(
            candidate,
            folder,
            unreal.load_class(None, PV + "ProceduralVegetation"),
            unreal.new_object(
                unreal.load_class(None, PVE_ED + "ProceduralVegetationFactory")
            ),
        )
        if asset is None:
            continue
        graph = open_graph(asset)
        if graph is not None:
            return graph, candidate
        unreal.SystemLibrary.collect_garbage()
    raise RuntimeError("could not create a usable graph for %s" % name)


def apply_vector_group(dist_settings, spec, group_prop, list_prop, entry_cls,
                       enum_cls, auto_align):
    vectors = dist_settings.get_editor_property("vector_settings")
    group = vectors.get_editor_property(group_prop)
    setp(group, ("auto_align_end", "b_auto_align_end"), bool(auto_align))
    if spec is None:
        group.set_editor_property(list_prop, [])
    else:
        entry = entry_cls()
        # Vector2 is the slot the distributor reads when duals are off.
        setp(entry, "vector2", getattr(enum_cls, spec["vector2"]))
        setp(entry, "vector2_axis", unreal.Vector3f(*spec["axis"]))
        setp(entry, "vector2_strength", float(spec["strength"]))
        setp(entry, "dual_vectors", bool(spec["dual"]))
        if spec["dual"] and spec["vector1"]:
            setp(entry, "vector1", getattr(enum_cls, spec["vector1"]))
            setp(entry, "vector1_axis", unreal.Vector3f(*spec["axis"]))
        setp(entry, ("affect_tip", "b_affect_tip"), bool(spec["affect_tip"]))
        if spec["ramp"]:
            ramp = entry.get_editor_property("vector_ramp")
            ramp.import_text(spec["ramp"])
            setp(entry, "vector_ramp", ramp)
        group.set_editor_property(list_prop, [entry])
    vectors.set_editor_property(group_prop, group)
    dist_settings.set_editor_property("vector_settings", vectors)


def build(spec):
    graph, name = make_graph(spec["graph_folder"], spec["graph_name"])
    full = "%s/%s" % (spec["graph_folder"], name)

    profile_node, profile_settings = graph.add_node_of_type(
        unreal.PVPlantProfileLoaderSettings
    )
    profile_node.set_node_position(-260, 0)
    profile_asset = eal.load_asset(spec["profile_asset"])
    if profile_asset is None:
        raise RuntimeError("trunk profile %s did not resolve" % spec["profile_asset"])
    profile_settings.set_editor_property("plant_profile_data", profile_asset)
    pins = [
        p for p in
        [pin_label(x) for x in profile_node.get_editor_property("output_pins")]
        if p == spec["profile_pin"]
    ]
    if not pins:
        raise RuntimeError("trunk profile pin %s absent" % spec["profile_pin"])
    profile_pin = pins[0]

    palette_node, palette_settings = graph.add_node_of_type(
        unreal.PVFoliagePaletteSettings
    )
    palette_node.set_node_position(-260, 220)
    infos = []
    missing = []
    for path in spec["palette_meshes"]:
        mesh = eal.load_asset(path)
        if mesh is None:
            missing.append(path)
            continue
        info = unreal.PVFoliageInfo()
        info.set_editor_property("mesh", mesh)
        infos.append(info)
    if missing:
        raise RuntimeError("palette meshes did not resolve: %s" % missing)
    palette_settings.set_editor_property("foliage_infos", infos)

    bark = eal.load_asset(spec["bark_material"])
    if bark is None:
        raise RuntimeError("bark material %s did not resolve" % spec["bark_material"])

    for index, chain in enumerate(spec["chains"]):
        row = index * 620

        import_node, import_settings = graph.add_node_of_type(
            unreal.PVGrowthDataJsonImporterSettings
        )
        import_node.set_node_position(0, row)
        file_path = unreal.FilePath()
        file_path.set_editor_property("file_path", chain["growth_json"])
        import_settings.set_editor_property("growth_data_file", file_path)

        mesh_node, _ = graph.add_node_of_type(unreal.PVMeshBuilderSettings)
        mesh_node.set_node_position(320, row)

        radius_node, radius_settings = graph.add_node_of_type(
            unreal.PVMeshBuilderBranchRadiusSettings
        )
        radius_node.set_node_position(0, row + 180)
        params = radius_settings.get_editor_property("params")
        setp(params, "da_vinci_rule_strength", spec["da_vinci_rule_strength"])
        setp(params, "min_radius", spec["min_radius"])
        radius_settings.set_editor_property("params", params)

        material_node, material_settings = graph.add_node_of_type(
            unreal.PVMeshBuilderMaterialDetailSettings
        )
        material_node.set_node_position(0, row + 320)
        setup = unreal.TrunkGenerationMaterialSetup()
        setp(
            setup,
            ("derive_from_trunk_texture_setup", "b_derive_from_trunk_texture_setup"),
            False,
        )
        setup.set_editor_property("material", bark)
        if spec["bark_y_scale"] is not None:
            setp(setup, "y_scale", float(spec["bark_y_scale"]))
        material_params = material_settings.get_editor_property("params")
        material_params.set_editor_property("material_setups", [setup])
        material_settings.set_editor_property("params", material_params)

        dist_node, dist_settings = graph.add_node_of_type(
            unreal.PVFoliageDistributorSettings
        )
        dist_node.set_node_position(660, row)
        dist_settings.set_editor_property(
            "mode", unreal.PVDistributionSettingsMode.PARAMETRIC_SETTINGS
        )
        parametric = dist_settings.get_editor_property("parametric_settings")

        spacing = parametric.get_editor_property("spacing_settings")
        setp(spacing, "branch_density", int(chain["branch_density"]))
        setp(
            spacing,
            "spacing_basis",
            getattr(unreal.PVDistributionBasis, chain["spacing_basis"]),
        )
        setp(spacing, "relative_start", float(chain["relative_start"]))
        setp(spacing, "relative_end", float(chain["relative_end"]))
        parametric.set_editor_property("spacing_settings", spacing)

        phyllotaxy = parametric.get_editor_property("phyllotaxy_settings")
        setp(
            phyllotaxy,
            ("reset_phyllotaxy", "b_reset_phyllotaxy"),
            bool(chain["reset_phyllotaxy"]),
        )
        setp(
            phyllotaxy,
            "phyllotaxy_type",
            getattr(unreal.PhyllotaxyType, chain["phyllotaxy_type"]),
        )
        setp(
            phyllotaxy,
            "phyllotaxy_formation",
            getattr(unreal.PhyllotaxyFormation, chain["phyllotaxy_formation"]),
        )
        # Read only under Whorled; harmless and explicit elsewhere.
        setp(phyllotaxy, "minimum_node_buds", int(chain["node_buds"]))
        setp(phyllotaxy, "maximum_node_buds", int(chain["node_buds"]))
        setp(phyllotaxy, "phyllotaxy_additional_angle", 0.0)
        setp(phyllotaxy, "phyllotaxy_offset", 0.0)
        setp(
            phyllotaxy,
            ("single_bud_tip", "b_single_bud_tip"),
            bool(chain["single_bud_tip"]),
        )
        parametric.set_editor_property("phyllotaxy_settings", phyllotaxy)

        angles = parametric.get_editor_property("angle_settings")
        setp(angles, "axil_angle", float(chain["axil_angle"]))
        setp(angles, "rotation", float(chain["rotation"]))
        setp(angles, "randomize_axil_angle_minimum", 0.0)
        setp(angles, "randomize_axil_angle_maximum", 0.0)
        axil_ramp = angles.get_editor_property("axil_angle_ramp")
        axil_ramp.import_text(chain["axil_angle_ramp"])
        setp(angles, "axil_angle_ramp", axil_ramp)
        parametric.set_editor_property("angle_settings", angles)

        scale = parametric.get_editor_property("scale_settings")
        setp(
            scale,
            "scale_ramp_basis",
            getattr(unreal.PVDistributionBasis, chain["scale_ramp_basis"]),
        )
        setp(scale, "base_scale", float(chain["base_scale"]))
        setp(scale, "branch_scale_impact", float(chain["branch_scale_impact"]))
        setp(scale, "randomize_scale_minimum", 1.0)
        setp(scale, "randomize_scale_maximum", 1.0)
        ramp = scale.get_editor_property("scale_ramp")
        ramp.import_text(chain["scale_ramp"])
        setp(scale, "scale_ramp", ramp)
        parametric.set_editor_property("scale_settings", scale)
        dist_settings.set_editor_property("parametric_settings", parametric)

        apply_vector_group(
            dist_settings, chain["aim"], "aim_vector_settings", "aim_vectors",
            unreal.PVAimVectorSettings, unreal.PVAimVectorType,
            chain["auto_align_end"],
        )
        apply_vector_group(
            dist_settings, chain["face"], "face_vector_settings", "face_vectors",
            unreal.PVFaceVectorSettings, unreal.PVFaceVectorType,
            chain["auto_align_end"],
        )

        export_node, export_settings = graph.add_node_of_type(unreal.PVExportSettings)
        export_node.set_node_position(1020, row)
        settings = export_settings.get_editor_property("export_settings")
        folder = unreal.DirectoryPath()
        folder.set_editor_property("path", spec["export_folder"])
        settings.set_editor_property("content_browser_folder", folder)
        settings.set_editor_property("mesh_name", chain["mesh_name"])
        settings.set_editor_property(
            "export_mesh_type", unreal.PVExportMeshType.SKELETAL_MESH
        )
        settings.set_editor_property(
            "create_nanite_foliage", bool(spec["create_nanite_foliage"])
        )
        settings.set_editor_property(
            "collision_generation", unreal.PVCollisionGeneration.NONE
        )
        settings.set_editor_property(
            "nanite_shape_preservation",
            getattr(
                unreal.NaniteShapePreservation, spec["nanite_shape_preservation"]
            ),
        )
        export_settings.set_editor_property("export_settings", settings)

        for src, src_pin, dst, dst_pin in (
            (import_node, "Out", mesh_node, "In"),
            (profile_node, profile_pin, mesh_node, "Profile"),
            (radius_node, "Out", mesh_node, "BranchRadius"),
            (material_node, "Out", mesh_node, "MaterialDetails"),
            (mesh_node, "Out", dist_node, "In"),
            (palette_node, "Out", dist_node, "Foliage"),
            (dist_node, "Out", export_node, "In"),
        ):
            graph.add_edge(src, src_pin, dst, dst_pin)

    edges = 0
    for node in list(graph.get_editor_property("nodes")):
        for out_pin in node.get_editor_property("output_pins"):
            try:
                edges += len(out_pin.get_editor_property("edges"))
            except Exception:
                pass
    expected = 7 * len(spec["chains"])
    eal.save_asset(full)
    status = "OK" if edges == expected else "EDGE COUNT MISMATCH"
    unreal.log(
        "[PVE] %s: %d chain(s), %d/%d edges %s"
        % (name, len(spec["chains"]), edges, expected, status)
    )
    if edges != expected:
        raise RuntimeError(
            "%s wired %d edges, expected %d" % (name, edges, expected)
        )
    return full


built = []
for graph_spec in GRAPHS:
    built.append(build(graph_spec))

unreal.log("[PVE] built %d graph(s):" % len(built))
for path in built:
    unreal.log("[PVE]   %s" % path)
unreal.log("[PVE] each graph now needs one manual Export click in the editor.")
'''


def split_by_triangles(
    chains: Sequence[TreeChainSpec],
    instances_for: Callable[[TreeChainSpec], int],
    triangles_per_instance: float,
    cap: float,
) -> list[tuple[TreeChainSpec, ...]]:
    """Bin-pack chains into graphs under a predicted-triangle cap.

    ONE EXPORT CLICK IS ONE FAILURE UNIT. The click builds every chain in its
    graph and holds the whole result in memory until it finishes, and an export
    is only durable once its package is saved -- so a click that dies takes its
    whole graph with it. An autosave crash on a beech click carrying roughly
    378 M foliage triangles destroyed nine meshes after every one of them had
    already exported and logged.

    SPLIT ON PREDICTED TRIANGLES, NOT ON CHAIN COUNT. A fir foliage instance
    averages 23,292 triangles against a beech one's 13,456, so an equal number
    of chains packs 1.7x the geometry into a fir click.

    Largest first, first fit: an oversized tree takes a bin of its own rather
    than pushing a nearly full bin over.

    Args:
        chains: Chains to pack.
        instances_for: Predicted instance count for one chain. The offline
            distributor model and the tracked calibration both supply this;
            neither is imported here, so the packing stays testable.
        triangles_per_instance: Mean triangles per placed foliage instance,
            per species.
        cap: Predicted-triangle ceiling for one graph, i.e. for one click.

    Returns:
        Groups of chains, each a graph. Order within a group is the packing
        order, not the input order.
    """
    if cap <= 0:
        raise ValueError(f"cap must be positive, got {cap}")
    if triangles_per_instance <= 0:
        raise ValueError(
            f"triangles_per_instance must be positive, got {triangles_per_instance}"
        )

    weighted = sorted(
        ((c, instances_for(c) * triangles_per_instance) for c in chains),
        key=lambda pair: -pair[1],
    )

    bins: list[list[TreeChainSpec]] = []
    loads: list[float] = []
    for chain, triangles in weighted:
        if triangles > cap:
            # Cannot be split further -- a chain is one mesh. Its own bin keeps
            # it from taking anything else down with it, but the click is still
            # over the ceiling, so say so rather than let it look packed.
            logger.warning(
                "chain %s is predicted at %.0f M triangles, over the %.0f M cap: "
                "it gets a click of its own, but that click is still oversized. "
                "Lower its density, or accept the risk knowingly",
                chain.mesh_name,
                triangles / 1e6,
                cap / 1e6,
            )
            bins.append([chain])
            loads.append(triangles)
            continue
        for i, load in enumerate(loads):
            if load + triangles <= cap:
                bins[i].append(chain)
                loads[i] = load + triangles
                break
        else:
            bins.append([chain])
            loads.append(triangles)

    for i, load in enumerate(loads):
        logger.info(
            "  graph %d: %d chain(s), %.0f M predicted triangles",
            i + 1,
            len(bins[i]),
            load / 1e6,
        )
    return [tuple(group) for group in bins]


def write_coverage_manifest(
    output_dir: Path,
    graphs: Sequence[PVEGraphSpec],
    manifest_name: str = "pve_export_manifest.json",
) -> Path:
    """List every mesh each graph is expected to export.

    Post-export consolidation (XRFF-420) otherwise has to guess what should
    exist. It also makes a lost click legible: after the autosave crash that
    destroyed nine meshes, nothing recorded what the click had been asked for.

    Densities travel with the names, because a mesh that exists is not
    necessarily a mesh built at the density intended.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / manifest_name
    payload = {
        "graphs": [
            {
                "graph_name": g.graph_name,
                "graph_asset": f"{g.graph_folder}/{g.graph_name}",
                "export_folder": g.export_folder,
                "bark_material": g.bark_material,
                "palette_meshes": list(g.palette_meshes),
                "meshes": [
                    {
                        "mesh_name": c.mesh_name,
                        "asset": f"{g.export_folder}/{c.mesh_name}",
                        "growth_json": str(Path(c.growth_json)).replace("\\", "/"),
                        "branch_density": c.distributor.branch_density,
                        "relative_start": c.distributor.relative_start,
                    }
                    for c in g.chains
                ],
            }
            for g in graphs
        ],
    }
    payload["expected_mesh_count"] = sum(len(g["meshes"]) for g in payload["graphs"])
    manifest_path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    logger.info(
        "Wrote PVE coverage manifest: %s (%d graph(s), %d mesh(es))",
        manifest_path,
        len(payload["graphs"]),
        payload["expected_mesh_count"],
    )
    return manifest_path


_RETUNE_TEMPLATE = '''\
"""GrowPy PVE density retune -- auto-generated, do not edit.

Sets branch_density on existing graphs IN PLACE. Never deletes and recreates a
graph asset: delete_asset + create_asset leaves the package pending-kill, then
get_mutable_pcg_graph() returns None on the recreated asset and the builder's
recovery renames it under a _b suffix -- which happened twice on 2026-09-11 and
left superseded graphs behind to be clicked by mistake.

    growpy-ue-exec <this file> --restart-ram-limit 0
"""

import unreal

RETUNES = {retunes}

eal = unreal.EditorAssetLibrary
PV = "/Script/ProceduralVegetation."

applied, missing = [], []

for entry in RETUNES:
    graph_path = entry["graph_asset"]
    pve = eal.load_asset(graph_path)
    if pve is None:
        missing.append("graph not found: %s" % graph_path)
        continue

    inst = unreal.new_object(
        unreal.load_class(None, PV + "ProceduralVegetationInstance"))
    gi = inst.get_editor_property("graph_instance")
    gi.set_editor_property("procedural_vegetation", pve)
    graph = gi.get_mutable_pcg_graph()
    if graph is None:
        missing.append("graph %s has no mutable PCG graph" % graph_path)
        continue

    nodes = list(graph.get_editor_property("nodes"))

    # Find each export node by the mesh name it writes, then walk its input
    # edges back to the distributor that feeds it. Matching on mesh name is
    # what makes this safe: a graph holds one chain per tree and they are
    # otherwise identical in shape.
    wanted = dict((m["mesh_name"], m["branch_density"]) for m in entry["meshes"])
    seen = set()

    for node in nodes:
        settings = node.get_settings()
        if type(settings).__name__ != "PVExportSettings":
            continue
        try:
            name = str(settings.get_editor_property("asset_name"))
        except Exception:
            continue
        if name not in wanted:
            continue

        distributor = None
        frontier, guard = [node], 0
        while frontier and distributor is None and guard < 64:
            guard += 1
            nxt = []
            for current in frontier:
                for pin in list(current.get_editor_property("input_pins") or []):
                    for edge in list(pin.get_editor_property("edges") or []):
                        other = edge.get_editor_property("input_pin")
                        upstream = other.get_editor_property("node") if other else None
                        if upstream is None:
                            continue
                        up_settings = upstream.get_settings()
                        if type(up_settings).__name__ == "PVFoliageDistributorSettings":
                            distributor = up_settings
                            break
                        nxt.append(upstream)
                    if distributor is not None:
                        break
                if distributor is not None:
                    break
            frontier = nxt

        if distributor is None:
            missing.append("no distributor upstream of %s" % name)
            continue

        parametric = distributor.get_editor_property("parametric_settings")
        spacing = parametric.get_editor_property("spacing_settings")
        before = spacing.get_editor_property("branch_density")
        spacing.set_editor_property("branch_density", int(wanted[name]))
        after = spacing.get_editor_property("branch_density")
        if int(after) != int(wanted[name]):
            missing.append("%s density did not take: wanted %s, read %s"
                           % (name, wanted[name], after))
            continue
        applied.append("%s %s -> %s" % (name, before, after))
        seen.add(name)

    for name in wanted:
        if name not in seen:
            missing.append("no export node named %s in %s" % (name, graph_path))

    eal.save_asset(graph_path, only_if_is_dirty=False)

print("")
for line in applied:
    print("retuned: %s" % line)
for line in missing:
    print("FAIL: %s" % line)
if missing:
    raise RuntimeError("%d retune problem(s) -- see above" % len(missing))
print("OK: retuned %d chain(s) in place" % len(applied))
'''


def generate_pve_retune_script(
    output_dir: Path,
    graphs: Sequence[PVEGraphSpec],
    script_name: str = "growpy_pve_retune.py",
) -> Path:
    """Write a UE script that sets densities on existing graphs, in place.

    Use this rather than re-authoring a graph whenever only a density changed.
    Re-authoring means deleting the asset, and a deleted-then-recreated PVE
    graph comes back with ``get_mutable_pcg_graph() == None``; the builder then
    retries under a ``_b`` suffix and leaves the superseded graph behind to be
    clicked by mistake.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = output_dir / script_name
    retunes = [
        {
            "graph_asset": f"{g.graph_folder}/{g.graph_name}",
            "meshes": [
                {
                    "mesh_name": c.mesh_name,
                    "branch_density": c.distributor.branch_density,
                }
                for c in g.chains
            ],
        }
        for g in graphs
    ]
    script_path.write_text(
        _RETUNE_TEMPLATE.format(retunes=retunes), encoding="utf-8"
    )
    logger.info(
        "Generated PVE retune script: %s (%d graph(s), %d chain(s))",
        script_path,
        len(graphs),
        sum(len(g.chains) for g in graphs),
    )
    return script_path


def generate_pve_graph_builder_script(
    output_dir: Path,
    graphs: list[PVEGraphSpec],
    script_name: str = "growpy_pve_graphs.py",
) -> Path:
    """Write a UE Python script that authors ``graphs`` in the open editor.

    Args:
        output_dir: Directory to write the script into; created if absent.
        graphs: Graph specifications, one asset each.
        script_name: File name for the generated script.

    Returns:
        Path to the written script, ready for ``growpy-ue-exec``.

    Raises:
        ValueError: If ``graphs`` is empty or two graphs share a name.
    """
    if not graphs:
        raise ValueError("no graphs to build")
    names = [g.graph_name for g in graphs]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise ValueError(f"duplicate graph names: {sorted(dupes)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = output_dir / script_name
    payload = [_graph_payload(g) for g in graphs]
    script_path.write_text(_SCRIPT_TEMPLATE.format(graphs=payload), encoding="utf-8")
    logger.info(
        "Generated PVE graph builder script: %s (%d graph(s), %d chain(s))",
        script_path,
        len(graphs),
        sum(len(g.chains) for g in graphs),
    )
    return script_path
