"""Where growpy's output lives inside an Unreal project.

The project-wide content layout agreed on 2026-09-24 and merged with the team's
folder proposal on 2026-10-13 (knowledge hub,
``02-SYSTEM-ARCHITECTURE/unreal-content-structure-plan``). Everything
growpy imports is regenerable and lands under ``TREES_ROOT``, which a dataset
run may wipe and re-import. The schema those imports depend on lives outside
it, under ``SCHEMA_ROOT``: UE's Python API cannot create a UserDefinedStruct,
so a wipe that took ``ST_TreeCatalogEntry`` would stop every later import.

Every Unreal path default in growpy comes from here; ``[unreal]`` in
``config/unreal.toml`` overrides them per project, because projects differ
(XRFF_Twin keeps the schema in ``/Game/00_XRFF/20_DigitalTwinDatabase``):
``project_path`` and ``pve_content_root`` for ``TREES_ROOT``, ``db_path`` for
``SCHEMA_ROOT``, ``pcg_trees_graph`` for ``PCG_TREES_GRAPH``.
"""

# Generated tree content (owner 2026-11-18, hub decisions "Tree catalog
# layout"): pipeline-written only, wiped and re-imported per dataset run.
TREES_ROOT = "/Game/00_XRFF/30_Forest/TreeLibrary"

# The root before 2026-11-18. Kept for the one migration: the next full
# regeneration writes into TREES_ROOT, this stays until the new one is verified.
LEGACY_TREES_ROOT = "/Game/Generated/Trees"

# Subfolders under a content root (TREES_ROOT or a sandbox root).
STRUCTURES_DIR = "Structures"  # PVE graphs
STRUCTURES_STATIC_DIR = "StructuresStatic"
TWIGS_DIR = "Twigs"  # foliage parts, <species>/ and ThirdParty/<pack>/
THIRD_PARTY_DIR = "ThirdParty"
MATERIALS_DIR = "Materials"  # leaf/bark MIs, <species>/ and Bark/
BARK_DIR = "Bark"
TREES_DIR = "Trees"  # exported SK assemblies, <species>/
TREES_STATIC_DIR = "TreesStatic"  # static SM twins, <species>/
WIND_DIR = "Wind"

STRUCTURES_PATH = f"{TREES_ROOT}/{STRUCTURES_DIR}"
STRUCTURES_STATIC_PATH = f"{TREES_ROOT}/{STRUCTURES_STATIC_DIR}"
TWIGS_PATH = f"{TREES_ROOT}/{TWIGS_DIR}"
MATERIALS_PATH = f"{TREES_ROOT}/{MATERIALS_DIR}"
BARK_PATH = f"{MATERIALS_PATH}/{BARK_DIR}"
TREES_PATH = f"{TREES_ROOT}/{TREES_DIR}"
TREES_STATIC_PATH = f"{TREES_ROOT}/{TREES_STATIC_DIR}"
WIND_PATH = f"{TREES_ROOT}/{WIND_DIR}"


def content_relpath(package_path: str) -> str:
    """The folder on disk under the project: ``/Game/X`` -> ``Content/X``."""
    return "Content" + package_path.removeprefix("/Game")


def third_party_twigs_path(pack: str) -> str:
    """Where copies of a vendor pack's parts used in our trees live."""
    return f"{TWIGS_PATH}/{THIRD_PARTY_DIR}/{pack}"


# Schema, never wiped: ST_TreeCatalogEntry, DT_TreeCatalogTemplate (the empty
# table growpy-pve-catalog duplicates) and, in projects that keep one, a local
# MA_Foliage_Trees copy (only the USD-route material batch looks for it).
SCHEMA_ROOT = "/Game/XRFF/Forest/Data"

# The plot-tree spawn graph whose TreeCatalogDataTable parameter points at the
# catalog.
PCG_TREES_GRAPH = "/Game/XRFF/Forest/Trees/PCG_Trees"

# QA levels growpy-pve-gallery writes. A personal sandbox: never migrated to
# the production project, never committed.
GALLERY_FOLDER = "/Game/Developers/Max/TreeGallery"
