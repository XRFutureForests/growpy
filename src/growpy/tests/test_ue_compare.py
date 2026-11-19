"""Tests for growpy.tools.ue_compare (no editor) and config/compare_sets.toml."""

from __future__ import annotations

from pathlib import Path

import pytest

from growpy.tools import ue_compare, ue_session
from growpy.tools.ue_compare import (
    SETS_FILE,
    CompareJob,
    load_sets,
    resolve_set,
    session_steps,
)

CAT = "/Game/Generated/Trees/Catalog/"
MPPINE = (
    "/Game/Megaplant_Library/Tree_Baltic_Pine/Tree_Baltic_Pine_01/Tree_Baltic_Pine_01_"
)
H = ("r07_h20m", "r10_h10m", "r10_h20m", "r10_h30m")


def _assets(name, **kw):
    return [(r.label, [t.asset for t in r.trees]) for r in resolve_set(name, **kw).rows]


def _write(tmp_path, body):
    path = tmp_path / "sets.toml"
    path.write_text(body, encoding="utf-8")
    return path


ONE = """
[compare]
level = "/Game/L"
[compare.sets.s]
rows = [ {{ label = "ours", {row} }} ]
"""


class TestShippedSets:
    def test_every_set_resolves_and_the_old_ones_are_all_there(self, tmp_path):
        variants = tmp_path / "variants.txt"
        variants.write_text(
            "v1 /G/PVG /Game/Developers/TwigTune/v1/Catalog/x/SK_X_r07\n"
        )
        sets = load_sets()["sets"]
        assert set(sets) >= {
            "catalog", "beech", "beech_e99", "beech_cut", "beech_floor", "beech12",
            "pine12", "douglas12", "pinecount", "pinemass", "pinepad", "barkzone",
            "e113fol", "e124", "e124lad", "barkzone3", "fleck", "mpbroadleaf",
            "dfyoung", "xrff686",
        }  # fmt: skip
        for name in sets:
            cset = resolve_set(name, variants=variants, params={"variant": "1"})
            assert cset.rows and all(
                r.trees or "twig test" in r.label for r in cset.rows
            )

    def test_spot_checks_against_the_old_if_blocks(self):
        # build_compare_conifers.py, 2026-11-19: the rows as its code built them
        assert _assets("pinecount")[0] == (
            "S12 pine 1.2 shipped",
            [CAT + "scots_pine/SK_ScotsPine_" + t for t in H],
        )
        assert _assets("pinemass")[2] == (
            "TIP40 pine twig mass",
            [
                "/Game/PVE_PINEMASS/tip40/Catalog/scots_pine/SK_ScotsPine_" + t
                for t in H
            ],
        )
        assert _assets("beech_floor")[3] == (
            "FLOOR22 cut 0.20 + crown floor 0.22",
            [
                "/Game/PVE_CUT/f020_cap25_floor22_B/Catalog/european_beech/SK_EuropeanBeech_r07_h20m",
                "/Game/PVE_CUT/f020_cap25_floor22_B/Catalog/european_beech/SK_EuropeanBeech_r10_h20m",
            ],
        )
        assert [label for label, _ in _assets("barkzone")][1:5] == [
            "BZ125 two-bark blend bh125",
            "BZ150 two-bark blend bh150",
            "BZ175 two-bark blend bh175",
            "BZ150MP two-bark blend bh150mp",
        ]
        assert _assets("barkzone")[1][1] == [
            "/Game/PVE_PINEPAD/barkzone/SK_ScotsPine_r10_h20m_bh125",
            "/Game/PVE_PINEPAD/barkzone/SK_ScotsPine_r10_h30m_bh125",
        ]
        assert _assets("barkzone3")[3] == (
            "pine megaplants",
            [MPPINE + "A", MPPINE + "D"],
        )
        dfy = _assets("dfyoung")
        assert [label for label, _ in dfy] == [
            "S07 shipped 1.2 B2 (fullness 1.2)", "A07 dfy24", "B07 dfy36", "C07 dfy24r0",  # noqa: E501
            "S10 shipped 1.2 B2 (fullness 1.2)", "A10 dfy24", "B10 dfy36", "C10 dfy24r0",  # noqa: E501
        ]  # fmt: skip
        assert (
            dfy[6][1][3]
            == "/Game/PVE_PINEPAD/dfy36/Catalog/douglas_fir/SK_DouglasFir_r10_h20m"
        )
        assert _assets("xrff686")[14] == (
            "SPB2 stronger ladder scots_pine",
            [
                "/Game/PVE_686/lad2_scots_pine/Catalog/scots_pine/SK_ScotsPine_r07_h10m",
                "/Game/PVE_686/lad2_scots_pine/Catalog/scots_pine/SK_ScotsPine_r07_h20m",
            ],
        )
        e113 = _assets("e113fol")[0][1]
        assert e113[2:] == [MPPINE + "A", MPPINE + "B"]

    def test_set_flags_and_the_forest_neighbours(self):
        assert (
            resolve_set("pinemass").assembly_tris
            and resolve_set("pinepad").assembly_tris
        )
        assert not resolve_set("pine12").assembly_tris
        e124 = resolve_set("e124")
        assert [r.optional for r in e124.rows] == [
            False,
            False,
            False,
            True,
        ]  # MEDU arm
        assert e124.neighbours[0] == (
            CAT + "douglas_fir/SK_DouglasFir_r10_h25m",
            1200.0,
            -450.0,
        )
        assert len(e124.neighbours) == 4
        assert resolve_set("fleck", params={"variant": "3"}).rows[0].label == (
            "F3 needle-fleck variant 3"
        )
        assert resolve_set("fleck", params={"variant": "3"}).contexts == (
            "light",
            "dark",
            "forest",
        )
        assert resolve_set("pine12").contexts == ("light",)

    def test_tags_are_first_words_and_twig_tune_arms(self, tmp_path):
        variants = tmp_path / "variants.txt"
        variants.write_text(
            "a /G/x /Game/Developers/TwigTune/arm7/Catalog/scots_pine/SK_ScotsPine_r07_h20m\n"  # noqa: E501
        )
        rows = resolve_set("catalog", variants=variants).rows
        assert rows[0].trees[0].tag == "ours"
        pine_test = [r for r in rows if r.label == "pine twig test"][0]
        assert [t.tag for t in pine_test.trees] == ["arm7"]

    def test_a_variants_row_without_the_file_is_left_out_and_named(self):
        cset = resolve_set("catalog")
        assert "spruce twig test" not in [r.label for r in cset.rows]
        assert any("spruce twig test" in n for n in cset.notes)

    def test_no_machine_paths_in_the_sets(self):
        text = SETS_FILE.read_text(encoding="utf-8")
        assert ":/" not in text and ":\\" not in text


