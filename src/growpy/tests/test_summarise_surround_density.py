"""Tests for growpy.tools.summarise_surround_density -- the seed-aware gate.

Pins the three behaviours XRFF-448 asked for: rows are grouped by seed, one
inverted replicate fails the density, and a single-seed broadleaf arm cannot
PASS on the crown-ø axis. Plus the crown-base axis, whose direction is the
reverse of the other two (the tight shell must sit HIGHER).
"""

import csv
import sys

import pytest

from growpy.tools import summarise_surround_density as ssd

FIELDS = ["run_utc", "species", "density", "seed", "radius", "stage", "height_m",
          "dbh_cm", "crown_diameter_m", "crown_base_m", "crown_ratio",
          "crown_d_over_h", "n_twigs", "twigs_per_m3", "leaf_area_m2", "lai",
          "in_sharma_band", "elapsed_s", "status"]


def _row(species, density, seed, radius, stage, *, dbh, crown, base):
    height = float(stage[1:3])
    return {
        "run_utc": "2026-09-15T00:00:00", "species": species,
        "density": density, "seed": seed, "radius": radius, "stage": stage,
        "height_m": height, "dbh_cm": dbh, "crown_diameter_m": crown,
        "crown_base_m": base, "crown_ratio": round(1 - base / height, 3),
        "crown_d_over_h": round(crown / height, 3), "n_twigs": 1000,
        "twigs_per_m3": 10.0, "leaf_area_m2": 1.0, "lai": 1.0,
        "in_sharma_band": "", "elapsed_s": 1, "status": "OK",
    }


def _write(work_dir, rows):
    work_dir.mkdir(parents=True, exist_ok=True)
    path = work_dir / "sweep_results.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def _arm(species, density, seed, *, dc, db):
    """One arm at h10/h15; `dc`/`db` = r16 minus r08 on crown ø / crown base."""
    rows = []
    for stage, dbh, crown, base in (("h10m", 10, 4.0, 3.0), ("h15m", 15, 6.0, 5.0)):
        rows.append(_row(species, density, seed, 8, stage,
                         dbh=dbh, crown=crown, base=base))
        rows.append(_row(species, density, seed, 16, stage,
                         dbh=dbh + 2, crown=crown + dc, base=base + db))
    return rows


def _run(monkeypatch, capsys, work_dir, *argv):
    monkeypatch.setattr(sys, "argv", ["summarise", "--work-dir", str(work_dir),
                                      "--stage", "h15m", *argv])
    assert ssd.main() == 0
    out = capsys.readouterr().out
    # Drop the fixed legend so assertions read only the per-species body.
    return "\n".join(ln for ln in out.splitlines()
                     if not ln.startswith(("NEEDS-SEEDS", "A FAIL", "A lowercase")))


class TestRadiusOrdering:
    def test_auto_axis_is_crown_base_for_every_habit(self):
        assert ssd.gate_axis("silver_birch") == ssd.GATE_BASE
        assert ssd.gate_axis("norway_spruce") == ssd.GATE_BASE
        # The pre-2026-09-15 split survives under its own name.
        assert ssd.gate_axis("silver_birch", "habit")[0] == "dbh_cm"
        assert ssd.gate_axis("norway_spruce", "habit")[0] == "crown_diameter_m"

    def test_direction_reverses_the_expected_order(self):
        cells = {"8": {"crown_base_m": "5.0", "n_twigs": "1"},
                 "16": {"crown_base_m": "3.0", "n_twigs": "1"}}
        # Crown base: the tight shell must sit HIGHER, so r08 > r16 is ok ...
        assert ssd.radius_ordering(cells, "crown_base_m", 0.5, -1)[0] == "ok"
        # ... and the same numbers read as an inversion on a +1 axis.
        assert ssd.radius_ordering(cells, "crown_base_m", 0.5, 1)[0] == "INVERTED"

    def test_spread_is_always_r16_minus_r08(self):
        cells = {"8": {"crown_base_m": "5.0", "n_twigs": "1"},
                 "16": {"crown_base_m": "3.0", "n_twigs": "1"}}
        _, _, spread = ssd.radius_ordering(cells, "crown_base_m", 0.5, -1)
        assert spread == pytest.approx(-2.0)


