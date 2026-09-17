"""Consolidate PVE exports into ``DT_TreeCatalog`` and audit coverage (XRFF-420).

After the graphs have been exported, three things have to be true before the
twin can spawn a tree: the skeletal mesh the manifest expected actually
exists (``FPVEditor::OnExport`` silently skips a chain whose input pin carries
no mesh, B8), the catalog names it with the columns ``PCG_Trees`` joins on,
and the PCG graph reads THAT catalog. This tool does all three from the
coverage manifest ``plan_pve_graphs`` wrote, in the running editor:

1. every expected mesh is loaded; a missing one is reported, never invented,
   and the bounds height is read back beside the stage it was grown to;
2. ``DT_TreeCatalog`` is (re)built under the PVE content root by duplicating
   the schema template in ``/Game/Templates`` and filling it from CSV, one row
   per exported mesh;
3. ``PCG_Trees``' ``TreeCatalogDataTable`` graph parameter is pointed at it
   (the parameter is a property bag, written through ``import_text`` and read
   back), so the join is live without a manual edit.

THE JOIN, read off ``PCG_Trees`` (T3D, 2026-09-15): the catalog side builds
``JoinKey = Species + Height + Competition``; the tree side builds
``species_name + round(height_m / HeightIncrement) * HeightIncrement +
(nn_distance_cm <= CompetitionThresholdCM)``. So ``Species`` must spell the
twin database's display name exactly (``European Beech``, ``Small-leaved
Linden``), ``Height`` is the STAGE height (5, 10, ... 25), and ``Competition``
is a boolean. With the r08 / r16 matrix the tight shell is the competed tree
(``true``) and the wide one the open tree (``false``).

Usage::

    growpy-pve-catalog data/output/forest/unreal_scripts/pve_export_manifest.json
    growpy-pve-catalog <manifest> --catalog /Game/PVE/DT_TreeCatalog --no-pcg
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import re
import sys
from pathlib import Path

logger = logging.getLogger("growpy.pve_catalog")

TEMPLATE_STRUCT = "/Game/Templates/ST_TreeCatalogEntry"
TEMPLATE_TABLE = "/Game/Templates/DT_TreeCatalog"
DEFAULT_CATALOG = "/Game/PVE/DT_TreeCatalog"
DEFAULT_PCG_GRAPH = "/Game/PCG/PCG_Trees"
PCG_PARAMETER = "TreeCatalogDataTable"

# Species column = the twin database's display name (data/lookups/species.csv
# in digital-twin-db), which is what DT_Trees.species_name carries and what the
# PCG join compares against. Title-casing the standardized name gives every
# name but the hyphenated one.
SPECIES_DISPLAY_OVERRIDES = {"small_leaved_linden": "Small-leaved Linden"}

# Radius label of the competed variant: r08 is the tight shell, r16 the open one.
COMPETED_RADIUS_MAX_M = 8.0

_TREE_ID = re.compile(r"^r(\d+)_h(\d+)m$")


def species_display_name(species: str) -> str:
    """``european_beech`` -> ``European Beech``; see SPECIES_DISPLAY_OVERRIDES."""
    if species in SPECIES_DISPLAY_OVERRIDES:
        return SPECIES_DISPLAY_OVERRIDES[species]
    return " ".join(part.capitalize() for part in species.split("_") if part)


def parse_tree_id(tree_id: str) -> tuple[float, float]:
    """``r08_h15m`` -> (radius m, stage height m)."""
    match = _TREE_ID.match(tree_id)
    if not match:
        raise ValueError(f"tree id {tree_id!r} is not r<NN>_h<NN>m")
    return float(match.group(1)), float(match.group(2))


def catalog_rows(manifest: dict) -> list[dict]:
    """One catalog row per expected mesh, from the manifest alone."""
    rows = []
    for graph in manifest["graphs"]:
        for mesh in graph["meshes"]:
            species = mesh.get("species")
            tree_id = mesh.get("tree_id")
            if not species or not tree_id:
                raise ValueError(
                    f"manifest mesh {mesh.get('mesh_name')!r} carries no species / "
                    f"tree_id -- re-run the plan; the catalog cannot guess them"
                )
            radius_m, height_m = parse_tree_id(tree_id)
            rows.append(
                {
                    "Name": mesh["mesh_name"],
                    "SkeletalMesh": f"{mesh['asset']}.{mesh['mesh_name']}",
                    "Species": species_display_name(species),
                    "Height": height_m,
                    "DBH": round(float(mesh.get("dbh_cm") or 0.0), 2),
                    "Competition": radius_m <= COMPETED_RADIUS_MAX_M,
                    # Not catalog columns; kept in the inventory beside it.
                    "species": species,
                    "tree_id": tree_id,
                    "radius_m": radius_m,
                    "asset": mesh["asset"],
                    "graph": graph["graph_asset"],
                    "density_source": mesh.get("density_source"),
                    "layout": mesh.get("layout"),
                    "predicted_instances": mesh.get("predicted_instances"),
                    "predicted_m2": mesh.get("predicted_m2"),
                    "target_m2": mesh.get("target_m2"),
                }
            )
    return rows


def rows_to_csv(rows: list[dict]) -> str:
    """UE DataTable CSV: ``---`` row-name header, the five struct columns."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["---", "SkeletalMesh", "Species", "Height", "DBH", "Competition"])
    for row in rows:
        writer.writerow(
            [
                row["Name"],
                row["SkeletalMesh"],
                row["Species"],
                f"{row['Height']:g}",
                f"{row['DBH']:g}",
                "true" if row["Competition"] else "false",
            ]
        )
    return out.getvalue()


