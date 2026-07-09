"""Generate a per-run dataset creation summary (timing, assembly counts, status).

Produces:
- dataset_run_summary.md: Human-readable report of the most recent step-4 run.
- dataset_run_summary.csv: Append-only run history (one row per species per run),
  for tracking generation time across dataset re-runs (e.g. before/after a
  refactor).
"""

import csv
import logging
from datetime import UTC, datetime
from pathlib import Path

from growpy.utils.naming import standardize_species_name

logger = logging.getLogger(__name__)

CSV_FIELDNAMES = [
    "run_timestamp",
    "species",
    "assemblies",
    "elapsed_seconds",
    "status",
]


def _count_assemblies(species_dir: Path) -> int:
    if not species_dir.exists():
        return 0
    return sum(1 for _ in species_dir.rglob("*_full_assembly.usda"))


def _format_duration(seconds: float) -> str:
    total_seconds = int(round(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def generate_run_summary(
    output_dir: Path,
    species_list: list,
    elapsed_by_species: dict,
    failed: list,
) -> Path:
    """Write dataset_run_summary.md/.csv for a completed step-4 dataset run.

    Args:
        output_dir: Forest output directory (config.output_dir).
        species_list: Species processed in this run (display or standardized
            names; standardized internally for directory lookup).
        elapsed_by_species: Wall-clock seconds spent per species, keyed by
            the same names as species_list.
        failed: Species names (matching species_list) that failed step 4.

    Returns the path to the generated markdown file.
    """
    failed_std = {standardize_species_name(s) for s in failed}
    rows = []
    for species in species_list:
        std_name = standardize_species_name(species)
        assemblies = _count_assemblies(output_dir / std_name)
        elapsed = elapsed_by_species.get(species, 0.0)
        status = "FAILED" if std_name in failed_std else "OK"
        rows.append(
            {
                "species": std_name,
                "assemblies": assemblies,
                "elapsed_seconds": round(elapsed, 1),
                "status": status,
            }
        )

    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    total_assemblies = sum(r["assemblies"] for r in rows)
    total_elapsed = sum(r["elapsed_seconds"] for r in rows)

    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "dataset_run_summary.csv"
    file_exists = csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({"run_timestamp": timestamp, **row})
    logger.info("Dataset run summary CSV updated at %s", csv_path)

    lines = [
        "# Dataset Run Summary",
        "",
        f"Run finished: {timestamp}",
        "",
        "| Species | Assemblies | Time | Status |",
        "|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['species']} | {row['assemblies']} | "
            f"{_format_duration(row['elapsed_seconds'])} | {row['status']} |"
        )
    lines.append("")
    lines.append(
        f"**Total: {total_assemblies} assemblies, "
        f"{_format_duration(total_elapsed)}, {len(failed)} failed species.**"
    )
    lines.append("")
    if failed:
        lines.append(f"Failed species: {', '.join(sorted(failed_std))}")
        lines.append("")
    lines.append(
        "Full run history across dataset re-runs: "
        "[dataset_run_summary.csv](dataset_run_summary.csv)"
    )
    lines.append("")

    md_path = output_dir / "dataset_run_summary.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Dataset run summary written to %s", md_path)
    return md_path
