"""Import the Content Browser assets a PVE graph needs, from growpy.

A PVE graph cannot build a tree until three things exist in the project: the
**growth JSON** (emitted by the pipeline -- see
:func:`growpy.pipelines.forest_stages.export_growth_json_only`), the **twig
prototypes as UE static meshes** for the foliage palette, and a **bark material
instance** for the trunk. This module owns the second and third, which were
done by hand until XRFF-440, and the **foliage material** the palette's leaves
render with (2026-09-25).

WHY THIS HAS AN OWNER NOW
-------------------------

An unowned step rots quietly. ``MI_european_beech_bark`` was never a material at
all -- it was a USD import stub parented to ``/USDCore/Materials/
UsdPreviewSurface`` with both texture parameters ``None``. Every beech trunk
exported on the PVE route rendered untextured for weeks, with its textures
sitting in the adjacent folder the whole time, and nobody noticed until a tree
was looked at closely. The fir equivalent had been repaired by hand in an
earlier session; beech never was.

THREE TRAPS, ALL PAID FOR ALREADY
---------------------------------

* **Virtual-texture streaming must be ON before the material points at the
  texture.** ``MA_Foliage_Trees`` samples virtual textures. A non-VT texture on
  it renders as a shifting magenta/violet and logs ``expects texture``, so
  reparenting alone would have replaced an untextured beech trunk with a
  magenta one. The generated script sets VT and saves the texture in a pass
  that completes before any material is touched.

* **Clone a known-good instance; never factory-create, and never parent to the**
  ``/Game/Templates`` **copy of** ``MA_Foliage_Trees``. Both have produced
  broken materials before. :class:`PVEAssetPlan` rejects a master under
  ``/Game/Templates`` outright, and the generated script duplicates a working
  sample instance rather than running the factory.

* **Verify by read-back.** The script re-loads every asset it wrote and asserts
  parent, both texture parameters and both VT flags, then fails loudly. A write
  that silently did not take is the failure mode this whole module exists to
  prevent.

* **PVE places a part with mesh +Z as the growth axis and +Y as the leaf
  face** (``FFoliageFacade::GetFoliageTransform`` is ``MakeFromYZ(Normal, Up)``),
  and growpy authors every twig with the shoot on **+X** and the face on Z --
  the frame its own PointInstancer route rotates. Handing the imported mesh to
  PVE unchanged put the twig's length on the sideways axis and its face on the
  growth axis, so no distributor setting could ever pose it (XRFF-438, measured
  2026-09-14). The generated script therefore re-authors each imported prototype
  into a ``SM_<name>_ZUP`` part (X->Z, Z->Y, Y->X, a proper rotation) and the
  palette a graph receives names the parts, never the imports. The shared
  ``*_twigs_combined_skeletal`` assets are untouched (XRFF-445). The guard
  refuses a source whose origin is not at the -X end, so a prototype authored in
  some other frame fails the import instead of being rotated into nonsense.

The script is idempotent: an existing correct material is left alone, an
existing wrong one is repaired **in place** (exported meshes reference it by
path, so a repair reaches every tree already exported without a re-export), and
a missing one is cloned.

THE LEAVES WERE NOBODY'S
------------------------

The twig prototypes import with the USD importer's ``UsdPreviewSurface``
materials, and those cannot see ``MPC_GlobalFoliageActor``: season, health and
the foliage actor's colour never reached a leaf, on the old ``/Game/PVE``
catalog as much as on the new one (found 2026-09-25). Each species now gets
``MI_<species>_foliage`` -- cloned from the plugin's own conifer or broadleaf
foliage sample, fed the two maps ``growpy-pack-pve-textures`` packs (Base Color
with opacity in alpha; Normal with translucency in alpha, imported as Masks, as
the samples do) -- and every ``*_leaf*`` instance in its palette is re-parented
to it in place, so the trees already exported follow without a re-export.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_CLONE_SOURCES",
    "DEFAULT_MASTER_MATERIAL",
    "PalettePrototype",
    "PVEAssetPlan",
    "SpeciesAssetSpec",
    "build_species_asset_spec",
    "generate_pve_asset_script",
    "FOLIAGE_SAMPLES",
]

# Shipped by the Procedural Vegetation Editor plugin. The /Game/Templates copy
# of the same material is NOT interchangeable -- parenting to it has produced
# broken materials -- so PVEAssetPlan refuses it.
DEFAULT_MASTER_MATERIAL = (
    "/ProceduralVegetationEditor/SampleAssets/Materials/MasterMaterials"
    "/MA_Foliage_Trees"
)

# Known-good bark instances to duplicate when a species has none. Tried in
# order; the script asserts the one it picks is parented to the master before
# cloning it, so a wrong entry is skipped rather than propagated.
#
# These are the plugin's own StarterContent trees, verified present in a live
# UE 5.8 project on 2026-09-14. Earlier guesses at Tree_European_Beech_01 /
# Tree_Norway_Spruce_01 paths do not exist -- the samples live under
# StarterContent/, and the run failed loudly rather than silently
# factory-creating a broken material.
DEFAULT_CLONE_SOURCES = (
    "/ProceduralVegetationEditor/SampleAssets/StarterContent/DeciduousTree_01"
    "/Materials/MI_LeafTree_01_Bark",
    "/ProceduralVegetationEditor/SampleAssets/StarterContent/ConiferTree_01"
    "/Materials/MI_Conifer_Bark_01",
    "/ProceduralVegetationEditor/SampleAssets/StarterContent/DeciduousTree_01"
    "/Materials/MI_PVE_Tree_01_Bark",
    "/ProceduralVegetationEditor/SampleAssets/StarterContent/ConiferTree_01"
    "/Materials/MI_PVE_ConiferTree_01_Bark",
)

_FORBIDDEN_MASTER_PREFIX = "/Game/Templates"

# The plugin's own foliage instances, one per growth habit, cloned as the base of
# a species' foliage material. Read off the live project on 2026-09-25: both are
# parented to MA_Foliage_Trees with Seasons on; the conifer one also takes
# health into roughness, the broadleaf one tints the leaf backside.
FOLIAGE_SAMPLES = {
    "conifer": "/ProceduralVegetationEditor/SampleAssets/StarterContent/"
    "ConiferTree_01/Materials/MI_Conifer_Foliage_01",
    "broadleaf": "/ProceduralVegetationEditor/SampleAssets/StarterContent/"
    "DeciduousTree_01/Materials/MI_LeafTree_01_Foliage",
}

# Which prototype set a species' palette is built from. "twigs" = the per-object
# twig prototypes growpy-convert-twigs writes under data/assets/twigs/ (a spray
# or a leaf cluster each); "compound" = branch parts baked from a Grove tree of
# the species with its twigs welded on (data/assets/compound_parts/
# <species>_pve_palette.json), the MegaPlants unit -- XRFF-463.
PALETTE_SOURCES = ("twigs", "compound")


@dataclass(frozen=True)
class PalettePrototype:
    """One twig prototype: a ``*_static.usda`` in, one static mesh out."""

    name: str
    source: Path

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("prototype name must not be empty")

    def mesh_path(self, foliage_folder: str) -> str:
        """Where the USD import lands this prototype's static mesh.

        A USD import writes ``<destination>/<name>/StaticMeshes/SM_<name>``;
        the nesting comes from the importer, not from us.
        """
        return f"{foliage_folder}/{self.name}/StaticMeshes/SM_{self.name}"

    def part_path(self, foliage_folder: str) -> str:
        """The re-framed copy PVE actually instances (see the module docstring).

        Written by the generated script next to the import, under the same
        ``StaticMeshes`` folder, so a re-import replaces both together.
        """
        return f"{self.mesh_path(foliage_folder)}_ZUP"


@dataclass(frozen=True)
class SpeciesAssetSpec:
    """Everything one species needs in the Content Browser."""

    species: str
    content_folder: str
    prototypes: tuple[PalettePrototype, ...]
    bark_color: Path
    bark_normal: Path
    materials_folder: str = ""
    # The packed leaf maps (growpy-pack-pve-textures). None leaves the palette's
    # leaves on their USD import materials, which the generated script reports.
    foliage_color: Path | None = None
    foliage_normal: Path | None = None
    foliage_params: Path | None = None
    habit: str = "broadleaf"

    def __post_init__(self) -> None:
        if not self.prototypes:
            raise ValueError(
                f"species {self.species!r} has no twig prototypes -- a foliage "
                f"palette cannot be empty"
            )
        names = [p.name for p in self.prototypes]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(
                f"species {self.species!r} has duplicate prototypes {sorted(dupes)}"
            )
        if not self.content_folder.startswith("/"):
            raise ValueError(
                f"content_folder must be a UE package path, got "
                f"{self.content_folder!r}"
            )
        if not self.materials_folder:
            # Keeps a hand-built spec self-consistent: bark beside the palette,
            # as it sat before the type-sorted layout split the two apart.
            object.__setattr__(
                self, "materials_folder", f"{self.content_folder}/Bark"
            )
        if self.habit not in FOLIAGE_SAMPLES:
            raise ValueError(
                f"habit must be one of {sorted(FOLIAGE_SAMPLES)}, got {self.habit!r}"
            )
        if (self.foliage_color is None) != (self.foliage_normal is None):
            raise ValueError(
                f"{self.species!r}: the foliage Base Color and Normal come as a "
                f"pair -- one alone would leave the sample's own map in the other"
            )

    @property
    def foliage_folder(self) -> str:
        """Where the palette prototypes live.

        The species folder under ``Foliage/`` IS the palette -- assets are
        sorted by type, not by the pipeline that produced them, so there is no
        second ``/Foliage`` level inside it.
        """
        return self.content_folder

    @property
    def bark_folder(self) -> str:
        """Where the bark textures and the bark material instance live.

        Under ``Materials/<species>/`` -- a material is a material wherever it
        came from, and the palette folder holds meshes.
        """
        return self.materials_folder

    @property
    def bark_material(self) -> str:
        return f"{self.bark_folder}/MI_{self.species}_bark"

    @property
    def foliage_material(self) -> str:
        """The species' leaf material, the parent of every palette leaf instance."""
        return f"{self.materials_folder}/MI_{self.species}_foliage"

    @property
    def palette_meshes(self) -> tuple[str, ...]:
        """Palette mesh paths, in prototype order -- the re-framed PARTS.

        This is the list a :class:`~growpy.io.unreal.pve_graph_builder.
        PVEGraphSpec` takes, so the graph and the import cannot disagree about
        where a prototype lives, nor about which of the two meshes per
        prototype is the one in PVE's frame.
        """
        return tuple(p.part_path(self.foliage_folder) for p in self.prototypes)