class TestSeedAwareGate:
    def test_one_inverted_seed_fails_the_density(self, tmp_path, monkeypatch, capsys):
        rows = (_arm("silver_birch", 0.7, 512, dc=+2.0, db=-1.0)
                + _arm("silver_birch", 0.7, 999, dc=-1.5, db=-1.0)
                + _arm("silver_birch", 0.7, 7, dc=+1.0, db=-1.0))
        _write(tmp_path, rows)
        out = _run(monkeypatch, capsys, tmp_path, "--gate-axis", "crown")
        line = next(ln for ln in out.splitlines() if ln.strip().startswith("0.7"))
        assert " 3 " in line and "FAIL" in line
        assert "seed 999" in out and "INVERTED" in out
        assert "NO arm passes" in out

    def test_single_seed_broadleaf_cannot_pass_on_crown_axis(
            self, tmp_path, monkeypatch, capsys):
        _write(tmp_path, _arm("silver_birch", 0.7, 512, dc=+2.0, db=-1.0))
        out = _run(monkeypatch, capsys, tmp_path, "--gate-axis", "crown")
        assert "PASS/n=1" in out
        assert "NO arm passes" in out
        assert "were not ranked: silver_birch 0.7" in out

    def test_single_seed_conifer_still_ranks_on_crown_axis(
            self, tmp_path, monkeypatch, capsys):
        _write(tmp_path, _arm("norway_spruce", 0.95, 512, dc=+0.5, db=-2.0))
        out = _run(monkeypatch, capsys, tmp_path, "--gate-axis", "crown")
        assert "-> 0.95" in out and "1 seed(s)" in out

    def test_min_seeds_applies_to_every_species(self, tmp_path, monkeypatch, capsys):
        _write(tmp_path, _arm("norway_spruce", 0.95, 512, dc=+0.5, db=-2.0))
        out = _run(monkeypatch, capsys, tmp_path,
                   "--gate-axis", "base", "--min-seeds", "2")
        assert "PASS/n=1" in out and "NO arm passes" in out

    def test_base_axis_passes_where_crown_flips(self, tmp_path, monkeypatch, capsys):
        # The birch pattern: crown ø flips sign across seeds, crown base agrees.
        rows = (_arm("silver_birch", 0.7, 512, dc=+2.0, db=-1.0)
                + _arm("silver_birch", 0.7, 999, dc=-1.5, db=-2.5)
                + _arm("silver_birch", 0.7, 7, dc=+1.0, db=-0.7))
        _write(tmp_path, rows)
        out = _run(monkeypatch, capsys, tmp_path, "--gate-axis", "base")
        assert "-> 0.7" in out and "3 seed(s)" in out
        assert "INVERTED" not in out

    def test_ratio_is_the_mean_over_seeds_with_its_range(
            self, tmp_path, monkeypatch, capsys):
        rows = (_arm("silver_birch", 0.7, 512, dc=+1.0, db=-1.0)
                + _arm("silver_birch", 0.7, 999, dc=+1.0, db=-1.0))
        # Both seeds share crown_base 5.0 at h15 on r08 -> ratio 1 - 5/15 = 0.667.
        _write(tmp_path, rows)
        out = _run(monkeypatch, capsys, tmp_path, "--gate-axis", "base")
        assert "0.67 (0.67-0.67)" in out

    def test_max_stage_ignores_cells_above_the_cap(self, tmp_path, monkeypatch, capsys):
        # h10/h15 correct on the base axis, h20 inverted (the shell inside a
        # mature broadleaf crown, A110) -- a stage the h15 catalog never exports.
        rows = _arm("european_beech", 0.75, 512, dc=+1.0, db=-2.0)
        rows.append(_row("european_beech", 0.75, 512, 8, "h20m",
                         dbh=28, crown=20.0, base=4.5))
        rows.append(_row("european_beech", 0.75, 512, 16, "h20m",
                         dbh=38, crown=18.0, base=9.0))
        _write(tmp_path, rows)
        out = _run(monkeypatch, capsys, tmp_path, "--gate-axis", "base")
        assert "h20m:INVERTED" in out and "FAIL" in out
        out = _run(monkeypatch, capsys, tmp_path, "--gate-axis", "base",
                   "--max-stage", "h15m")
        assert "INVERTED" not in out and "-> 0.75" in out

    def test_wall_warns_when_crown_radius_exceeds_shell_distance(
            self, tmp_path, monkeypatch, capsys):
        rows = _arm("common_ash", 0.75, 512, dc=+0.5, db=-1.0)
        # r08 h15 crown diameter 18 m -> radius 9 m, past an 8 m wall.
        for r in rows:
            if r["radius"] == 8 and r["stage"] == "h15m":
                r["crown_diameter_m"] = 18.0
        _write(tmp_path, rows)
        out = _run(monkeypatch, capsys, tmp_path, "--gate-axis", "base")
        assert "h15m:WALL(r8 radius 9.0>8)" in out
        assert "-> 0.75" in out  # a warning, not a gate failure
