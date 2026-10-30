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

# Generated tree content: Catalog/<species>/, Foliage/, Materials/<species>/,
# Graphs/ and DT_TreeCatalog. Wiped and re-imported per dataset run.
TREES_ROOT = "/Game/Generated/Trees"

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