@dataclass(frozen=True)
class PVEAssetPlan:
    """One asset-import run: every species, plus the material sources."""

    species: tuple[SpeciesAssetSpec, ...]
    master_material: str = DEFAULT_MASTER_MATERIAL
    clone_sources: tuple[str, ...] = DEFAULT_CLONE_SOURCES

    def __post_init__(self) -> None:
        if not self.species:
            raise ValueError("no species to import")
        if self.master_material.startswith(_FORBIDDEN_MASTER_PREFIX):
            raise ValueError(
                f"refusing to parent bark materials to {self.master_material!r}: "
                f"the {_FORBIDDEN_MASTER_PREFIX} copy of MA_Foliage_Trees has "
                f"produced broken materials. Use the plugin's own copy "
                f"({DEFAULT_MASTER_MATERIAL})"
            )
        if not self.clone_sources:
            raise ValueError(
                "no clone sources -- a species with no existing bark material "
                "needs a known-good instance to duplicate, and factory-creating "
                "one has produced broken materials"
            )
        folders = [s.content_folder for s in self.species]
        dupes = {f for f in folders if folders.count(f) > 1}
        if dupes:
            raise ValueError(
                f"two species share a content folder {sorted(dupes)} -- their "
                f"bark materials and palettes would collide"
            )


