"""E144 editor-side dump for the UE 5.9 PVE analysis project (run through growpy-ue-session --run).

Read-only: T3D of every PVE graph / data asset in the project, the 5.9 PVE subsystem API facts (node types, schemas,
export support, export node settings) and the asset-registry mesh tags of the foliage parts (no mesh is loaded, so
no Nanite build). Output folder: env PVE59_OUT (default data/output/pve59_extract/raw next to this checkout).
"""

import json
import os
import traceback

import unreal

OUT = os.environ.get("PVE59_OUT", r"D:\Git\work\growpy\data\output\pve59_extract\raw")
os.makedirs(os.path.join(OUT, "t3d"), exist_ok=True)
ar = unreal.AssetRegistryHelpers.get_asset_registry()
ar.wait_for_completion()
sub = unreal.get_editor_subsystem(unreal.ProceduralVegetationEditorSubsystem)
res = {"engine": unreal.SystemLibrary.get_engine_version(), "errors": []}


def err(where):
    res["errors"].append({"where": where, "tb": traceback.format_exc()[-500:]})


def t3d(asset, name):
    f = os.path.join(OUT, "t3d", name + ".t3d")
    task = unreal.AssetExportTask()
    task.object, task.filename, task.exporter = asset, f, unreal.ObjectExporterT3D()
    task.automated, task.prompt, task.replace_identical = True, False, True
    return f if unreal.Exporter.run_asset_export_task(task) else None


def props(obj, names):
    out = {}
    for n in names:
        try:
            v = obj.get_editor_property(n)
            out[n] = str(v) if not isinstance(v, (int, float, bool, str)) else v
        except Exception as e:
            out[n] = f"<{type(e).__name__}>"
    return out


# --- API facts
try:
    types = [str(t) for t in sub.list_node_types()]
    res["node_types"] = types
    res["node_desc"], res["node_schema"] = {}, {}
    for t in types:
        try:
            d = sub.describe_node(t)
            res["node_desc"][t] = {"title": str(d.default_title), "tooltip": str(d.tooltip)}
            s = sub.get_node_schema(t)
            pin = lambda p: {"label": str(p.label), "type": str(p.type_identifier), "required": bool(p.required), "multi": bool(p.allow_multiple_connections)}  # noqa: E731
            res["node_schema"][t] = {"in": [pin(p) for p in s.input_pins], "out": [pin(p) for p in s.output_pins]}
        except Exception:
            err("node " + t)
except Exception:
    err("list_node_types")
try:
    es = sub.get_export_support()
    res["export_support"] = {"nanite": es.nanite_supported, "nanite_foliage": es.nanite_foliage_supported, "nanite_voxels": es.nanite_voxels_supported}
except Exception:
    err("export_support")
try:
    res["data_assets"] = [{"path": str(a.path), "class": str(a.class_name), "name": str(a.display_name)} for a in sub.list_data_assets()]
    res["pve_assets"] = [str(p) for p in sub.list_assets()]
except Exception:
    err("lists")

# --- every PVE-ish asset under /Game: T3D (graph + data assets), export-node settings of the graphs
EXPORT_FIELDS = None
rows = {}
for ad in ar.get_assets_by_path("/Game", recursive=True):
    cls = str(ad.asset_class_path.asset_name)
    if not (cls.startswith("ProceduralVegetation") or cls.startswith("PV")):
        continue
    pkg = str(ad.package_name)
    row = {"class": cls}
    try:
        a = unreal.load_asset(pkg)
        row["t3d"] = t3d(a, pkg.strip("/").replace("/", "__"))
        if cls == "ProceduralVegetation":
            try:
                g = sub.get_graph(a)
                row["nodes"] = len(g.get_editor_property("nodes")) if hasattr(g, "nodes") else None
                ex = []
                for e in sub.get_export_settings(a):
                    st = e.settings
                    ex.append({"node": str(e.node_name), "settings": {k: str(st.get_editor_property(k)) for k in dir(st) if not k.startswith("_") and not callable(getattr(st, k, None)) and k != "cls"}})
                row["export_nodes"] = ex
            except Exception:
                row["export_error"] = traceback.format_exc()[-400:]
    except Exception:
        row["error"] = traceback.format_exc()[-400:]
    rows[pkg] = row
    unreal.log(f"PVE59 dumped {pkg} ({cls})")
res["assets"] = rows

# --- foliage part tags from the registry (no load)
TAGS = ("Triangles", "NaniteTriangles", "Vertices", "ApproxSize", "LODs", "NaniteEnabled", "Materials", "Bones", "ImportedBounds")
parts = {}
for ad in ar.get_assets_by_path("/Game", recursive=True):
    cls = str(ad.asset_class_path.asset_name)
    if cls not in ("StaticMesh", "SkeletalMesh"):
        continue
    pkg = str(ad.package_name)
    if "/Instances/" not in pkg and "/Twigs/" not in pkg and "/Trees/" not in pkg and "/Tree_" not in pkg:
        continue
    parts[pkg] = {"class": cls, **{t: str(ad.get_tag_value(t)) for t in TAGS if ad.get_tag_value(t)}}
res["mesh_tags"] = parts
json.dump(res, open(os.path.join(OUT, "dump.json"), "w", encoding="utf-8"), indent=1)
print("PVE59_DUMP_DONE", len(rows), "pve assets,", len(parts), "meshes,", len(res["errors"]), "errors")
