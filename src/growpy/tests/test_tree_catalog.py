"""Tree catalog manifest (XRFF-678): build from plans, bones, scores; check gaps."""

import json
import tomllib

from growpy.tools import tree_catalog


def _plan(folder, tree_id, growth, instances=1592, bark="/Game/M/MI_bark"):
    folder.mkdir(parents=True)
    mesh = {
        "mesh_name": f"SK_NorwaySpruce_{tree_id}",
        "asset": f"/Game/C/SK_NorwaySpruce_{tree_id}",
        "static_asset": f"/Game/CS/SM_NorwaySpruce_{tree_id}",
        "growth_json": str(growth),
        "species": "norway_spruce",
        "tree_id": tree_id,
        "palette": "twigs",
        "dbh_cm": 27.2,
        "height_m": 20.88,
        "predicted_instances": instances,
        "predicted_m2": 476.0,
        "target_m2": 477.1,
    }
    manifest = {"graphs": [{"bark_material": bark, "meshes": [mesh]}]}
    (folder / "pve_export_manifest.json").write_text(json.dumps(manifest))
    return folder


def _scores(path, growth_name, base_inside):
    rows = [
        "trait,value,height_row,p25,median,p75,n,source,flag,inside,pass_fail,offset_iqr,tree",
        f"height_m,20.1,20,19.4,20.5,21.4,215,measured,,True,False,0,{growth_name}",
        f"dbh_m,0.27,20,0.22,0.25,0.28,215,measured,,True,True,0,{growth_name}",
        f"crown_base_m,8.5,20,5,7,9,215,measured,,{base_inside},True,0,{growth_name}",
        f"crown_radius_m,2.67,20,1.86,2.05,2.33,215,measured,,False,True,1,{growth_name}",
    ]
    path.write_text("\n".join(rows) + "\n")
    return path


def test_build_writes_one_entry_per_tree_and_a_later_plan_wins(tmp_path):
    growth = tmp_path / "Norway_Spruce_r07_h20m_d27cm_full_growth_data.json"
    growth.write_text("{}")
    old = _plan(tmp_path / "old", "r07_h20m", growth, instances=16285)
    new = _plan(tmp_path / "new", "r07_h20m", growth, instances=1592)
    bones = tmp_path / "bones.json"
    bones.write_text(json.dumps({"SK_NorwaySpruce_r07_h20m": 2307}))
    scores = _scores(tmp_path / "s.csv", growth.name, True)
    out = tmp_path / "tree_catalog.toml"

    tree_catalog.build([old, new], bones, [scores], out)

    tree = tomllib.loads(out.read_text(encoding="utf-8"))["trees"]["norway_spruce"][
        "r07_h20m"
    ]
    assert (tree["twigs"], tree["plan"], tree["bones"]) == (1592, "new", 2307)
    assert (tree["radius"], tree["variant"], tree["twig_set"]) == (7, "summer", "twigs")
    assert (
        tree["material"] == "/Game/M/MI_bark"
    )  # not an intake entry: the instance path
    assert set(tree["target"]) == {
        "dbh_m",
        "crown_base_m",
        "crown_radius_m",
    }  # no height
    assert tree["target"]["crown_radius_m"]["inside"] is False


def test_check_reports_gaps_and_out_of_target_traits(tmp_path):
    growth = tmp_path / "Norway_Spruce_r07_h20m_d27cm_full_growth_data.json"
    growth.write_text("{}")
    plan = _plan(tmp_path / "p", "r07_h20m", growth)
    out = tmp_path / "tree_catalog.toml"
    tree_catalog.build(
        [plan], None, [_scores(tmp_path / "s.csv", growth.name, False)], out
    )

    missing, out_of_target = tree_catalog.check(out)

    assert missing == ["norway_spruce.r07_h20m: no bones"]
    assert out_of_target == [
        "norway_spruce.r07_h20m: crown_base_m 8.5 outside [5.0, 9.0]",
        "norway_spruce.r07_h20m: crown_radius_m 2.67 outside [1.86, 2.33]",
    ]
    assert tree_catalog.main(["check", "--manifest", str(out)]) == 1


def test_a_planned_tree_missing_from_the_bones_dump_is_not_a_catalog_asset(tmp_path):
    growth = tmp_path / "g.json"
    growth.write_text("{}")
    kept = _plan(tmp_path / "a", "r07_h20m", growth)
    dropped = _plan(
        tmp_path / "b", "r00_h20m", growth
    )  # e.g. an r00 tree since dropped
    bones = tmp_path / "bones.json"
    bones.write_text(json.dumps({"SK_NorwaySpruce_r07_h20m": 2307}))
    out = tmp_path / "tree_catalog.toml"

    tree_catalog.build([kept, dropped], bones, [], out)

    trees = tomllib.loads(out.read_text(encoding="utf-8"))["trees"]["norway_spruce"]
    assert set(trees) == {"r07_h20m"}


def test_a_tree_without_scores_is_a_finding_not_a_gap(tmp_path):
    growth = tmp_path / "g.json"
    growth.write_text("{}")
    plan = _plan(tmp_path / "p", "r10_h05m", growth)
    bones = tmp_path / "bones.json"
    bones.write_text(json.dumps({"SK_NorwaySpruce_r10_h05m": 877}))
    out = tmp_path / "tree_catalog.toml"
    tree_catalog.build([plan], bones, [], out)

    missing, out_of_target = tree_catalog.check(out)

    assert missing == []
    assert out_of_target == ["norway_spruce.r10_h05m: no target-sheet result"]
    assert tree_catalog.main(["check", "--manifest", str(out)]) == 0
