"""Measurement probe wrapping ``growpy-ue-exec`` batch imports.

Runs the same ``import_batch_*.py`` sequence that ``growpy.tools.ue_exec``
runs, but instead of only logging progress it emits a structured JSON
measurement record per batch: wall-clock duration, peak RAM/VRAM sampled
during the (blocking) remote-exec call, watchdog restart count/reason, and
a best-effort reconciliation between what a batch *requested* (parsed from
the generated script's per-file resume markers) and what it actually
*completed* (parsed from the batch's ``done.txt`` progress file and its
final summary line).

This module deliberately reuses ue_exec's internals (``_RamWatchdog``,
``_ue_alive``, ``_restart_ue``, ``_discover_batch_scripts``) and
``ue_remote.run_file`` directly, rather than reimplementing the Remote
Execution protocol or the watchdog/restart state machine.

Ordering matters for GrowPy's generated batches (see
docs/guides/unreal-import.md): the shared twig ``Instances/`` batch must
run before any species batch, species batches must finish before the
materials batch, and materials must finish before the DataTable batch.
:func:`validate_ordering` checks this and the probe refuses to execute
(``OrderingError``) rather than silently running batches out of order.

IMPORTANT -- what a UE-side failure looks like here, and what stays
invisible:

* ``ue_exec``/Remote Execution can only tell you the script was delivered
  and returned without raising. A per-file import failure inside UE is
  visible to this probe only if (a) the generated batch script's own
  ``imported_count``/``failed_count`` bookkeeping surfaces in the final
  "Batch complete: N imported, M skipped, K failed" print (captured via
  the remote-exec response's stdout capture), or (b) the requested label
  never lands in ``done.txt`` (see ``missing_labels`` below).
* ``unreal.log_warning``/``unreal.log_error`` calls (used throughout the
  generated scripts for per-slot/per-parameter failures, e.g. in
  ``unreal_material_script.py``) go to UE's Output Log. Whether they are
  also mirrored into the remote-exec response's captured output is not
  guaranteed by the protocol (only ``print()``/``unreal.log()`` during
  unattended exec are documented to be captured) -- this probe does not
  assume they are, and does not claim coverage of anything that only
  reaches Output Log.
* Visual/geometric correctness of an imported mesh (e.g. a valid-looking
  but wrong Nanite build) is invisible to this probe entirely -- it only
  checks "did an asset get recorded as imported", not "does it look
  right". That is exactly the gap :mod:`growpy.tools.ue_viewport_probe`
  exists to cover.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("growpy.ue_import_probe")

# Re-exported/reused from ue_exec rather than reimplemented.
from growpy.tools.ue_exec import (  # noqa: E402
    BATCH_PATTERN,
    POST_IMPORT_SCRIPTS,
    _discover_batch_scripts,
)
from growpy.utils.vram import query_gpu_vram as _get_gpu_vram  # noqa: E402
from growpy.utils.vram import query_system_ram as _get_system_ram  # noqa: E402

# Per-file resume marker emitted by unreal_scripts._build_import_block for
# every asset in a batch: `if "<label>" in _completed_files:`. Reused here
# to recover "what this batch was asked to import" without re-deriving it
# from the forest output directory.
_LABEL_PATTERN = re.compile(r'if "([^"]+)" in _completed_files:')

# Final summary line printed by _write_batch_script's generated content.
_SUMMARY_PATTERN = re.compile(
    r"Batch '.*?' complete: (\d+) imported, (\d+) skipped, (\d+) failed"
)

# Final summary line printed by unreal_material_script._build_material_script.
_MATERIALS_SUMMARY_PATTERN = re.compile(
    r"Material assignment complete: (\d+) meshes updated, (\d+) skipped"
)

_MATERIALS_PREREQ_MARKER = "Parent material not found"
_DATATABLE_PREREQ_MARKER = "PREREQUISITE: ST_TreeCatalogEntry struct not found"

# --- Batch categories, used for ordering validation -------------------------
CATEGORY_INSTANCES = "instances"
CATEGORY_SPECIES = "species"
CATEGORY_MATERIALS = "materials"
CATEGORY_CONSOLIDATE = "consolidate"
CATEGORY_DATATABLE = "datatable"
CATEGORY_POST_IMPORT = "post_import"
CATEGORY_UNKNOWN = "unknown"


class ProbeError(Exception):
    """Raised for probe-level setup failures (missing dir, missing config)."""


class OrderingError(ProbeError):
    """Raised when the handed batch list violates a known ordering prerequisite."""

    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("; ".join(issues))


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _classify_batch(path: Path) -> str:
    """Classify a batch script by its well-known filename.

    See unreal_scripts.generate_unreal_import_script for the naming
    convention: import_batch_00_instances.py, import_batch_NN_<species>.py,
    import_batch_98_materials.py, import_batch_99_consolidate.py,
    import_batch_100_datatable.py, plus the fixed POST_IMPORT_SCRIPTS list.
    """
    name = path.name
    if name == "import_batch_00_instances.py":
        return CATEGORY_INSTANCES
    if name == "import_batch_98_materials.py":
        return CATEGORY_MATERIALS
    if name == "import_batch_99_consolidate.py":
        return CATEGORY_CONSOLIDATE
    if name == "import_batch_100_datatable.py":
        return CATEGORY_DATATABLE
    if name in POST_IMPORT_SCRIPTS:
        return CATEGORY_POST_IMPORT
    if BATCH_PATTERN.match(name):
        return CATEGORY_SPECIES
    return CATEGORY_UNKNOWN


def validate_ordering(batches: list[Path]) -> list[str]:
    """Check known ordering prerequisites among a (sub)set of batch scripts.

    Rules, derived from unreal_scripts.py / docs/guides/unreal-import.md:
      1. The shared twig instances batch must run before any species batch
         (species assemblies reference twigs already imported into
         Instances/; see "Twigs missing after import" in the troubleshooting
         guide).
      2. All species batches must run before the materials batch (it scans
         already-imported meshes and assigns MICs to their slots).
      3. All species batches must run before the consolidate batch (it
         de-duplicates twig copies left in each tree's folder).
      4. The materials batch must run before the DataTable batch and all
         species batches must run before it (it scans already-imported
         assembly SkeletalMeshes).

    Returns a list of human-readable violation messages; empty means the
    handed ordering is acceptable.
    """
    idx_by_cat: dict[str, list[int]] = {}
    for i, p in enumerate(batches):
        idx_by_cat.setdefault(_classify_batch(p), []).append(i)

    def first(cat: str) -> int | None:
        vals = idx_by_cat.get(cat)
        return vals[0] if vals else None

    issues: list[str] = []
    inst = first(CATEGORY_INSTANCES)
    species_idxs = idx_by_cat.get(CATEGORY_SPECIES, [])
    materials = first(CATEGORY_MATERIALS)
    consolidate = first(CATEGORY_CONSOLIDATE)
    datatable = first(CATEGORY_DATATABLE)

    if inst is not None and species_idxs and inst > min(species_idxs):
        issues.append(
            f"{batches[inst].name} (twig instances) is scheduled after "
            f"{batches[min(species_idxs)].name} (a species batch); twigs "
            "must import first or species assemblies will be missing them."
        )
    if species_idxs and materials is not None and materials < max(species_idxs):
        issues.append(
            f"{batches[materials].name} (materials) is scheduled before "
            f"{batches[max(species_idxs)].name} (a species batch); materials "
            "assigns MICs to already-imported meshes and must run after all "
            "species batches."
        )
    if species_idxs and consolidate is not None and consolidate < max(species_idxs):
        issues.append(
            f"{batches[consolidate].name} (consolidate) is scheduled before "
            f"{batches[max(species_idxs)].name} (a species batch); twig "
            "consolidation needs all species batches imported first."
        )
    if datatable is not None:
        if materials is not None and datatable < materials:
            issues.append(
                f"{batches[datatable].name} (datatable) is scheduled before "
                f"{batches[materials].name} (materials)."
            )
        if species_idxs and datatable < max(species_idxs):
            issues.append(
                f"{batches[datatable].name} (datatable) is scheduled before "
                f"{batches[max(species_idxs)].name} (a species batch); the "
                "DataTable scan requires all assemblies already imported."
            )
    return issues


def _parse_requested_labels(script_text: str) -> list[str]:
    return _LABEL_PATTERN.findall(script_text)


def _read_done_txt(batch_path: Path) -> list[str]:
    """Read the per-file resume progress file next to a batch script.

    Mirrors the naming convention from unreal_scripts._write_batch_script:
    ``<batch_stem>_done.txt``. Only species/instances batches have one.
    """
    done_path = batch_path.parent / f"{batch_path.stem}_done.txt"
    if not done_path.is_file():
        return []
    return [
        line.strip()
        for line in done_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _parse_summary(output_text: str) -> tuple[int | None, int | None, int | None]:
    m = _SUMMARY_PATTERN.search(output_text)
    if not m:
        return None, None, None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


class _ResourceSampler:
    """Background poller that tracks peak VRAM/RAM during a blocking call.

    A single remote-exec call blocks until UE returns the full result, so
    the only way to see a peak *during* the batch (rather than only
    before/after) is to sample from a side thread -- the same shape as
    ue_exec._RamWatchdog, but read-only (never kills UE).
    """

    def __init__(self, interval: float = 5.0):
        self.interval = interval
        self.vram_peak: float | None = None
        self.ram_peak: float | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _sample(self) -> None:
        vram = _get_gpu_vram()
        if vram is not None:
            pct = vram[2]
            self.vram_peak = pct if self.vram_peak is None else max(self.vram_peak, pct)
        ram = _get_system_ram()
        if ram is not None:
            pct = ram[2]
            self.ram_peak = pct if self.ram_peak is None else max(self.ram_peak, pct)

    def _run(self) -> None:
        self._sample()
        while not self._stop.wait(self.interval):
            self._sample()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)


def _run_single_capturing(
    script_path: Path, port: int, timeout: float
) -> tuple[bool, bool, str]:
    """Like ue_exec._run_single, but returns captured output text.

    ue_exec._run_single only prints output/result lines; this probe needs
    the text itself for done.txt/summary-line reconciliation, so it calls
    ue_remote.run_file directly (the same primitive _run_single calls)
    instead of reimplementing the wire protocol.
    """
    from growpy.io.unreal.ue_remote import run_file
    from growpy.tools.ue_exec import ABORT_MARKER

    try:
        result = run_file(
            str(script_path), timeout=timeout, command_endpoint=("127.0.0.1", port)
        )
    except ConnectionError as e:
        logger.error("Connection failed: %s", e)
        return False, False, ""
    except RuntimeError as e:
        logger.error("Execution error: %s", e)
        return False, False, ""

    success = bool(result.get("success", False))
    aborted = False
    lines: list[str] = []
    for line in result.get("output", []) or []:
        text = line.get("output", "")
        if text:
            print(text)
            lines.append(text)
            if ABORT_MARKER in text:
                aborted = True
    if result.get("result"):
        result_text = result["result"]
        print(result_text)
        lines.append(result_text)
        if ABORT_MARKER in result_text:
            aborted = True

    return success, aborted, "\n".join(lines)


def _run_batch_instrumented(
    script_path: Path,
    port: int,
    timeout: float,
    editor_exe: str | None,
    uproject: str | None,
    restart_ram_limit: float,
    restart_poll_interval: float,
    max_restarts: int,
) -> tuple[bool, bool, list[dict[str, Any]], str]:
    """Mirrors ue_exec._run_single_with_restart, recording restart events.

    ue_exec's version returns only (success, aborted); this variant reuses
    the same primitives (_RamWatchdog, _ue_alive, _restart_ue) but records
    each restart's reason -- "proactive_ram_limit" when the RAM watchdog
    fired during the call, "reactive_crash" when UE went unreachable on its
    own -- and returns the captured output text for reconciliation.

    Returns (success, aborted_memory, restart_events, output_text).
    """
    from growpy.tools import ue_exec as _ue

    restart_events: list[dict[str, Any]] = []
    attempts = 0
    while True:
        watchdog = _ue._RamWatchdog(restart_ram_limit, restart_poll_interval)
        watchdog.start()
        try:
            ok, aborted, text = _run_single_capturing(script_path, port, timeout)
        finally:
            proactive = watchdog.triggered
            watchdog.stop()

        if ok or aborted:
            return ok, aborted, restart_events, text

        # Failure with UE still reachable is a genuine script error, not a
        # crash -- don't mask it with blind retries (same rule as ue_exec).
        if _ue._ue_alive():
            return ok, aborted, restart_events, text

        attempts += 1
        reason = "proactive_ram_limit" if proactive else "reactive_crash"
        restart_events.append(
            {"reason": reason, "attempt": attempts, "at": _now_iso()}
        )
        if attempts > max_restarts:
            logger.error(
                "[Restart] UE down and exceeded max restarts (%d) for %s",
                max_restarts,
                script_path.name,
            )
            return False, False, restart_events, text

        if not _ue._restart_ue(editor_exe, uproject):
            logger.error("[Restart] UE did not come back online within timeout.")
            return False, False, restart_events, text


def run_import_probe(
    scripts_dir: Path,
    *,
    batches_override: list[str] | None = None,
    port: int = 6776,
    timeout: float = 0,
    editor_exe: str | None = None,
    uproject: str | None = None,
    restart_ram_limit: float = 95.0,
    restart_poll_interval: float = 10.0,
    max_restarts: int = 10,
    sample_interval: float = 5.0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run (or plan) the measurement probe over a batch of UE import scripts.

    Raises ProbeError for setup problems (missing directory, missing
    watchdog config) and OrderingError (a ProbeError subclass) when the
    handed/discovered batch order violates a known prerequisite -- unless
    dry_run is True, in which case ordering issues are reported in the
    returned plan instead of raising, so ``--dry-run`` always succeeds and
    only *describes* what would happen.
    """
    if not scripts_dir.is_dir():
        raise ProbeError(f"Scripts directory not found: {scripts_dir}")

    if batches_override:
        batches = [scripts_dir / name for name in batches_override]
        missing = [b for b in batches if not b.is_file()]
        if missing:
            raise ProbeError(
                "Batch file(s) not found: "
                + ", ".join(str(m) for m in missing)
            )
    else:
        batches = _discover_batch_scripts(scripts_dir)

    if not batches:
        raise ProbeError(f"No batch scripts discovered in {scripts_dir}")

    ordering_issues = validate_ordering(batches)

    plan = {
        "scripts_dir": str(scripts_dir),
        "batch_count": len(batches),
        "batches": [
            {"file": b.name, "category": _classify_batch(b)} for b in batches
        ],
        "ordering_issues": ordering_issues,
    }

    if dry_run:
        return {"dry_run": True, "plan": plan}

    if ordering_issues:
        raise OrderingError(ordering_issues)

    if restart_ram_limit > 0 and (not editor_exe or not uproject):
        raise ProbeError(
            "Auto-restart watchdog is enabled (restart_ram_limit > 0) but "
            "editor_exe/uproject were not resolved. Pass them explicitly or "
            "set restart_ram_limit=0."
        )

    results: list[dict[str, Any]] = []

    for batch_path in batches:
        category = _classify_batch(batch_path)
        script_text = batch_path.read_text(encoding="utf-8")
        requested_labels = (
            _parse_requested_labels(script_text)
            if category in (CATEGORY_INSTANCES, CATEGORY_SPECIES)
            else []
        )

        ram_before = _get_system_ram()
        vram_before = _get_gpu_vram()

        sampler = _ResourceSampler(sample_interval)
        sampler.start()
        started_at = _now_iso()
        t0 = time.monotonic()
        ok, aborted, restart_events, output_text = _run_batch_instrumented(
            batch_path,
            port,
            timeout,
            editor_exe,
            uproject,
            restart_ram_limit,
            restart_poll_interval,
            max_restarts,
        )
        duration_s = time.monotonic() - t0
        sampler.stop()

        ram_after = _get_system_ram()
        vram_after = _get_gpu_vram()

        completed_labels = _read_done_txt(batch_path) if requested_labels else []
        missing_labels = sorted(set(requested_labels) - set(completed_labels))
        imported, skipped, failed = _parse_summary(output_text)

        notes: list[str] = []
        ue_side_failure = False
        if requested_labels and missing_labels:
            ue_side_failure = True
            notes.append(
                f"{len(missing_labels)}/{len(requested_labels)} requested "
                "asset(s) missing from done.txt despite a reported-success "
                "batch -- possible UE-side per-file failure invisible to "
                "remote-exec's success flag."
            )

        if category == CATEGORY_MATERIALS:
            if _MATERIALS_PREREQ_MARKER in output_text:
                ue_side_failure = True
                notes.append(
                    f"'{_MATERIALS_PREREQ_MARKER}' seen in output -- "
                    "MA_Foliage_Trees not duplicated to db_path (see "
                    "docs/guides/unreal-import.md troubleshooting)."
                )
            m = _MATERIALS_SUMMARY_PATTERN.search(output_text)
            if m and int(m.group(1)) == 0:
                ue_side_failure = True
                notes.append(
                    "Materials batch reported 0 meshes updated -- likely "
                    "missing parent material or no species colour data."
                )

        if category == CATEGORY_DATATABLE:
            if _DATATABLE_PREREQ_MARKER in output_text:
                ue_side_failure = True
                notes.append(
                    f"'{_DATATABLE_PREREQ_MARKER}' seen in output -- "
                    "ST_TreeCatalogEntry struct missing at db_path."
                )
            expected_assemblies = sum(
                r["requested_count"]
                for r in results
                if r["category"] == CATEGORY_SPECIES
            )
            inventory_path = batch_path.parent / "tree_inventory.json"
            if inventory_path.is_file():
                try:
                    rows = json.loads(inventory_path.read_text(encoding="utf-8"))
                    if expected_assemblies and len(rows) != expected_assemblies:
                        ue_side_failure = True
                        notes.append(
                            f"tree_inventory.json has {len(rows)} rows but "
                            f"{expected_assemblies} assemblies were requested "
                            "across species batches."
                        )
                except Exception as e:
                    notes.append(f"Could not parse tree_inventory.json: {e}")

        measurement: dict[str, Any] = {
            "batch": batch_path.name,
            "category": category,
            "started_at": started_at,
            "duration_s": round(duration_s, 2),
            "ram_before_pct": ram_before[2] if ram_before else None,
            "ram_after_pct": ram_after[2] if ram_after else None,
            "ram_peak_pct": sampler.ram_peak,
            "vram_before_pct": vram_before[2] if vram_before else None,
            "vram_after_pct": vram_after[2] if vram_after else None,
            "vram_peak_pct": sampler.vram_peak,
            "restart_count": len(restart_events),
            "restarts": restart_events,
            "aborted_memory": aborted,
            "remote_exec_success": ok,
            "requested_count": len(requested_labels),
            "completed_count": len(completed_labels),
            "missing_labels": missing_labels,
            "summary_imported": imported,
            "summary_skipped": skipped,
            "summary_failed": failed,
            "ue_side_failure_suspected": ue_side_failure,
            "notes": notes,
        }
        results.append(measurement)

        if aborted:
            logger.error(
                "Batch aborted (memory limit): stopping probe, %s remaining "
                "batch(es) not attempted.",
                len(batches) - len(results),
            )
            break

    return {"dry_run": False, "plan": plan, "results": results}


def _print_summary(record: dict[str, Any]) -> None:
    plan = record["plan"]
    print("=" * 72)
    print(f"GrowPy UE Import Probe -- {plan['scripts_dir']}")
    print("=" * 72)
    if plan["ordering_issues"]:
        print("ORDERING ISSUES:")
        for issue in plan["ordering_issues"]:
            print(f"  - {issue}")
        print("")

    if record.get("dry_run"):
        print(f"{len(plan['batches'])} batch(es) planned (dry run, nothing executed):")
        for b in plan["batches"]:
            print(f"  [{b['category']:>11}] {b['file']}")
        return

    header = (
        f"{'batch':<34}{'cat':<11}{'dur(s)':>8}{'ram%':>7}{'vram%':>7}"
        f"{'restart':>8}{'req/done':>10}  status"
    )
    print(header)
    print("-" * len(header))
    for r in record["results"]:
        status = "OK"
        if not r["remote_exec_success"]:
            status = "FAILED"
        elif r["aborted_memory"]:
            status = "ABORTED"
        elif r["ue_side_failure_suspected"]:
            status = "SUSPECT"
        req_done = f"{r['completed_count']}/{r['requested_count']}"
        print(
            f"{r['batch']:<34}{r['category']:<11}{r['duration_s']:>8.1f}"
            f"{(r['ram_peak_pct'] or 0):>7.1f}{(r['vram_peak_pct'] or 0):>7.1f}"
            f"{r['restart_count']:>8}{req_done:>10}  {status}"
        )
        for note in r["notes"]:
            print(f"    note: {note}")
    print("")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Measurement probe for growpy-ue-exec batch imports: wraps the "
            "same import_batch_*.py sequence with per-batch timing, "
            "RAM/VRAM peak sampling, watchdog restart accounting, and "
            "done.txt reconciliation. Does not replace growpy-ue-exec for "
            "production imports."
        ),
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Path to an unreal_scripts/ directory",
    )
    parser.add_argument(
        "--batches",
        default=None,
        help=(
            "Comma-separated batch filenames (relative to target) to run in "
            "this exact order, overriding auto-discovery. The probe still "
            "validates this ordering and refuses to run it if invalid."
        ),
    )
    parser.add_argument("--port", type=int, default=6776)
    parser.add_argument("--timeout", type=float, default=0)
    parser.add_argument(
        "--editor-exe",
        default=None,
        help="Path to UnrealEditor.exe for auto-restart (falls back to config).",
    )
    parser.add_argument(
        "--uproject",
        default=None,
        help="Path to the .uproject file for auto-restart (falls back to config).",
    )
    parser.add_argument("--restart-ram-limit", type=float, default=95.0)
    parser.add_argument("--restart-poll-interval", type=float, default=10.0)
    parser.add_argument("--max-restarts", type=int, default=10)
    parser.add_argument(
        "--sample-interval",
        type=float,
        default=5.0,
        help="Seconds between RAM/VRAM peak samples during each batch.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan and ordering validation only; execute nothing.",
    )
    parser.add_argument(
        "--json", default=None, help="Write the JSON record to this path."
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    if not args.target:
        parser.error("A target unreal_scripts/ directory is required.")

    target = Path(args.target).resolve()
    if not target.exists():
        logger.error("Scripts directory not found: %s", target)
        logger.error(
            "(data/output/forest/ may not exist yet if a forest run hasn't "
            "completed -- this is expected, not a bug.)"
        )
        sys.exit(1)
    if not target.is_dir():
        parser.error(f"Expected a directory, got a file: {target}")

    editor_exe = args.editor_exe
    uproject = args.uproject
    watchdog_enabled = not args.dry_run and args.restart_ram_limit > 0
    if watchdog_enabled and (not editor_exe or not uproject):
        from growpy.config.core import get_config

        config = get_config()
        editor_exe = editor_exe or config.unreal_editor_exe or None
        uproject = uproject or config.unreal_uproject or None
        if not editor_exe or not uproject:
            parser.error(
                "Auto-restart watchdog is enabled (--restart-ram-limit > 0) "
                "but editor_exe/uproject could not be resolved. Set "
                "[unreal.watchdog] in config, pass --editor-exe/--uproject, "
                "or use --restart-ram-limit 0."
            )

    batches_override = args.batches.split(",") if args.batches else None

    try:
        record = run_import_probe(
            target,
            batches_override=batches_override,
            port=args.port,
            timeout=args.timeout,
            editor_exe=editor_exe,
            uproject=uproject,
            restart_ram_limit=args.restart_ram_limit,
            restart_poll_interval=args.restart_poll_interval,
            max_restarts=args.max_restarts,
            sample_interval=args.sample_interval,
            dry_run=args.dry_run,
        )
    except OrderingError as e:
        logger.error("Refusing to run: batch ordering is invalid.")
        for issue in e.issues:
            logger.error("  - %s", issue)
        sys.exit(3)
    except ProbeError as e:
        logger.error(str(e))
        sys.exit(2)

    _print_summary(record)

    if args.json:
        Path(args.json).write_text(json.dumps(record, indent=2), encoding="utf-8")
        logger.info("Wrote JSON measurement record: %s", args.json)

    if record.get("dry_run"):
        sys.exit(0)

    any_bad = any(
        (not r["remote_exec_success"]) or r["ue_side_failure_suspected"]
        for r in record["results"]
    )
    sys.exit(1 if any_bad else 0)


if __name__ == "__main__":
    main()