class TestValidation:
    @pytest.mark.parametrize(
        ("row", "match"),
        [
            ('assets = ["/Game/A"], colour = "red"', "unknown key"),
            ('pattern = "/Game/A_{cell}"', "pattern needs"),
            ('pattern = "/Game/A", cells = ["1"]', "pattern needs"),
            (
                'assets = ["/Game/A"], pattern = "/Game/B_{cell}", cells = ["1"]',
                "exactly one",
            ),
            ("tag = 'x'", "exactly one"),
            ("assets = []", "empty assets"),
            ('assets = ["X:/not/content/A"]', "content path"),
        ],
    )
    def test_a_bad_row_is_refused(self, tmp_path, row, match):
        with pytest.raises(ValueError, match=match):
            load_sets(_write(tmp_path, ONE.format(row=row)))

    def test_empty_rows_an_unknown_set_key_or_context_are_refused(self, tmp_path):
        body = '[compare]\nlevel = "/Game/L"\n[compare.sets.s]\nrows = []\n'
        with pytest.raises(ValueError, match="no rows"):
            load_sets(_write(tmp_path, body))
        body = ONE.format(row='assets = ["/Game/A"]') + 'contexts = ["dusk"]\n'
        with pytest.raises(ValueError, match="unknown context"):
            load_sets(_write(tmp_path, body))
        body = ONE.format(row='assets = ["/Game/A"]').replace(
            "[compare.sets.s]", "[compare.sets.s]\nwind = true"
        )
        with pytest.raises(ValueError, match="unknown key"):
            load_sets(_write(tmp_path, body))
        with pytest.raises(ValueError, match="one \\[compare\\] table"):
            load_sets(_write(tmp_path, "[sets.s]\nrows = []\n"))

    def test_a_tag_collision_is_refused(self, tmp_path):
        # two rows whose first word is "pine" and that hold the same mesh: one actor label  # noqa: E501
        body = (
            '[compare]\nlevel = "/Game/L"\n[compare.sets.s]\nrows = [\n'
            '  { label = "pine shipped", assets = ["/Game/C/SK_ScotsPine_r07_h20m"] },\n'  # noqa: E501
            '  { label = "pine again", assets = ["/Game/D/SK_ScotsPine_r07_h20m"] },\n]\n'  # noqa: E501
        )
        path = _write(tmp_path, body)
        with pytest.raises(ValueError, match="tag collision"):
            resolve_set("s", path)
        fixed = body.replace(
            'label = "pine again"', 'label = "pine again", tag = "pine2"'
        )
        assert len(resolve_set("s", _write(tmp_path, fixed)).rows) == 2

    def test_an_unknown_set_or_a_missing_param_is_refused(self):
        with pytest.raises(ValueError, match="no set"):
            resolve_set("nope")
        with pytest.raises(ValueError, match="--param variant"):
            resolve_set("fleck")