def camel_species(species: str) -> str:
    """``common_ash`` -> ``CommonAsh``, for ASSET names only.

    Folders stay in the pipeline's own lowercase spelling, because the material
    and texture batches key a species off the folder-name string and match it
    against the lowercase keys in ``config/tree_asset_lookup.csv``. Asset names
    are never looked up that way, so they keep the UE-idiomatic spelling.
    """
    return "".join(part.capitalize() for part in species.split("_") if part)


def _compound_prototypes(species: str) -> tuple[PalettePrototype, ...]:
    """The baked compound parts of ``species``, in manifest order.

    The manifest is what the bake wrote (name, file, welded twigs, leaf area);
    the part USDs sit beside it, authored in growpy's twig frame (base at the
    origin, axis +X) so the same re-frame applies to them.
    """
    from growpy.config.paths import get_assets_directory

    manifest = get_assets_directory() / "compound_parts" / f"{species}_pve_palette.json"
    if not manifest.is_file():
        raise FileNotFoundError(
            f"no compound palette for {species!r} at {manifest} -- bake one "
            f"(tools/harvest_compound_parts.py) before asking for palette = "
            f"'compound'"
        )
    data = json.loads(manifest.read_text(encoding="utf-8"))
    prototypes = []
    for entry in data.get("prototypes", []):
        source = Path(entry["file"])
        if not source.is_absolute():
            source = manifest.parent / source.name
        if not source.is_file():
            raise FileNotFoundError(
                f"{species!r} compound part {entry.get('name')!r} named by "
                f"{manifest.name} is missing at {source}"
            )
        prototypes.append(PalettePrototype(name=str(entry["name"]), source=source))
    return tuple(prototypes)


