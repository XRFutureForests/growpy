"""Import the Content Browser assets a PVE graph needs, from growpy.

A PVE graph cannot build a tree until three things exist in the project: the
**growth JSON** (emitted by the pipeline -- see
:func:`growpy.pipelines.forest_stages.export_growth_json_only`), the **twig
prototypes as UE static meshes** for the foliage palette, and a **bark material
instance** for the trunk. This module owns the second and third, which were
done by hand until XRFF-440.

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

The script is idempotent: an existing correct material is left alone, an
existing wrong one is repaired **in place** (exported meshes reference it by
path, so a repair reaches every tree already exported without a re-export), and
a missing one is cloned.
"""

from __future__ import annotations

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


@dataclass(frozen=True)
class SpeciesAssetSpec:
    """Everything one species needs in the Content Browser."""

    species: str
    content_folder: str
    prototypes: tuple[PalettePrototype, ...]
    bark_color: Path
    bark_normal: Path

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

    @property
    def foliage_folder(self) -> str:
        return f"{self.content_folder}/Foliage"

    @property
    def bark_folder(self) -> str:
        return f"{self.content_folder}/Bark"

    @property
    def bark_material(self) -> str:
        return f"{self.bark_folder}/MI_{self.species}_bark"

    @property
    def palette_meshes(self) -> tuple[str, ...]:
        """Palette mesh paths, in prototype order.

        This is the list a :class:`~growpy.io.unreal.pve_graph_builder.
        PVEGraphSpec` takes, so the graph and the import cannot disagree about
        where a prototype lives.
        """
        return tuple(p.mesh_path(self.foliage_folder) for p in self.prototypes)


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


def _camel(species: str) -> str:
    return "".join(part.capitalize() for part in species.split("_") if part)


def build_species_asset_spec(
    species: str,
    content_root: str = "/Game/PVE",
    folder_name: str | None = None,
) -> SpeciesAssetSpec:
    """Resolve one species' palette and bark sources from disk.

    Prototype count is discovered, never hardcoded -- beech ships 5 and fir 8.
    Twig directory and bark texture both resolve through
    ``config/tree_asset_lookup.csv``, so a species whose twig is another
    species' (Norway spruce uses the fir's) resolves to the right files.

    Raises:
        FileNotFoundError: If the twig prototypes or either bark texture are
            missing. Silence here would mean an empty palette or an untextured
            trunk discovered only by looking at a tree.
    """
    from growpy.config.paths import (
        get_bark_normal_texture_path,
        get_bark_texture_path,
        get_twig_files_by_type,
    )

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

    return SpeciesAssetSpec(
        species=species,
        content_folder=f"{content_root}/{folder_name or _camel(species)}",
        prototypes=prototypes,
        bark_color=color,
        bark_normal=normal,
    )


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
            }
            for s in plan.species
        ],
    }


_SCRIPT_TEMPLATE = '''\
"""GrowPy PVE asset import -- auto-generated, do not edit.

Imports the twig palette and builds the bark material for each species, then
verifies every write by reading it back. Run with:

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


def import_palette(spec):
    """Import every *_static.usda prototype that is not already present."""
    missing = []
    for proto in spec["prototypes"]:
        if eal.does_asset_exist(proto["mesh"]):
            print("   palette exists: %s" % proto["name"])
            continue
        print("   importing %s" % proto["name"])
        _import(proto["source"], spec["foliage_folder"], proto["name"])
        if not eal.does_asset_exist(proto["mesh"]):
            missing.append(proto["mesh"])
    return missing


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


print("=" * 64)
print("GrowPy PVE asset import: %d species" % len(PLAN["species"]))
print("=" * 64)

master = PLAN["master_material"]
if eal.load_asset(master) is None:
    raise RuntimeError("master material not found: %s" % master)

for spec in PLAN["species"]:
    print("")
    print("--- %s -> %s" % (spec["species"], spec["content_folder"]))

    for mesh in import_palette(spec):
        failures.append("palette mesh missing after import: %s" % mesh)

    # Textures first, materials second: VT must be on before the material
    # points at the texture.
    for entry, is_normal in (
            (spec["bark_color"], False), (spec["bark_normal"], True)):
        problem = import_bark_texture(entry, is_normal)
        if problem:
            failures.append(problem)

    failures.extend(build_bark_material(spec, master))
    failures.extend(audit_for_usd_stubs(spec["bark_folder"]))

    print("   palette: %d prototype(s)" % len(spec["prototypes"]))

print("")
print("=" * 64)
if failures:
    for problem in failures:
        print("FAIL: %s" % problem)
    raise RuntimeError("%d PVE asset problem(s) -- see above" % len(failures))
print("OK: palette and bark material verified for %d species"
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