UE_SCRIPT = '''\
"""GrowPy PVE catalog -- auto-generated, do not edit."""
import json
import unreal

ROWS = {rows!r}
CSV = {csv!r}
CATALOG = {catalog!r}
TEMPLATE_TABLE = {template_table!r}
TEMPLATE_STRUCT = {template_struct!r}
PCG_GRAPH = {pcg_graph!r}
PCG_PARAMETER = {pcg_parameter!r}
SET_PCG = {set_pcg!r}

eal = unreal.EditorAssetLibrary
report = {{"meshes": [], "missing": [], "catalog": CATALOG, "rows": 0, "pcg": None}}

# 1. every expected mesh exists; read its height off the bounds
for row in ROWS:
    path = row["asset"]
    entry = {{"mesh_name": row["Name"], "asset": path, "tree_id": row["tree_id"]}}
    if not eal.does_asset_exist(path):
        report["missing"].append(path)
        entry["exists"] = False
        report["meshes"].append(entry)
        continue
    mesh = eal.load_asset(path)
    entry["exists"] = mesh is not None
    if mesh is not None:
        try:
            bounds = mesh.get_bounds()
            extent = bounds.box_extent
            entry["height_m"] = round(float(extent.z) * 2.0 / 100.0, 2)
            entry["width_m"] = round(float(max(extent.x, extent.y)) * 2.0 / 100.0, 2)
        except Exception as exc:
            entry["bounds_error"] = repr(exc)
        try:
            nanite = mesh.get_editor_property("nanite_settings")
            entry["nanite"] = bool(nanite.get_editor_property("enabled"))
        except Exception:
            pass
    report["meshes"].append(entry)

present = [r for r in ROWS if r["asset"] not in set(report["missing"])]
unreal.log("PVECATALOG %d of %d expected meshes present" % (len(present), len(ROWS)))

# 2. the catalog: duplicate the schema template, fill from CSV
if not eal.does_asset_exist(TEMPLATE_STRUCT):
    raise RuntimeError("struct template missing: %s" % TEMPLATE_STRUCT)
folder = CATALOG.rsplit("/", 1)[0]
if not eal.does_directory_exist(folder):
    eal.make_directory(folder)
table = None
if eal.does_asset_exist(CATALOG):
    # Reuse a catalog that already exists: once PCG_Trees points at it the
    # delete fails (it is referenced) and the duplicate then finds the path
    # taken (2026-09-16). fill_data_table_from_csv_string replaces the rows.
    table = eal.load_asset(CATALOG)
    if table is not None:
        unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(table)
if table is None and eal.does_asset_exist(TEMPLATE_TABLE):
    table = eal.duplicate_asset(TEMPLATE_TABLE, CATALOG)
if table is None:
    factory = unreal.DataTableFactory()
    factory.set_editor_property("struct", eal.load_asset(TEMPLATE_STRUCT))
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    table = tools.create_asset(
        CATALOG.rsplit("/", 1)[1], folder, unreal.DataTable, factory
    )
if table is None:
    raise RuntimeError("could not create %s" % CATALOG)

# Only rows whose mesh exists: a row naming an absent mesh spawns nothing and
# hides the gap. The missing list above is the audit.
present_names = set(r["Name"] for r in present)
lines = CSV.splitlines()
kept = [lines[0]] + [ln for ln in lines[1:] if ln.split(",", 1)[0] in present_names]
ok = unreal.DataTableFunctionLibrary.fill_data_table_from_csv_string(
    table, "\\n".join(kept)
)
if not ok:
    raise RuntimeError("fill_data_table_from_csv_string failed for %s" % CATALOG)
names = unreal.DataTableFunctionLibrary.get_data_table_row_names(table)
report["rows"] = len(names)
if len(names) != len(present):
    raise RuntimeError(
        "catalog holds %d rows, expected %d" % (len(names), len(present))
    )
eal.save_asset(CATALOG)
unreal.log("PVECATALOG %s: %d rows" % (CATALOG, len(names)))

# 3. point PCG_Trees at it
if SET_PCG:
    pcg = eal.load_asset(PCG_GRAPH)
    if pcg is None:
        report["pcg"] = "graph not found: %s" % PCG_GRAPH
    else:
        bag = pcg.get_editor_property("user_parameters")
        text = bag.export_text()
        wanted = '%s="%s.%s"' % (PCG_PARAMETER, CATALOG, CATALOG.rsplit("/", 1)[1])
        import re as _re
        replacement = wanted.replace("\\\\", "\\\\\\\\")
        new_text, n = _re.subn(PCG_PARAMETER + r'="[^"]*"', replacement, text)
        if n == 0:
            report["pcg"] = "parameter %s not in %s" % (PCG_PARAMETER, text[:200])
        else:
            bag.import_text(new_text)
            pcg.set_editor_property("user_parameters", bag)
            back = pcg.get_editor_property("user_parameters").export_text()
            if wanted in back:
                eal.save_asset(PCG_GRAPH)
                report["pcg"] = "ok"
            else:
                report["pcg"] = "write did not take: %s" % back[:300]
    unreal.log("PVECATALOG pcg: %s" % report["pcg"])

unreal.log("PVECATALOG_REPORT " + json.dumps(report))
'''


