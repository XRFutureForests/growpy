# ruff: noqa: E501, E731, C408, C416
"""E144 editor-side A/B (growpy-ue-session --run-until-done, ticker): which distributor of the Greenleaf maple graph makes the trees?

The graph holds two parallel branches (hormone-mode distributor -> export node 1, parametric-mode distributor -> export node 2,
both naming the same mesh). Executes the graph once, exports each Export node to its own scratch folder with ExportWithSettings
(the graph and the sandbox are untouched), then reads each result: bounds, bones, T3D (Nanite assembly nodes = parts).
Output: env PVE59_OUT / gvmode/ (probe.json + t3d, same layout as maple_pilot/gv_probe) and export_done_gvmode.json (done file).
"""

import json
import os
import time
import traceback

import unreal

OUT = os.environ.get("PVE59_OUT", "data/output/pve59_extract/raw")
G = os.path.join(OUT, "gvmode")
os.makedirs(G, exist_ok=True)
GRAPH = "/Game/GVBroadleafPresets/Procedural/PVE_GV_Simple_Maple"
DONE = os.path.join(OUT, "export_done_gvmode.json")
sub = unreal.get_editor_subsystem(unreal.ProceduralVegetationEditorSubsystem)
t0 = time.time()
res = {"graph": GRAPH, "events": [], "errors": [], "exports": {}}
st = {"phase": "start", "i": 0, "nodes": []}


def ev(m):
    res["events"].append([round(time.time() - t0, 1), m])
    unreal.log(f"PVE59GV {m}")


def t3d(a, name):
    f = os.path.join(G, name + ".t3d")
    task = unreal.AssetExportTask()
    task.object, task.filename, task.exporter = a, f, unreal.ObjectExporterT3D()
    task.automated, task.prompt, task.replace_identical = True, False, True
    return f if unreal.Exporter.run_asset_export_task(task) else None


def probe(path, name):
    a = unreal.load_asset(path)
    b = a.get_bounds()
    row = {
        "origin": [b.origin.x, b.origin.y, b.origin.z],
        "extent": [b.box_extent.x, b.box_extent.y, b.box_extent.z],
        "t3d": t3d(a, name),
    }
    pose = unreal.AnimPoseExtensions.get_reference_pose(a.skeleton)
    names = unreal.AnimPoseExtensions.get_bone_names(pose)
    row["bones"] = [
        [str(n)]
        + [
            getattr(
                unreal.AnimPoseExtensions.get_bone_pose(
                    pose, n, unreal.AnimPoseSpaces.WORLD
                ).translation,
                k,
            )
            for k in "xyz"
        ]
        for n in names
    ]
    return row


def fin():
    res["total_s"] = round(time.time() - t0, 1)
    json.dump(res, open(DONE, "w", encoding="utf-8"), indent=1)
    unreal.unregister_slate_post_tick_callback(handle)


def tick(_dt):
    try:
        p = st["phase"]
        if p == "start":
            a = unreal.load_asset(GRAPH)
            st["asset"] = a
            st["nodes"] = [
                (str(e.node_name), e.settings) for e in sub.get_export_settings(a)
            ]
            res["export_nodes"] = [n for n, _ in st["nodes"]]
            st["exec"] = sub.execute_graph(a)
            st["phase"] = "executing"
            ev("execute_graph started")
        elif p == "executing":
            s = sub.get_execution_state(st["asset"])
            if not s.is_running:
                ev(f"execution finished has_result={s.has_result}")
                try:
                    v = st["exec"].get_editor_property("value")
                    res["execution"] = {
                        "succeeded": v.succeeded,
                        "messages": [
                            [str(m.node_name), str(m.severity), str(m.message)]
                            for m in v.messages
                        ],
                    }
                except Exception as e:
                    res["execution"] = {"read_error": repr(e)}
                st["phase"] = "next"
        elif p == "next":
            if st["i"] >= len(st["nodes"]):
                fin()
                st["phase"] = "done"
                return
            node, settings = st["nodes"][st["i"]]
            s2 = settings.copy() if hasattr(settings, "copy") else settings
            s2.set_editor_property(
                "content_browser_folder",
                unreal.DirectoryPath(f"/Game/PVE59Out/GV_{st['i']}"),
            )
            s2.set_editor_property("mesh_name", f"SK_GVmaple_node{st['i']}")
            s2.set_editor_property(
                "replace_policy", unreal.PVAssetReplacePolicy.REPLACE
            )
            st["cur"] = node
            st["t_exp"] = time.time()
            st["export"] = sub.export_with_settings(st["asset"], node, s2, True, True)
            st["phase"] = "exporting"
            ev(f"export started node {node} -> GV_{st['i']}")
        elif p == "exporting":
            s = sub.get_export_state(st["asset"])
            if s.has_result and not s.is_exporting and not s.is_waiting_for_execution:
                r = s.result
                nd = [
                    {
                        "node": str(n.node_name),
                        "status": str(n.status),
                        "message": str(n.message),
                        "assets": [str(x) for x in n.created_assets],
                        "warnings": [str(x) for x in n.warnings],
                    }
                    for n in r.nodes
                ]
                res["exports"][st["cur"]] = {
                    "succeeded": r.succeeded,
                    "seconds": round(time.time() - st["t_exp"], 1),
                    "nodes": nd,
                }
                ev(f"export finished {st['cur']} succeeded={r.succeeded}")
                for n in nd:
                    for path in n["assets"]:
                        if "/SK_" in path:
                            try:
                                res.setdefault("trees", {})[path] = probe(
                                    path.split(".")[0], f"node{st['i']}"
                                )
                            except Exception:
                                res.setdefault("trees", {})[path] = {
                                    "error": traceback.format_exc()[-300:]
                                }
                st["i"] += 1
                st["phase"] = "next"
    except Exception:
        res["errors"].append(traceback.format_exc()[-800:])
        ev("tick exception")
        fin()
        st["phase"] = "done"


handle = unreal.register_slate_post_tick_callback(tick)
print("PVE59_GVMODE_TICKER_REGISTERED")
