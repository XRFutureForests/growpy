"""Where growpy's output lives inside an Unreal project.

The project-wide content layout agreed on 2026-09-24 (knowledge hub,
``02-SYSTEM-ARCHITECTURE/unreal-collaboration-boundaries`` §9.3). Everything
growpy imports is regenerable and lands under ``TREES_ROOT``, which a dataset
run may wipe and re-import. The schema those imports depend on lives outside
it, under ``SCHEMA_ROOT``: UE's Python API cannot create a UserDefinedStruct,
so a wipe that took ``ST_TreeCatalogEntry`` would stop every later import.

Every Unreal path default in growpy comes from here; ``config/unreal.toml``
overrides them per project.
"""

# Generated tree content: Catalog/<species>/, Foliage/, Materials/<species>/,
# Graphs/ and DT_TreeCatalog. Wiped and re-imported per dataset run.
TREES_ROOT = "/Game/Generated/Trees"

# Schema, never wiped: ST_TreeCatalogEntry, DT_TreeCatalogTemplate (the empty
# table growpy-pve-catalog duplicates) and the local MA_Foliage_Trees copy.
SCHEMA_ROOT = "/Game/XRFF/Twin"

# The plot-tree spawn graph whose TreeCatalogDataTable parameter points at the
# catalog.
PCG_TREES_GRAPH = "/Game/XRFF/PCG/PCG_Trees"

# QA levels growpy-pve-gallery writes. A personal sandbox: never migrated to
# the production project, never committed.
GALLERY_FOLDER = "/Game/Developers/Max/TreeGallery"