def write_ue_script(
    manifest_path: Path,
    rows: list[dict],
    *,
    catalog: str,
    set_pcg: bool,
    pcg_graph: str = DEFAULT_PCG_GRAPH,
) -> Path:
    script = manifest_path.parent / "growpy_pve_catalog.py"
    script.write_text(
        UE_SCRIPT.format(
            rows=rows,
            csv=rows_to_csv(rows),
            catalog=catalog,
            template_table=TEMPLATE_TABLE,
            template_struct=TEMPLATE_STRUCT,
            pcg_graph=pcg_graph,
            pcg_parameter=PCG_PARAMETER,
            set_pcg=set_pcg,
        ),
        encoding="utf-8",
    )
    return script


def write_inventory(manifest_path: Path, rows: list[dict]) -> tuple[Path, Path]:
    json_path = manifest_path.parent / "tree_inventory.json"
    csv_path = manifest_path.parent / "tree_inventory.csv"
    json_path.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return json_path, csv_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "manifest", type=Path, help="pve_export_manifest.json of the run"
    )
    parser.add_argument("--catalog", default=DEFAULT_CATALOG)
    parser.add_argument("--pcg-graph", default=DEFAULT_PCG_GRAPH)
    parser.add_argument(
        "--no-pcg", action="store_true", help="do not repoint PCG_Trees at the catalog"
    )
    parser.add_argument(
        "--script-only", action="store_true", help="write the UE script, do not run it"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s"
    )

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    rows = catalog_rows(manifest)
    if not rows:
        logger.error("manifest lists no meshes")
        return 1
    json_path, csv_path = write_inventory(args.manifest, rows)
    logger.info("inventory: %s, %s (%d trees)", json_path, csv_path, len(rows))
    script = write_ue_script(
        args.manifest,
        rows,
        catalog=args.catalog,
        set_pcg=not args.no_pcg,
        pcg_graph=args.pcg_graph,
    )
    logger.info("UE script: %s", script)
    if args.script_only:
        return 0

    from growpy.io.unreal import ue_remote

    result = ue_remote.run_file(str(script), timeout=1800)
    report = None
    for line in result.get("output", []):
        text = line.get("output", "") if isinstance(line, dict) else str(line)
        if "PVECATALOG_REPORT " in text:
            report = json.loads(text.split("PVECATALOG_REPORT ", 1)[1])
        elif "PVECATALOG" in text:
            logger.info("  %s", text.split("LogPython:")[-1].strip())
    if not result.get("success"):
        logger.error("editor script failed: %s", result.get("result"))
        return 1
    if report is None:
        logger.error("no report from the editor")
        return 1
    report_path = args.manifest.parent / "pve_catalog_report.json"
    report_path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    logger.info(
        "catalog %s: %d rows, %d missing mesh(es), pcg=%s -> %s",
        report["catalog"],
        report["rows"],
        len(report["missing"]),
        report["pcg"],
        report_path,
    )
    for path in report["missing"]:
        logger.warning("  missing: %s", path)
    return 1 if report["missing"] else 0


if __name__ == "__main__":
    sys.exit(main())