def build_species_asset_spec(
    species: str,
    content_root: str = "/Game/Assets/Trees",
    folder_name: str | None = None,
    palette: str = "twigs",
) -> SpeciesAssetSpec:
    """Resolve one species' palette and bark sources from disk.

    Prototype count is discovered, never hardcoded -- beech ships 5 and fir 8.
    Twig directory and bark texture both resolve through
    ``config/tree_asset_lookup.csv``, so a species whose twig is another
    species' (Norway spruce uses the fir's) resolves to the right files.
    ``palette`` picks the prototype set (see :data:`PALETTE_SOURCES`).

    Raises:
        FileNotFoundError: If the twig prototypes, either bark texture or the
            packed foliage maps are missing. Silence here would mean an empty
            palette, an untextured trunk or leaves no season reaches,
            discovered only by looking at a tree.
    """
    from growpy.config.paths import (
        get_bark_normal_texture_path,
        get_bark_texture_path,
        get_species_growth_habit,
        get_twig_files_by_type,
    )

    if palette not in PALETTE_SOURCES:
        raise ValueError(f"palette must be one of {PALETTE_SOURCES}, got {palette!r}")
    if palette == "compound":
        prototypes = _compound_prototypes(species)
    else:
        by_type = get_twig_files_by_type(species)
        prototypes = tuple(
            PalettePrototype(name=stem[: -len("_static")], source=paths[0])
            for stem, paths in sorted(by_type.items())
            if stem.endswith("_static") and paths
        )
    if not prototypes:
        raise FileNotFoundError(
            f"no *_static.usda twig prototypes found for {species!r} -- run "
            f"growpy-convert-twigs first"
        )

    color = get_bark_texture_path(species)
    normal = get_bark_normal_texture_path(species)
    missing = [
        label
        for label, path in (("bark", color), ("bark normal", normal))
        if path is None
    ]
    if missing:
        raise FileNotFoundError(
            f"{species!r} is missing its {' and '.join(missing)} texture; "
            f"MA_Foliage_Trees needs both, and a material with either unset "
            f"renders untextured"
        )

    foliage_color, foliage_normal, foliage_params = _foliage_textures(species)

    return SpeciesAssetSpec(
        species=species,
        content_folder=f"{content_root}/Foliage/{folder_name or species}",
        prototypes=prototypes,
        bark_color=color,
        bark_normal=normal,
        materials_folder=f"{content_root}/Materials/{folder_name or species}",
        foliage_color=foliage_color,
        foliage_normal=foliage_normal,
        foliage_params=foliage_params,
        habit=get_species_growth_habit(species) or "broadleaf",
    )


def _foliage_textures(species: str) -> tuple[Path, Path, Path | None]:
    """The packed leaf maps of the species' twig, and its colour parameters.

    ``growpy-pack-pve-textures`` writes them into the twig's own ``textures/``
    folder as ``<twig>_pve_basecolor.png``, ``_pve_normal.png`` and, where the
    twig has a leaf underside or an autumn map, ``_pve_params.json``.

    Raises:
        FileNotFoundError: If either map is missing. Without them the palette's
            leaves keep the USD import's material, which season and health
            cannot reach -- a failure nobody sees until the season changes.
    """
    from growpy.config.paths import get_twig_files_by_type

    files = [p for paths in get_twig_files_by_type(species).values() for p in paths]
    if not files:
        raise FileNotFoundError(f"no twig directory resolves for {species!r}")
    twig_dir = files[0].parent
    textures = twig_dir / "textures"
    color = textures / f"{twig_dir.name}_pve_basecolor.png"
    normal = textures / f"{twig_dir.name}_pve_normal.png"
    params = textures / f"{twig_dir.name}_pve_params.json"
    missing = [p.name for p in (color, normal) if not p.is_file()]
    if missing:
        raise FileNotFoundError(
            f"{species!r} has no packed foliage maps ({', '.join(missing)}) -- run "
            f"growpy-pack-pve-textures; without them its leaves keep the USD "
            f"import's material, which season and health cannot reach"
        )
    return color, normal, params if params.is_file() else None


def _plan_payload(plan: PVEAssetPlan) -> dict:
    return {
        "master_material": plan.master_material,
        "clone_sources": list(plan.clone_sources),
        "species": [
            {
                "species": s.species,
                "foliage_folder": s.foliage_folder,
                "bark_folder": s.bark_folder,
                "bark_material": s.bark_material,
                "content_folder": s.content_folder,
                "prototypes": [
                    {
                        "name": p.name,
                        "source": str(Path(p.source).resolve()).replace("\\", "/"),
                        "mesh": p.mesh_path(s.foliage_folder),
                        "part": p.part_path(s.foliage_folder),
                    }
                    for p in s.prototypes
                ],
                "bark_color": {
                    "source": str(Path(s.bark_color).resolve()).replace("\\", "/"),
                    "name": Path(s.bark_color).stem,
                    "asset": f"{s.bark_folder}/{Path(s.bark_color).stem}",
                },
                "bark_normal": {
                    "source": str(Path(s.bark_normal).resolve()).replace("\\", "/"),
                    "name": Path(s.bark_normal).stem,
                    "asset": f"{s.bark_folder}/{Path(s.bark_normal).stem}",
                },
                "foliage": _foliage_payload(s),
            }
            for s in plan.species
        ],
    }


