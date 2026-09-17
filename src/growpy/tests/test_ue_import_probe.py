"""Tests for growpy.tools.ue_import_probe.

Follows the mocking approach used in test_ue_exec.py: no live UE editor,
no real Remote Execution socket traffic. Batch scripts under test are
minimal fabricated files containing just the resume markers the probe's
regexes look for.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from growpy.tools.ue_import_probe import (
    CATEGORY_CONSOLIDATE,
    CATEGORY_DATATABLE,
    CATEGORY_INSTANCES,
    CATEGORY_MATERIALS,
    CATEGORY_POST_IMPORT,
    CATEGORY_SPECIES,
    CATEGORY_UNKNOWN,
    OrderingError,
    ProbeError,
    _classify_batch,
    _parse_asset_records,
    _parse_requested_labels,
    _parse_summary,
    _read_done_txt,
    main,
    run_import_probe,
    validate_ordering,
)


def _write(tmp_path: Path, name: str, content: str = "pass\n") -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def _cls(tmp_path: Path, name: str) -> str:
    return _classify_batch(tmp_path / name)


class TestClassifyBatch:
    def test_instances(self, tmp_path):
        assert _cls(tmp_path, "import_batch_00_instances.py") == CATEGORY_INSTANCES

    def test_species(self, tmp_path):
        assert _cls(tmp_path, "import_batch_01_european_oak.py") == CATEGORY_SPECIES
        assert _cls(tmp_path, "import_batch_12_norway_spruce.py") == CATEGORY_SPECIES

    def test_materials(self, tmp_path):
        assert _cls(tmp_path, "import_batch_98_materials.py") == CATEGORY_MATERIALS

    def test_consolidate(self, tmp_path):
        assert _cls(tmp_path, "import_batch_99_consolidate.py") == CATEGORY_CONSOLIDATE

    def test_datatable(self, tmp_path):
        assert _cls(tmp_path, "import_batch_100_datatable.py") == CATEGORY_DATATABLE

    def test_post_import(self, tmp_path):
        assert _cls(tmp_path, "growpy_wind_import.py") == CATEGORY_POST_IMPORT
        assert _cls(tmp_path, "growpy_pve_preset_import.py") == CATEGORY_POST_IMPORT
        # Both joined POST_IMPORT_SCRIPTS on 2026-09-04. Voxelize had been
        # generated but never run, which left every imported asset on
        # shape_preservation=NONE; prune removes the SK_*_stems sources.
        assert _cls(tmp_path, "growpy_nanite_voxelize.py") == CATEGORY_POST_IMPORT
        assert _cls(tmp_path, "growpy_prune_intermediates.py") == CATEGORY_POST_IMPORT

    def test_unknown(self, tmp_path):
        assert _cls(tmp_path, "clean_assets.py") == CATEGORY_UNKNOWN


class TestValidateOrdering:
    def test_correct_order_is_clean(self, tmp_path):
        batches = [
            tmp_path / "import_batch_00_instances.py",
            tmp_path / "import_batch_01_oak.py",
            tmp_path / "import_batch_02_spruce.py",
            tmp_path / "import_batch_98_materials.py",
            tmp_path / "import_batch_99_consolidate.py",
            tmp_path / "import_batch_100_datatable.py",
        ]
        assert validate_ordering(batches) == []

    def test_species_before_instances_is_flagged(self, tmp_path):
        batches = [
            tmp_path / "import_batch_01_oak.py",
            tmp_path / "import_batch_00_instances.py",
        ]
        issues = validate_ordering(batches)
        assert any("twig instances" in i for i in issues)

    def test_materials_before_species_is_flagged(self, tmp_path):
        batches = [
            tmp_path / "import_batch_00_instances.py",
            tmp_path / "import_batch_98_materials.py",
            tmp_path / "import_batch_01_oak.py",
        ]
        issues = validate_ordering(batches)
        assert any("materials" in i for i in issues)

    def test_consolidate_before_species_is_flagged(self, tmp_path):
        batches = [
            tmp_path / "import_batch_00_instances.py",
            tmp_path / "import_batch_99_consolidate.py",
            tmp_path / "import_batch_01_oak.py",
        ]
        issues = validate_ordering(batches)
        assert any("consolidate" in i for i in issues)

    def test_datatable_before_materials_is_flagged(self, tmp_path):
        batches = [
            tmp_path / "import_batch_00_instances.py",
            tmp_path / "import_batch_01_oak.py",
            tmp_path / "import_batch_100_datatable.py",
            tmp_path / "import_batch_98_materials.py",
        ]
        issues = validate_ordering(batches)
        assert any(
            "datatable" in i.lower() and "materials" in i.lower() for i in issues
        )

    def test_datatable_before_species_is_flagged(self, tmp_path):
        batches = [
            tmp_path / "import_batch_00_instances.py",
            tmp_path / "import_batch_100_datatable.py",
            tmp_path / "import_batch_01_oak.py",
        ]
        issues = validate_ordering(batches)
        assert any("datatable" in i.lower() for i in issues)

    def test_no_species_no_instances_is_clean(self, tmp_path):
        # A materials-only or datatable-only re-run shouldn't trip the
        # "before species" rules when there's nothing to be before.
        batches = [tmp_path / "import_batch_98_materials.py"]
        assert validate_ordering(batches) == []


class TestParseRequestedLabels:
    def test_extracts_labels(self):
        text = (
            'if "tree_0001" in _completed_files:\n    pass\n'
            'if "tree_0002" in _completed_files:\n    pass\n'
        )
        assert _parse_requested_labels(text) == ["tree_0001", "tree_0002"]

    def test_no_labels(self):
        assert _parse_requested_labels("print('hello')\n") == []


class TestReadDoneTxt:
    def test_reads_sibling_done_file(self, tmp_path):
        batch = _write(tmp_path, "import_batch_01_oak.py")
        _write(tmp_path, "import_batch_01_oak_done.txt", "tree_0001\ntree_0002\n\n")
        assert _read_done_txt(batch) == ["tree_0001", "tree_0002"]

    def test_missing_done_file_returns_empty(self, tmp_path):
        batch = _write(tmp_path, "import_batch_01_oak.py")
        assert _read_done_txt(batch) == []


class TestParseSummary:
    def test_matches_summary_line(self):
        text = "Batch 'oak (3 trees)' complete: 3 imported, 0 skipped, 0 failed"
        assert _parse_summary(text) == (3, 0, 0)

    def test_no_match_returns_none_triplet(self):
        assert _parse_summary("nothing here") == (None, None, None)


class TestParseAssetRecords:
    """Per-asset records are what separate a build from a skip; the batch
    summary line alone cannot (XRFF-323)."""

    def test_parses_outcome_seconds_and_label(self):
        text = (
            "  [ASSET] outcome=imported seconds=3671.8 label=Silver_Fir_h15m\n"
            "  [ASSET] outcome=skipped seconds=0.0 label=Silver_Fir_h05m\n"
        )
        assert _parse_asset_records(text) == [
            {
                "outcome": "imported",
                "seconds": 3671.8,
                "label": "Silver_Fir_h15m",
            },
            {"outcome": "skipped", "seconds": 0.0, "label": "Silver_Fir_h05m"},
        ]

    def test_separates_a_skipped_batch_from_a_fast_build(self):
        skipped = "\n".join(
            f"  [ASSET] outcome=skipped seconds=0.0 label=t{i}" for i in range(3)
        )
        records = _parse_asset_records(skipped)
        assert len(records) == 3
        assert not [r for r in records if r["outcome"] == "imported"]

    def test_no_records_returns_empty(self):
        assert _parse_asset_records("Batch 'x' complete: 3 imported") == []


class TestRunImportProbeSetup:
    def test_missing_dir_raises(self, tmp_path):
        with pytest.raises(ProbeError):
            run_import_probe(tmp_path / "does_not_exist")

    def test_empty_dir_raises(self, tmp_path):
        with pytest.raises(ProbeError):
            run_import_probe(tmp_path)

    def test_batches_override_missing_file_raises(self, tmp_path):
        _write(tmp_path, "import_batch_00_instances.py")
        with pytest.raises(ProbeError):
            run_import_probe(
                tmp_path, batches_override=["does_not_exist.py"], dry_run=True
            )

    def test_dry_run_reports_ordering_issues_without_raising(self, tmp_path):
        # Auto-discovery always sorts batches into valid numeric order (00 <
        # 01-97 < 98 < 99 < 100), so a real violation can only be exercised
        # via an explicit (caller-supplied) override -- exactly the case
        # validate_ordering exists to guard.
        _write(tmp_path, "import_batch_98_materials.py")
        _write(tmp_path, "import_batch_01_oak.py")
        record = run_import_probe(
            tmp_path,
            batches_override=[
                "import_batch_98_materials.py",
                "import_batch_01_oak.py",
            ],
            dry_run=True,
        )
        assert record["dry_run"] is True
        assert record["plan"]["ordering_issues"]

    def test_dry_run_clean_order_reports_no_issues(self, tmp_path):
        _write(tmp_path, "import_batch_00_instances.py")
        _write(tmp_path, "import_batch_01_oak.py")
        record = run_import_probe(tmp_path, dry_run=True)
        assert record["plan"]["ordering_issues"] == []
        assert record["plan"]["batch_count"] == 2

    def test_non_dry_run_ordering_violation_raises(self, tmp_path):
        _write(tmp_path, "import_batch_98_materials.py")
        _write(tmp_path, "import_batch_01_oak.py")
        with pytest.raises(OrderingError):
            run_import_probe(
                tmp_path,
                batches_override=[
                "import_batch_98_materials.py",
                "import_batch_01_oak.py",
            ],
                dry_run=False,
            )

    def test_watchdog_enabled_without_config_raises(self, tmp_path):
        _write(tmp_path, "import_batch_00_instances.py")
        with pytest.raises(ProbeError):
            run_import_probe(tmp_path, dry_run=False, restart_ram_limit=82.0)

    def test_watchdog_disabled_skips_config_check(self, tmp_path):
        _write(tmp_path, "import_batch_00_instances.py")
        with patch(
            "growpy.tools.ue_import_probe._run_batch_instrumented",
            return_value=(True, False, [], ""),
        ):
            record = run_import_probe(tmp_path, dry_run=False, restart_ram_limit=0)
        assert record["dry_run"] is False
        assert len(record["results"]) == 1


class TestRunImportProbeExecution:
    def _make_species_batch(self, tmp_path, name="import_batch_01_oak.py"):
        text = (
            'if "European_Oak_0001_assembly" in _completed_files:\n    pass\n'
            'if "European_Oak_0002_assembly" in _completed_files:\n    pass\n'
        )
        return _write(tmp_path, name, text)

    def test_full_success_reconciles_done_txt(self, tmp_path):
        batch = self._make_species_batch(tmp_path)
        _write(
            tmp_path,
            "import_batch_01_oak_done.txt",
            "European_Oak_0001_assembly\nEuropean_Oak_0002_assembly\n",
        )
        output_text = (
            "Batch 'oak (2 trees)' complete: 2 imported, 0 skipped, 0 failed"
        )
        with patch(
            "growpy.tools.ue_import_probe._run_batch_instrumented",
            return_value=(True, False, [], output_text),
        ):
            record = run_import_probe(
                tmp_path,
                batches_override=[batch.name],
                dry_run=False,
                restart_ram_limit=0,
            )
        r = record["results"][0]
        assert r["remote_exec_success"] is True
        assert r["requested_count"] == 2
        assert r["completed_count"] == 2
        assert r["missing_labels"] == []
        assert r["ue_side_failure_suspected"] is False
        assert r["summary_imported"] == 2

    def test_missing_asset_in_done_txt_flags_ue_side_failure(self, tmp_path):
        batch = self._make_species_batch(tmp_path)
        _write(
            tmp_path,
            "import_batch_01_oak_done.txt",
            "European_Oak_0001_assembly\n",  # second asset silently missing
        )
        summary = "Batch 'oak (2 trees)' complete: 2 imported, 0 skipped, 0 failed"
        with patch(
            "growpy.tools.ue_import_probe._run_batch_instrumented",
            return_value=(True, False, [], summary),
        ):
            record = run_import_probe(
                tmp_path,
                batches_override=[batch.name],
                dry_run=False,
                restart_ram_limit=0,
            )
        r = record["results"][0]
        assert r["missing_labels"] == ["European_Oak_0002_assembly"]
        assert r["ue_side_failure_suspected"] is True

    def test_materials_missing_parent_material_is_flagged(self, tmp_path):
        batch = _write(tmp_path, "import_batch_98_materials.py")
        output_text = (
            "Parent material not found: /Game/Templates/MA_Foliage_Trees "
            "-- aborting."
        )
        with patch(
            "growpy.tools.ue_import_probe._run_batch_instrumented",
            return_value=(True, False, [], output_text),
        ):
            record = run_import_probe(
                tmp_path,
                batches_override=[batch.name],
                dry_run=False,
                restart_ram_limit=0,
            )
        r = record["results"][0]
        assert r["ue_side_failure_suspected"] is True
        assert any("Parent material not found" in n for n in r["notes"])

    def test_restart_events_recorded(self, tmp_path):
        batch = _write(tmp_path, "import_batch_00_instances.py")
        restart_events = [
            {
                "reason": "proactive_ram_limit",
                "attempt": 1,
                "at": "2026-01-01T00:00:00+00:00",
            }
        ]
        with patch(
            "growpy.tools.ue_import_probe._run_batch_instrumented",
            return_value=(True, False, restart_events, ""),
        ):
            record = run_import_probe(
                tmp_path,
                batches_override=[batch.name],
                dry_run=False,
                restart_ram_limit=0,
            )
        r = record["results"][0]
        assert r["restart_count"] == 1
        assert r["restarts"][0]["reason"] == "proactive_ram_limit"

    def test_aborted_batch_stops_remaining(self, tmp_path):
        b1 = _write(tmp_path, "import_batch_00_instances.py")
        _write(tmp_path, "import_batch_01_oak.py")
        with patch(
            "growpy.tools.ue_import_probe._run_batch_instrumented",
            return_value=(False, True, [], ""),
        ):
            record = run_import_probe(
                tmp_path,
                batches_override=[b1.name, "import_batch_01_oak.py"],
                dry_run=False,
                restart_ram_limit=0,
            )
        assert len(record["results"]) == 1
        assert record["results"][0]["aborted_memory"] is True


class TestMain:
    def test_missing_target_errors(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["growpy-ue-import-probe"])
        with pytest.raises(SystemExit):
            main()

    def test_nonexistent_dir_exits_1(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "sys.argv", ["growpy-ue-import-probe", str(tmp_path / "nope")]
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_dry_run_exits_0(self, monkeypatch, tmp_path):
        _write(tmp_path, "import_batch_00_instances.py")
        monkeypatch.setattr(
            "sys.argv", ["growpy-ue-import-probe", str(tmp_path), "--dry-run"]
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_ordering_violation_exits_3(self, monkeypatch, tmp_path):
        _write(tmp_path, "import_batch_98_materials.py")
        _write(tmp_path, "import_batch_01_oak.py")
        monkeypatch.setattr(
            "sys.argv",
            [
                "growpy-ue-import-probe",
                str(tmp_path),
                "--batches",
                "import_batch_98_materials.py,import_batch_01_oak.py",
                # Ordering is checked before the watchdog runs; keep the
                # watchdog disabled so this test isolates the ordering
                # exit code (3) from the separate config-validation exit
                # code (2), covered by test_missing_watchdog_config_exits_2.
                "--restart-ram-limit",
                "0",
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 3

    def test_missing_watchdog_config_exits_2(self, monkeypatch, tmp_path):
        _write(tmp_path, "import_batch_00_instances.py")
        monkeypatch.setattr(
            "growpy.config.core.get_config",
            lambda: type("C", (), {"unreal_editor_exe": "", "unreal_uproject": ""})(),
        )
        monkeypatch.setattr(
            "sys.argv", ["growpy-ue-import-probe", str(tmp_path)]
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

    def test_dry_run_writes_json(self, monkeypatch, tmp_path):
        _write(tmp_path, "import_batch_00_instances.py")
        json_out = tmp_path / "out.json"
        monkeypatch.setattr(
            "sys.argv",
            [
                "growpy-ue-import-probe",
                str(tmp_path),
                "--dry-run",
                "--json",
                str(json_out),
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        assert json_out.is_file()
