"""Tests for growpy.pipelines.run_summary."""

import csv

import pytest

from growpy.pipelines.run_summary import (
    _count_assemblies,
    _format_duration,
    generate_run_summary,
)


class TestFormatDuration:
    """Tests for human-readable elapsed-time formatting."""

    @pytest.mark.parametrize(
        "seconds,expected",
        [
            (0, "0s"),
            (45, "45s"),
            (60, "1m00s"),
            (397, "6m37s"),
            (3600, "1h00m00s"),
            (7638, "2h07m18s"),
        ],
    )
    def test_formatting(self, seconds, expected):
        assert _format_duration(seconds) == expected


class TestCountAssemblies:
    """Tests for counting *_full_assembly.usda files under a species dir."""

    def test_missing_dir_returns_zero(self, tmp_path):
        assert _count_assemblies(tmp_path / "nonexistent") == 0

    def test_counts_nested_assemblies(self, tmp_path):
        species_dir = tmp_path / "common_ash"
        (species_dir / "open_grown").mkdir(parents=True)
        (species_dir / "surround").mkdir(parents=True)
        (species_dir / "open_grown" / "a_full_assembly.usda").write_text("x")
        (species_dir / "surround" / "b_full_assembly.usda").write_text("x")
        (species_dir / "surround" / "not_an_assembly.usda").write_text("x")
        assert _count_assemblies(species_dir) == 2


class TestGenerateRunSummary:
    """Tests for the end-to-end run summary generation."""

    def _make_species_output(self, output_dir, std_name, n_assemblies):
        species_dir = output_dir / std_name / "open_grown"
        species_dir.mkdir(parents=True)
        for i in range(n_assemblies):
            (species_dir / f"tree_{i}_full_assembly.usda").write_text("x")

    def test_writes_markdown_and_csv(self, tmp_path):
        self._make_species_output(tmp_path, "european_beech", 6)
        self._make_species_output(tmp_path, "common_ash", 6)

        md_path = generate_run_summary(
            tmp_path,
            ["European Beech", "Common Ash"],
            {"European Beech": 6863.0, "Common Ash": 397.0},
            failed=[],
        )

        assert md_path.exists()
        md_text = md_path.read_text(encoding="utf-8")
        assert "european_beech" in md_text
        assert "common_ash" in md_text
        assert "6" in md_text  # assembly count
        assert "OK" in md_text
        assert "FAILED" not in md_text

        csv_path = tmp_path / "dataset_run_summary.csv"
        assert csv_path.exists()
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert {r["species"] for r in rows} == {"european_beech", "common_ash"}

    def test_failed_species_marked(self, tmp_path):
        self._make_species_output(tmp_path, "sycamore_maple", 4)

        md_path = generate_run_summary(
            tmp_path,
            ["Sycamore Maple"],
            {"Sycamore Maple": 120.0},
            failed=["Sycamore Maple"],
        )

        md_text = md_path.read_text(encoding="utf-8")
        assert "FAILED" in md_text
        assert "sycamore_maple" in md_text

        with open(
            tmp_path / "dataset_run_summary.csv", newline="", encoding="utf-8"
        ) as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["status"] == "FAILED"

    def test_csv_accumulates_across_runs(self, tmp_path):
        self._make_species_output(tmp_path, "common_ash", 6)

        generate_run_summary(tmp_path, ["Common Ash"], {"Common Ash": 397.0}, [])
        generate_run_summary(tmp_path, ["Common Ash"], {"Common Ash": 410.0}, [])

        with open(
            tmp_path / "dataset_run_summary.csv", newline="", encoding="utf-8"
        ) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2

    def test_missing_species_output_dir_counts_zero(self, tmp_path):
        md_path = generate_run_summary(
            tmp_path, ["Wild Cherry"], {"Wild Cherry": 211.0}, []
        )
        md_text = md_path.read_text(encoding="utf-8")
        assert "| wild_cherry | 0 |" in md_text