def _foliage_payload(s: SpeciesAssetSpec) -> dict | None:
    """The leaf material, its sample, its two maps and its colour parameters."""
    if s.foliage_color is None or s.foliage_normal is None:
        return None
    params = {}
    if s.foliage_params is not None and Path(s.foliage_params).is_file():
        params = json.loads(Path(s.foliage_params).read_text(encoding="utf-8"))

    def texture(path: Path) -> dict:
        return {
            "source": str(Path(path).resolve()).replace("\\", "/"),
            "name": Path(path).stem,
            "asset": f"{s.materials_folder}/{Path(path).stem}",
        }

    return {
        "material": s.foliage_material,
        "sample": FOLIAGE_SAMPLES[s.habit],
        "color": texture(s.foliage_color),
        "normal": texture(s.foliage_normal),
        "params": params,
    }


_SCRIPT_TEMPLATE = '''\
"""GrowPy PVE asset import -- auto-generated, do not edit.

Imports the twig palette and builds the bark and foliage materials for each
species, then verifies every write by reading it back. Run with:

    growpy-ue-exec <this file> --restart-ram-limit 0
"""

import unreal

PLAN = {plan}

eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()

USD_STUB = "UsdPreviewSurface"
failures = []


def _path_of(asset):
    return asset.get_path_name().split(".")[0] if asset is not None else None


def _import(source, folder, name):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", source)
    task.set_editor_property("destination_path", folder)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    tools.import_asset_tasks([task])
    return list(task.get_editor_property("imported_object_paths") or [])


def _bounds(mesh):
    box = mesh.get_bounds()
    o, e = box.origin, box.box_extent
    return (o.x - e.x, o.y - e.y, o.z - e.z, o.x + e.x, o.y + e.y, o.z + e.z)


# growpy authoring frame -> PVE part frame: X->Z, Z->Y, Y->X. A 120 degree turn
# about (1,1,1); a proper rotation, so no face is mirrored.
_REFRAME = unreal.Quat(-0.5, -0.5, -0.5, 0.5)


def reframe_prototype(mesh_path, part_path):
    """Author the PVE part from the imported mesh. Returns a problem or None."""
    src = eal.load_asset(mesh_path)
    if src is None:
        return "cannot re-frame, import missing: %s" % mesh_path
    x0, y0, z0, x1, y1, z1 = _bounds(src)
    # growpy puts the attachment at the origin and the shoot along +X; a
    # broadleaf's spread may exceed its length, so only the origin is checked.
    # An apical rosette (ash: leaves spread around the bud, X extent no longer
    # than Y/Z) keeps its origin INSIDE the mesh in growpy's own frame, so only
    # a shoot-shaped mesh with its origin away from the -X end is refused.
    length = x1 - x0
    end_anchored = x0 > -0.35 * length
    rosette = length < 1.5 * max(y1 - y0, z1 - z0)
    if not end_anchored and not rosette:
        return ("refusing to re-frame %s: origin is not at the -X end "
                "(X %.2f..%.2f) -- not growpy's authoring frame" % (mesh_path, x0, x1))
    if not end_anchored:
        print("   rosette prototype (origin inside the mesh), re-framed as is: %s"
              % mesh_path)
    dyn = unreal.DynamicMesh()
    lod = unreal.GeometryScriptMeshReadLOD()
    lod.set_editor_property("lod_type", unreal.GeometryScriptLODType.SOURCE_MODEL)
    lod.set_editor_property("lod_index", 0)
    unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(
        src, dyn, unreal.GeometryScriptCopyMeshFromAssetOptions(), lod)
    unreal.GeometryScript_MeshTransforms.transform_mesh(
        dyn,
        unreal.Transform(
            unreal.Vector(0, 0, 0), _REFRAME.rotator(), unreal.Vector(1, 1, 1)),
        True,
    )
    opts = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
    opts.set_editor_property("enable_recompute_normals", False)
    opts.set_editor_property("enable_recompute_tangents", False)
    opts.set_editor_property("enable_nanite", False)
    result = unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(
        dyn, part_path, opts, None)
    part = result[0] if isinstance(result, tuple) else result
    if part is None:
        return "re-frame produced no asset: %s" % part_path
    # The new asset carries no materials; take the import's slots verbatim.
    part.set_editor_property(
        "static_materials", list(src.get_editor_property("static_materials")))
    eal.save_asset(part_path, only_if_is_dirty=False)
    # Read back: the shoot must now run along +Z from the origin (a rosette
    # only has to keep its length).
    px0, py0, pz0, px1, py1, pz1 = _bounds(eal.load_asset(part_path))
    length_kept = abs((pz1 - pz0) - length) < 0.01 * length + 0.01
    anchored = pz0 > -0.35 * (pz1 - pz0) or not end_anchored
    if not (anchored and length_kept):
        return ("re-framed part has the wrong extents: %s Z %.2f..%.2f"
                % (part_path, pz0, pz1))
    return None


def import_palette(spec):
    """Import every *_static.usda prototype not already present, then author
    its PVE part. Returns the problems found."""
    problems = []
    for proto in spec["prototypes"]:
        if eal.does_asset_exist(proto["mesh"]):
            print("   palette exists: %s" % proto["name"])
        else:
            print("   importing %s" % proto["name"])
            _import(proto["source"], spec["foliage_folder"], proto["name"])
            if not eal.does_asset_exist(proto["mesh"]):
                problems.append("palette mesh missing after import: %s" % proto["mesh"])
                continue
        if eal.does_asset_exist(proto["part"]):
            continue
        print("   re-framing %s -> %s"
              % (proto["name"], proto["part"].rsplit("/", 1)[-1]))
        problem = reframe_prototype(proto["mesh"], proto["part"])
        if problem:
            problems.append(problem)
        elif not eal.does_asset_exist(proto["part"]):
            problems.append("palette part missing after re-frame: %s" % proto["part"])
    return problems


def import_bark_texture(entry, is_normal):
    """Import one bark texture and force virtual-texture streaming ON.

    MA_Foliage_Trees samples VIRTUAL textures. A non-VT texture on it renders
    as a shifting magenta/violet and logs "expects texture", so this must
    complete before any material points at the texture.
    """
    if not eal.does_asset_exist(entry["asset"]):
        print("   importing texture %s" % entry["name"])
        _import(entry["source"], entry["asset"].rsplit("/", 1)[0], entry["name"])

    tex = eal.load_asset(entry["asset"])
    if tex is None:
        return "texture missing after import: %s" % entry["asset"]

    if is_normal:
        tex.set_editor_property(
            "compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        tex.set_editor_property("srgb", False)
    if not tex.get_editor_property("virtual_texture_streaming"):
        tex.set_editor_property("virtual_texture_streaming", True)
        print("   VT enabled: %s" % entry["name"])
    eal.save_asset(entry["asset"], only_if_is_dirty=False)

    if not eal.load_asset(entry["asset"]).get_editor_property(
            "virtual_texture_streaming"):
        return "virtual_texture_streaming did not stick: %s" % entry["asset"]
    return None


def resolve_clone_source(master):
    """A known-good instance to duplicate, verified parented to the master.

    Factory-creating a MaterialInstanceConstant has produced broken materials,
    so a species with no bark material clones one that works instead.
    """
    for path in PLAN["clone_sources"]:
        src = eal.load_asset(path)
        if src is None:
            continue
        parent = _path_of(src.get_editor_property("parent"))
        if parent == master:
            return path
        print("   clone candidate %s has parent %s, skipping" % (path, parent))
    return None


def build_bark_material(spec, master):
    """Create, repair or leave alone one species' bark material.

    Repaired IN PLACE rather than replaced: exported meshes reference the
    material by path, so every tree already exported picks a fix up with no
    re-export.
    """
    mi_path = spec["bark_material"]
    color = spec["bark_color"]["asset"]
    normal = spec["bark_normal"]["asset"]

    if not eal.does_asset_exist(mi_path):
        source = resolve_clone_source(master)
        if source is None:
            return ["no known-good bark instance to clone for %s" % spec["species"]]
        print("   cloning %s -> %s" % (source, mi_path))
        if eal.duplicate_asset(source, mi_path) is None:
            return ["duplicate_asset failed: %s -> %s" % (source, mi_path)]

    mi = eal.load_asset(mi_path)
    master_asset = eal.load_asset(master)
    if mi is None or master_asset is None:
        return ["material or master missing: %s / %s" % (mi_path, master)]

    before = _path_of(mi.get_editor_property("parent"))
    if before != master:
        print("   reparenting %s (was %s)" % (spec["species"], before))
        mi.set_editor_property("parent", master_asset)

    mel.set_material_instance_texture_parameter_value(
        mi, "Base Color", eal.load_asset(color))
    mel.set_material_instance_texture_parameter_value(
        mi, "Normal", eal.load_asset(normal))
    mel.update_material_instance(mi)
    eal.save_asset(mi_path, only_if_is_dirty=False)

    # Read back. A write that silently did not take is the failure this whole
    # step exists to prevent.
    check = eal.load_asset(mi_path)
    problems = []
    parent = _path_of(check.get_editor_property("parent"))
    if parent != master:
        problems.append("%s parent is %s, expected %s" % (mi_path, parent, master))
    for param, want in (("Base Color", color), ("Normal", normal)):
        got = _path_of(
            mel.get_material_instance_texture_parameter_value(check, param))
        if got != want:
            problems.append("%s %s is %s, expected %s" % (mi_path, param, got, want))
    return problems


def audit_for_usd_stubs(folder):
    """Flag any material instance still parented to the USD import stub.

    This is the specific failure that went unnoticed for weeks, so it gets an
    explicit sweep rather than relying on someone looking at a tree.
    """
    stubs = []
    if not eal.does_directory_exist(folder):
        return stubs
    for listed in eal.list_assets(folder, recursive=True, include_folder=False):
        path = str(listed).split(".")[0]
        asset = eal.load_asset(path)
        if not isinstance(asset, unreal.MaterialInstanceConstant):
            continue
        parent = _path_of(asset.get_editor_property("parent"))
        if parent and USD_STUB in parent:
            stubs.append("%s is still parented to %s" % (path, parent))
    return stubs


def import_foliage_texture(entry, is_normal):
    """Import one packed leaf map with the settings the plugin's own foliage
    samples use: Base Color sRGB, Normal (normal + translucency in alpha) as
    Masks with sRGB off -- normal-map compression would drop the translucency --
    and both virtual-texture streamed.

    Always re-imported, so a re-pack on disk reaches the project.
    """
    print("   importing texture %s" % entry["name"])
    _import(entry["source"], entry["asset"].rsplit("/", 1)[0], entry["name"])
    tex = eal.load_asset(entry["asset"])
    if tex is None:
        return "texture missing after import: %s" % entry["asset"]
    tcs = unreal.TextureCompressionSettings
    tex.set_editor_property(
        "compression_settings", tcs.TC_MASKS if is_normal else tcs.TC_DEFAULT)
    tex.set_editor_property("srgb", not is_normal)
    tex.set_editor_property("virtual_texture_streaming", True)
    eal.save_asset(entry["asset"], only_if_is_dirty=False)
    if not eal.load_asset(entry["asset"]).get_editor_property(
            "virtual_texture_streaming"):
        return "virtual_texture_streaming did not stick: %s" % entry["asset"]
    return None


def build_foliage_material(spec, master):
    """Create or repair the species' leaf material, cloned from the plugin's
    foliage sample for its habit so the season and health switches come as
    Epic set them."""
    fol = spec["foliage"]
    mi_path = fol["material"]
    if not eal.does_asset_exist(mi_path):
        sample = eal.load_asset(fol["sample"])
        if sample is None or _path_of(sample.get_editor_property("parent")) != master:
            return ["foliage sample %s is missing or not parented to %s"
                    % (fol["sample"], master)]
        print("   cloning %s -> %s" % (fol["sample"], mi_path))
        if eal.duplicate_asset(fol["sample"], mi_path) is None:
            return ["duplicate_asset failed: %s -> %s" % (fol["sample"], mi_path)]

    mi = eal.load_asset(mi_path)
    if _path_of(mi.get_editor_property("parent")) != master:
        mi.set_editor_property("parent", eal.load_asset(master))
    mel.set_material_instance_texture_parameter_value(
        mi, "Base Color", eal.load_asset(fol["color"]["asset"]))
    mel.set_material_instance_texture_parameter_value(
        mi, "Normal", eal.load_asset(fol["normal"]["asset"]))
    # Colours the master has no texture slot for (leaf underside, autumn),
    # measured off the twig's own maps by growpy-pack-pve-textures.
    for name, value in sorted(fol["params"].items()):
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            rgba = (list(value) + [1.0])[:4]
            mel.set_material_instance_vector_parameter_value(
                mi, name, unreal.LinearColor(*rgba))
        elif isinstance(value, (int, float)):
            mel.set_material_instance_scalar_parameter_value(mi, name, float(value))
    mel.update_material_instance(mi)
    eal.save_asset(mi_path, only_if_is_dirty=False)

    check = eal.load_asset(mi_path)
    problems = []
    parent = _path_of(check.get_editor_property("parent"))
    if parent != master:
        problems.append("%s parent is %s, expected %s" % (mi_path, parent, master))
    for param, want in (("Base Color", fol["color"]["asset"]),
                        ("Normal", fol["normal"]["asset"])):
        got = _path_of(
            mel.get_material_instance_texture_parameter_value(check, param))
        if got != want:
            problems.append("%s %s is %s, expected %s" % (mi_path, param, got, want))
    if not mel.get_material_instance_static_switch_parameter_value(check, "Seasons"):
        problems.append("%s has Seasons off: the foliage actor's season would "
                        "not reach it" % mi_path)
    return problems


def repoint_leaf_materials(spec):
    """Re-parent every *_leaf* instance in the species' palette to its leaf
    material, IN PLACE.

    The USD import gives each prototype its own leaf instances, parented to
    UsdPreviewSurface, and the exported trees reference exactly those by path.
    Re-parenting them (overrides cleared, so they inherit everything) reaches
    every tree already exported without a re-export. A leaf is found by name:
    growpy's twig converter names the leaf material "leaf" and the shoot's
    "bark", and the shoot keeps its own atlas.
    """
    want = spec["foliage"]["material"]
    parent = eal.load_asset(want)
    problems = []
    seen = moved = 0
    for proto in spec["prototypes"]:
        folder = "%s/%s/Materials" % (spec["foliage_folder"], proto["name"])
        if not eal.does_directory_exist(folder):
            problems.append("palette materials folder missing: %s" % folder)
            continue
        for listed in eal.list_assets(folder, recursive=False, include_folder=False):
            path = str(listed).split(".")[0]
            if "_leaf" not in path.rsplit("/", 1)[1]:
                continue
            mi = eal.load_asset(path)
            if not isinstance(mi, unreal.MaterialInstanceConstant):
                continue
            seen += 1
            if _path_of(mi.get_editor_property("parent")) == want:
                continue
            mel.clear_all_material_instance_parameters(mi)
            mi.set_editor_property(
                "base_property_overrides",
                unreal.MaterialInstanceBasePropertyOverrides())
            mi.set_editor_property("parent", parent)
            mel.update_material_instance(mi)
            eal.save_asset(path, only_if_is_dirty=False)
            moved += 1
            if _path_of(eal.load_asset(path).get_editor_property("parent")) != want:
                problems.append("%s did not take its new parent %s" % (path, want))
    if seen == 0:
        problems.append("no *_leaf* material in the palette of %s" % spec["species"])
    print("   leaves: %d leaf material(s), %d re-parented to %s"
          % (seen, moved, want.rsplit("/", 1)[1]))
    return problems


def trees_in_open_level():
    """Skinned-mesh components in the open level showing a tree of this content.

    Re-parenting a leaf material refreshes every tree that shows it; with a
    gallery level open that overflowed the GPU-scene scatter buffer and took
    the editor down while the new material instance was saved (2026-09-25).
    """
    roots = sorted(set(s["content_folder"].rsplit("/Foliage/", 1)[0] + "/"
                       for s in PLAN["species"]))
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    found = 0
    for actor in actors.get_all_level_actors():
        for comp in actor.get_components_by_class(unreal.SkinnedMeshComponent):
            asset = comp.get_skinned_asset()
            if asset is not None and asset.get_path_name().startswith(tuple(roots)):
                found += 1
    return found


print("=" * 64)
print("GrowPy PVE asset import: %d species" % len(PLAN["species"]))
print("=" * 64)

master = PLAN["master_material"]
if eal.load_asset(master) is None:
    raise RuntimeError("master material not found: %s" % master)
trees = trees_in_open_level()
if trees:
    raise RuntimeError(
        "the open level shows %d tree(s) from this content: open an empty level "
        "first, the material updates below refresh every one of them and have "
        "crashed the editor that way" % trees)

for spec in PLAN["species"]:
    print("")
    print("--- %s -> %s" % (spec["species"], spec["content_folder"]))

    failures.extend(import_palette(spec))

    # Textures first, materials second: VT must be on before the material
    # points at the texture.
    for entry, is_normal in (
            (spec["bark_color"], False), (spec["bark_normal"], True)):
        problem = import_bark_texture(entry, is_normal)
        if problem:
            failures.append(problem)

    failures.extend(build_bark_material(spec, master))
    failures.extend(audit_for_usd_stubs(spec["bark_folder"]))

    # Leaves: the same order, maps before the material that samples them.
    if spec["foliage"]:
        for entry, is_normal in (
                (spec["foliage"]["color"], False), (spec["foliage"]["normal"], True)):
            problem = import_foliage_texture(entry, is_normal)
            if problem:
                failures.append(problem)
        problems = build_foliage_material(spec, master)
        failures.extend(problems)
        if not problems:
            failures.extend(repoint_leaf_materials(spec))
    else:
        failures.append("%s has no packed foliage maps in the plan: its leaves "
                        "keep the USD import material, which season and health "
                        "cannot reach" % spec["species"])

    print("   palette: %d prototype(s)" % len(spec["prototypes"]))

print("")
print("=" * 64)
if failures:
    for problem in failures:
        print("FAIL: %s" % problem)
    raise RuntimeError("%d PVE asset problem(s) -- see above" % len(failures))
print("OK: palette, bark and foliage materials verified for %d species"
      % len(PLAN["species"]))
'''


def generate_pve_asset_script(
    output_dir: Path,
    plan: PVEAssetPlan,
    script_name: str = "growpy_pve_assets.py",
) -> Path:
    """Write a UE Python script that imports ``plan``'s assets in the open editor.

    Args:
        output_dir: Directory to write the script into; created if absent.
        plan: What to import, and which material sources to build from.
        script_name: File name for the generated script.

    Returns:
        Path to the written script, ready for ``growpy-ue-exec``.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = output_dir / script_name
    script_path.write_text(
        _SCRIPT_TEMPLATE.format(plan=_plan_payload(plan)), encoding="utf-8"
    )
    logger.info(
        "Generated PVE asset script: %s (%d species, %d prototype(s))",
        script_path,
        len(plan.species),
        sum(len(s.prototypes) for s in plan.species),
    )
    return script_path