class TestJob:
    def test_the_job_round_trips(self, tmp_path):
        cset = resolve_set("e124")
        job = CompareJob.for_set(
            cset, SETS_FILE, tmp_path / "out", ["light", "forest"],
            crown_base={"SK_ScotsPine_r10_h20m": 9.5}, sweep=[["ours", "1", "4"]],
        )  # fmt: skip
        path = job.write(tmp_path / "out" / "compare_job.json")
        back = CompareJob.read(path)
        assert back == job
        assert back.rows[3] == {
            "label": "MEDU crown base 11.5 m, no cap",
            "optional": True,
            "trees": [
                {
                    "asset": "/Game/PVE_PINEPAD/mpparts_cbmedu_e113/Catalog/scots_pine/SK_ScotsPine_r07_h20m",  # noqa: E501
                    "tag": "MEDU",
                },
                {
                    "asset": "/Game/PVE_PINEPAD/mpparts_cbmedu_e113/Catalog/scots_pine/SK_ScotsPine_r10_h20m",  # noqa: E501
                    "tag": "MEDU",
                },
            ],
        }
        assert Path(back.out).is_absolute() and back.neighbours[0][1] == 1200.0


class TestSessionSteps:
    def test_build_then_per_context_backdrop_and_capture_then_save(self, tmp_path):
        out = tmp_path / "shots"
        job_path = out / "compare_job.json"
        argv = session_steps(job_path, out, ["light", "forest"])
        project = tmp_path / "Twin.uproject"
        project.write_text("{}")
        engine = tmp_path / "UnrealEditor.exe"
        engine.write_text("")
        args = ue_session.parse_args(
            ["--project", str(project), "--engine", str(engine), *argv], env={}
        )
        assert [(s.kind, Path(s.target).name, s.done) for s in args.steps] == [
            ("run", "1_level.py", None),
            ("run", "2_light_context.py", None),
            ("until", "2_light_capture.py", out / "light" / "DONE"),
            ("run", "3_forest_context.py", None),
            ("until", "3_forest_capture.py", out / "forest" / "DONE"),
            ("run", "4_save.py", None),
        ]
        assert [s.timeout for s in args.steps] == [
            1500.0,
            600.0,
            1200.0,
            600.0,
            1200.0,
            600.0,
        ]

    def test_each_stub_runs_its_packaged_script_with_the_job_and_mode(self, tmp_path):
        out = tmp_path / "shots"
        job_path = out / "compare_job.json"
        session_steps(job_path, out, ["dark"])
        stub = (out / "steps" / "2_dark_capture.py").read_text(encoding="utf-8")
        compile(stub, "stub", "exec")
        assert repr(str(ue_compare.UE_SCRIPTS / "compare_capture.py")) in stub
        assert repr({"JOB": str(job_path), "MODE": "dark"}) in stub
        level = (out / "steps" / "1_level.py").read_text(encoding="utf-8")
        assert "'MODE'" not in level and "compare_level.py" in level
        save = (out / "steps" / "3_save.py").read_text(encoding="utf-8")
        assert "'MODE': 'save'" in save and "compare_context.py" in save

    def test_the_packaged_editor_scripts_compile(self):
        for name in ("compare_level.py", "compare_context.py", "compare_capture.py"):
            source = (ue_compare.UE_SCRIPTS / name).read_text(encoding="utf-8")
            compile(source, name, "exec")
            assert ":/" not in source and ":\\\\" not in source  # no machine paths

    def test_dry_run_writes_the_job_and_starts_no_editor(
        self, tmp_path, capsys, monkeypatch
    ):
        monkeypatch.setattr(
            ue_session, "main", lambda argv: pytest.fail("no session in a dry run")
        )
        rc = ue_compare.main(["pine12", "--out", str(tmp_path / "o"), "--dry-run"])
        assert rc == 0
        assert CompareJob.read(tmp_path / "o" / "compare_job.json").set == "pine12"
        out = capsys.readouterr().out
        assert "set pine12: 3 row(s), 16 tree(s), contexts light" in out
        assert "--run-until-done" in out

    def test_a_session_run_prints_the_shot_folder_per_context(
        self, tmp_path, capsys, monkeypatch
    ):
        seen = []

        def fake_session(argv):
            seen.append(argv)
            (tmp_path / "o" / "light").mkdir(parents=True)
            (tmp_path / "o" / "light" / "DONE").write_text("16")
            return 0

        monkeypatch.setattr(ue_session, "main", fake_session)
        rc = ue_compare.main(
            ["pine12", "--out", str(tmp_path / "o"), "--contexts", "light", "dark",
             "--lock", "slot"]
        )  # fmt: skip
        assert rc == 0
        assert seen[0][:2] == ["--lock", "slot"]
        out = capsys.readouterr().out
        assert f"light shots -> {tmp_path / 'o' / 'light'} (16)" in out
        assert f"dark shots -> {tmp_path / 'o' / 'dark'} (no DONE)" in out
