"""E144 editor-side export test for UE 5.9 (growpy-ue-session --run-until-done, ticker): ExecuteGraph + Export without dialogs.

Graph: our E143 r1 au04s2 h20 graph (copy in the PVE59Test project). Records timings, execution messages, export result,
and the Nanite / bone facts of the written meshes -> env PVE59_OUT / export_done.json (the done file; written last).
"""

import json
import os
import time
import traceback

import unreal

OUT = os.environ.get("PVE59_OUT", r"D:\Git\work\growpy\data\output\pve59_extract\raw")
GRAPH = "/Game/PVE_E143/r1_au04s2_c27p5/Structures/PVG_SycamoreMaple_1"
DONE = os.path.join(OUT, "export_done.json")
sub = unreal.get_editor_subsystem(unreal.ProceduralVegetationEditorSubsystem)
t0 = time.time()
res = {"graph": GRAPH, "events": [], "errors": []}
st = {"phase": "start", "asset": None, "exec_started": None, "export_started": None}


def ev(msg):
    res["events"].append([round(time.time() - t0, 1), msg])
    unreal.log(f"PVE59 {msg}")


def fin():
    res["total_s"] = round(time.time() - t0, 1)
    json.dump(res, open(DONE, "w", encoding="utf-8"), indent=1)
    unreal.unregister_slate_post_tick_callback(handle)


def mesh_facts(path):
    a = unreal.load_asset(path)
    row = {"class": a.get_class().get_name()}
    try:
        row["nanite"] = str(a.get_editor_property("nanite_settings"))[:600]
    except Exception:
        pass
    try:
        b = a.get_bounds()
        row["extent_cm"] = [b.box_extent.x, b.box_extent.y, b.box_extent.z]
    except Exception:
        pass
    try:
        pose = unreal.AnimPoseExtensions.get_reference_pose(a.skeleton)
        row["bones"] = len(unreal.AnimPoseExtensions.get_bone_names(pose))
    except Exception:
        pass
    return row


def tick(_dt):
    try:
        p = st["phase"]
        if p == "start":
            a = unreal.load_asset(GRAPH)
            st["asset"] = a
            es = sub.get_export_support()
            res["support"] = [es.nanite_supported, es.nanite_foliage_supported, es.nanite_voxels_supported]
            res["export_nodes"] = [{"node": str(e.node_name), "settings": str(e.settings)[:1500]} for e in sub.get_export_settings(a)]
            st["exec"] = sub.execute_graph(a)
            st["phase"] = "executing"
            ev("execute_graph started")
        elif p == "executing":
            s = sub.get_execution_state(st["asset"])
            if not s.is_running:
                ev(f"execution finished has_result={s.has_result} out_of_date={s.is_out_of_date}")
                try:
                    v = st["exec"].get_editor_property("value")
                    res["execution"] = {"succeeded": v.succeeded, "messages": [[str(m.node_name), str(m.severity), str(m.message)] for m in v.messages]}
                except Exception as e:
                    res["execution"] = {"read_error": repr(e)}
                st["export"] = sub.export(st["asset"], "", True, True)
                st["phase"] = "exporting"
                ev("export started (save, overwrite)")
        elif p == "exporting":
            s = sub.get_export_state(st["asset"])
            if s.has_result and not s.is_exporting and not s.is_waiting_for_execution:
                r = s.result
                res["export"] = {"succeeded": r.succeeded, "warnings": [str(w) for w in r.warnings],
                                 "nodes": [{"node": str(n.node_name), "status": str(n.status), "message": str(n.message),
                                            "assets": [str(x) for x in n.created_assets], "warnings": [str(x) for x in n.warnings]} for n in r.nodes]}
                ev(f"export finished succeeded={r.succeeded}")
                res["meshes"] = {}
                for n in r.nodes:
                    for path in n.created_assets:
                        try:
                            res["meshes"][str(path)] = mesh_facts(str(path))
                        except Exception:
                            res["meshes"][str(path)] = {"error": traceback.format_exc()[-300:]}
                fin()
                st["phase"] = "done"
    except Exception:
        res["errors"].append(traceback.format_exc()[-800:])
        ev("tick exception")
        fin()
        st["phase"] = "done"


handle = unreal.register_slate_post_tick_callback(tick)
print("PVE59_EXPORT_TICKER_REGISTERED")
