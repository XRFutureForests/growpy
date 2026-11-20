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


def test_grown_reads_the_tamf_sidecar_not_a_rewritten_growth_json(tmp_path):
    import os

    growth = tmp_path / "Norway_Spruce_r07_h20m_d27cm_full_growth_data.json"
    tamf = tmp_path / "Norway_Spruce_r07_h20m_d27cm_full.tamf.json"
    growth.write_text("{}")
    tamf.write_text("{}")
    os.utime(tamf, (1_700_000_000, 1_700_000_000))  # grown long ago; the JSON was rewritten since (DBH pass)
    assert tree_catalog.grown_at(growth) == tree_catalog._iso(1_700_000_000)
    tamf.unlink()
    assert tree_catalog.grown_at(growth) == tree_catalog._iso(growth.stat().st_mtime)


def test_build_records_bark_sources_settings_and_check_flags_stale_trees(tmp_path):
    import os

    growth = tmp_path / "Norway_Spruce_r07_h20m_d27cm_full_growth_data.json"
    growth.write_text("{}")
    patches = tmp_path / "preset_patches.json"
    patch = {"_README": ["x"], "norway_spruce": {"grow_nodes": 2, "_why": "y"}}
    patches.write_text(json.dumps(patch))
    os.utime(growth, (1_700_000_000, 1_700_000_000))  # grown before the patch file
    out = tmp_path / "tree_catalog.toml"

    plan = _plan(tmp_path / "p", "r07_h20m", growth)
    tree_catalog.build([plan], None, [], out, patches)

    trees = tomllib.loads(out.read_text(encoding="utf-8"))["trees"]
    tree = trees["norway_spruce"]["r07_h20m"]
    assert tree["structure_settings"] == {"grow_nodes": 2}  # notes dropped
    assert (tree["bark_trunk"], tree["bark_branch"]) == (
        "fab_nordic_spruce_detail_bark",
        "fab_nordic_spruce_bark",
    )  # config/pve_calibration.toml's tile pair
    _, findings = tree_catalog.check(out)
    assert any("STALE" in f for f in findings)


def test_a_held_species_carries_its_release_hold(tmp_path):
    growth = tmp_path / "Norway_Spruce_r07_h20m_d27cm_full_growth_data.json"
    growth.write_text("{}")
    plan = _plan(tmp_path / "p", "r07_h20m", growth, instances=10)
    holds = tmp_path / "holds.toml"
    holds.write_text('norway_spruce = "1.2: look verdict failed"\n')
    out = tmp_path / "tree_catalog.toml"

    tree_catalog.build([plan], None, [], out, holds=holds)

    tree = tomllib.loads(out.read_text(encoding="utf-8"))["trees"]["norway_spruce"]
    assert tree["r07_h20m"]["release_hold"] == "1.2: look verdict failed"


def test_a_tree_key_holds_only_that_tree(tmp_path):
    plans = []
    for tid, d in (("r07_h20m", "d23cm"), ("r07_h30m", "d32cm")):
        growth = tmp_path / f"Norway_Spruce_{tid}_{d}_full_growth_data.json"
        growth.write_text("{}")
        plans.append(_plan(tmp_path / tid, tid, growth, instances=10))
    holds = tmp_path / "holds.toml"
    holds.write_text('"norway_spruce.r07_h30m" = "1.2: not in the new ladder"\n')
    out = tmp_path / "tree_catalog.toml"

    tree_catalog.build(plans, None, [], out, holds=holds)

    tree = tomllib.loads(out.read_text(encoding="utf-8"))["trees"]["norway_spruce"]
    assert tree["r07_h30m"]["release_hold"] == "1.2: not in the new ladder"
    assert "release_hold" not in tree["r07_h20m"]


def test_build_writes_a_catalog_index_row_of_each_kind(tmp_path, monkeypatch):
    growth = tmp_path / "forest" / "norway_spruce" / "r07" / (
        "Norway_Spruce_r07_h20m_d27cm_full_growth_data.json"
    )
    growth.parent.mkdir(parents=True)
    growth.write_text("{}")
    plan = _plan(tmp_path / "plan", "r07_h20m", growth)
    twigs = tmp_path / "twigs"
    for tid, kind in (("a", "twig"), ("b", "spray"), ("c", "compound")):
        (twigs / tid).mkdir(parents=True)
        (twigs / tid / "twig.toml").write_text(
            f'id = "{tid}"\nspecies = "norway_spruce"\npart_kind = "{kind}"\n'
            f'source = "megaplants"\nsource_ref = "pack:P/{tid}"\n'
            'licence = "Fab"\nfaces = 10\nstatus = "candidate"\n'
        )
    materials = tmp_path / "materials.toml"
    materials.write_text(
        '[materials.fab_x]\nspecies = "norway_spruce"\nsource = "fab"\n'
        'licence = "Fab Standard License"\ninstance = "/Game/M/MI_fab_x"\n'
    )
    monkeypatch.setattr(tree_catalog, "MATERIAL_CATALOG", materials)
    out = tmp_path / "tree_catalog.toml"

    tree_catalog.build([plan], None, [], out, twigs=twigs, forest=tmp_path / "forest")

    rows = tomllib.loads((tmp_path / "catalog_index.toml").read_text("utf-8"))[
        "components"
    ]
    by_kind = {r["kind"]: r for r in rows}
    kinds = {"structure", "twig", "spray", "compound", "material", "tree"}
    assert set(by_kind) == kinds
    assert by_kind["structure"]["licence"] == "own (Grove growth)"
    assert by_kind["structure"]["species"] == "norway_spruce"
    assert by_kind["compound"]["path"] == "pack:P/c"
    assert by_kind["compound"]["status"] == "candidate"
    assert by_kind["material"]["path"] == "/Game/M/MI_fab_x"
    assert by_kind["tree"]["id"] == "norway_spruce.r07_h20m"
