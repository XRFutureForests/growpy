#!/usr/bin/env python3
"""Ingest yield tables from external providers into the local store.

Runs each available provider, normalizes output, and writes CSVs to the
store directory (default: data/input/yield_tables/store/).

Usage:
    python src/growpy/cli/ingest_yield_tables.py
    python src/growpy/cli/ingest_yield_tables.py --list-providers
    python src/growpy/cli/ingest_yield_tables.py --providers forest_elements et_nwfva
    python src/growpy/cli/ingest_yield_tables.py --clean
"""

import argparse
import logging
import sys
from pathlib import Path

from growpy.config import get_config
from growpy.utils.log import setup_logging
from pylometree.yield_tables import (
    StoreManifest,
    get_all_providers,
    get_available_providers,
    get_provider_by_name,
)
from pylometree.yield_tables.species import load_species_mapping

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Ingest yield tables from external providers into the local store."
    )
    parser.add_argument(
        "--list-providers",
        action="store_true",
        help="List all providers and their status, then exit.",
    )
    parser.add_argument(
        "--providers",
        nargs="+",
        help="Run only these providers (by name). Default: all available.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clear existing store before ingesting.",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose logging."
    )
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)
    config = get_config()
    project_root = Path(config.csv_file).resolve().parents[2]
    if not (project_root / "src" / "growpy").exists():
        project_root = Path.cwd()

    store_dir = config.yield_sources_store_dir
    if not store_dir.is_absolute():
        store_dir = project_root / store_dir

    if args.list_providers:
        _list_providers()
        return

    providers = _select_providers(args.providers)
    if not providers:
        logger.error("No providers available. Install dependencies or check --list-providers.")
        sys.exit(1)

    if args.clean and store_dir.exists():
        import shutil

        shutil.rmtree(store_dir)
        logger.info("Cleared store: %s", store_dir)

    store_dir.mkdir(parents=True, exist_ok=True)
    manifest = StoreManifest.load(store_dir / "manifest.csv")

    # Load species mapping from growpy's lookup CSV
    species_csv = project_root / "src" / "growpy" / "config" / "tree_asset_lookup.csv"
    species_mapping = load_species_mapping(species_csv if species_csv.exists() else None)

    # Provider config: point parametric_models at growpy's yield_models dir
    models_dir = project_root / "data" / "input" / "yield_models"
    provider_config = {"models_dir": str(models_dir.resolve())}

    total_tables = 0
    total_errors = 0

    for provider in providers:
        logger.info("")
        logger.info("Running provider: %s", provider.name)
        logger.info("  %s", provider.description)
        count = 0
        errors = 0
        try:
            for record in provider.iter_tables(species_mapping, provider_config):
                issues = record.validate()
                if issues:
                    logger.warning(
                        "  Skipping %s (si=%.0f): %s",
                        record.standardized_name,
                        record.site_index,
                        "; ".join(issues),
                    )
                    errors += 1
                    continue

                filename = record.filename()
                csv_path = store_dir / filename
                record.to_csv(csv_path)
                manifest.add(record, filename)
                count += 1
                logger.debug(
                    "  Wrote %s (%d rows)", filename, len(record.ages)
                )
        except Exception as e:
            logger.error("  Provider %s failed: %s", provider.name, e)
            errors += 1

        logger.info("  %s: %d tables ingested, %d errors", provider.name, count, errors)
        total_tables += count
        total_errors += errors

    manifest.save(store_dir / "manifest.csv")

    logger.info("")
    logger.info("Ingestion complete: %d tables in %s", total_tables, store_dir)
    if total_errors:
        logger.warning("  %d errors encountered", total_errors)

    _print_summary(manifest)


def _list_providers():
    print("Yield table providers:")
    print()
    for p in get_all_providers():
        marker = "[OK]" if p.available() else "[--]"
        print(f"  {marker} {p.name:25s} {p.status_message()}")
        print(f"      {p.description}")
    print()
    available = get_available_providers()
    print(f"  {len(available)} / {len(get_all_providers())} providers available")


def _select_providers(names):
    if names:
        providers = []
        for name in names:
            p = get_provider_by_name(name)
            if p is None:
                logger.error("Unknown provider: %s", name)
                continue
            if not p.available():
                logger.warning("Provider %s not available: %s", name, p.status_message())
                continue
            providers.append(p)
        return providers
    return get_available_providers()


def _print_summary(manifest):
    if not manifest.entries:
        return
    species_set = {e["standardized_name"] for e in manifest.entries}
    sources = {e.get("source", "?") for e in manifest.entries}
    print()
    print(f"  Store contains {len(manifest.entries)} tables for {len(species_set)} species")
    print(f"  Sources: {', '.join(sorted(sources))}")
    print(f"  Species: {', '.join(sorted(species_set))}")


if __name__ == "__main__":
    main()
