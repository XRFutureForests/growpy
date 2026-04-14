#!/usr/bin/env python3
"""
GBIF species name validation and standardization.

Uses pygbif (https://techdocs.gbif.org/en/data-use/pygbif) to:
- Validate scientific names against GBIF backbone taxonomy
- Get accepted names for synonyms
- Retrieve taxonomic hierarchy (family, genus)
- Look up vernacular (common) names

Installation:
    conda install -c conda-forge pygbif
    # or: pip install pygbif

Quick Start:
    # Validate all species in lookup table
    python src/growpy/utils/gbif_species.py --validate

    # Enrich lookup table with GBIF data
    python src/growpy/utils/gbif_species.py --enrich

    # Look up a single species
    python src/growpy/utils/gbif_species.py --species "Quercus robur"

Usage:
    python src/growpy/utils/gbif_species.py [options]
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

try:
    from pygbif import species as gbif_species

    PYGBIF_AVAILABLE = True
except ImportError:
    PYGBIF_AVAILABLE = False


def validate_scientific_name(scientific_name: str) -> dict:
    """Validate a scientific name against GBIF backbone taxonomy.

    Args:
        scientific_name: Scientific name to validate (e.g., "Quercus robur")

    Returns:
        Dictionary with validation results:
        - valid: Whether name is recognized
        - matched_name: Name matched in GBIF
        - accepted_name: Current accepted name (if different)
        - status: ACCEPTED, SYNONYM, DOUBTFUL, etc.
        - taxon_key: GBIF taxon key for the accepted name
        - family: Taxonomic family
        - genus: Taxonomic genus
        - confidence: Match confidence (0-100)
    """
    if not PYGBIF_AVAILABLE:
        raise ImportError(
            "pygbif not installed. Run: conda install -c conda-forge pygbif"
        )

    result = {
        "input": scientific_name,
        "valid": False,
        "matched_name": None,
        "accepted_name": None,
        "status": None,
        "taxon_key": None,
        "accepted_key": None,
        "family": None,
        "genus": None,
        "rank": None,  # Taxonomic rank of the match (SPECIES, GENUS, FAMILY, etc.)
        "match_type": None,  # EXACT, FUZZY, HIGHERRANK, NONE
        "confidence": 0,
        "issues": [],
    }

    try:
        # Call GBIF API - returns dict with usage, classification, diagnostics, synonym
        response = gbif_species.name_backbone(
            scientificName=scientific_name,
            kingdom="Plantae",
            strict=False,
        )

        # Extract components from response
        usage = response.get("usage", {})
        classification = response.get("classification", [])  # List of rank dicts
        diagnostics = response.get("diagnostics", {})
        is_synonym = response.get("synonym", False)

        match_type = diagnostics.get("matchType", "NONE")
        result["match_type"] = match_type

        if match_type == "NONE":
            result["issues"].append("No match found in GBIF backbone")
            return result

        result["valid"] = True
        result["matched_name"] = usage.get("canonicalName") or usage.get("name")
        result["status"] = usage.get("status", "SYNONYM" if is_synonym else "ACCEPTED")
        result["taxon_key"] = usage.get("key")
        result["rank"] = usage.get("rank")  # SPECIES, GENUS, FAMILY, etc.
        result["confidence"] = diagnostics.get("confidence", 0)

        # Parse classification list to extract family and genus
        for taxon in classification:
            rank = taxon.get("rank", "").upper()
            if rank == "FAMILY":
                result["family"] = taxon.get("name")
            elif rank == "GENUS":
                result["genus"] = taxon.get("name")

        # Check if it's a synonym
        if is_synonym and usage.get("acceptedKey"):
            result["accepted_key"] = usage.get("acceptedKey")
            # Get the accepted name
            accepted = gbif_species.name_usage(key=usage["acceptedKey"])
            result["accepted_name"] = accepted.get("canonicalName") or accepted.get(
                "scientificName"
            )
            result["issues"].append(
                f"Synonym - accepted name is {result['accepted_name']}"
            )
        else:
            result["accepted_name"] = result["matched_name"]
            result["accepted_key"] = result["taxon_key"]

        # Flag low confidence matches
        if result["confidence"] < 90:
            result["issues"].append(f"Low confidence match ({result['confidence']}%)")

        # Check for match type issues
        if match_type == "FUZZY":
            result["issues"].append("Fuzzy match - may not be exact")
        elif match_type == "HIGHERRANK":
            result["issues"].append("Higher rank match - species not found exactly")

        # Check for notes in diagnostics
        if diagnostics.get("note"):
            result["issues"].append(diagnostics["note"])

    except Exception as e:
        result["issues"].append(f"GBIF API error: {str(e)}")

    return result


def get_vernacular_names(taxon_key: int, language: str = "eng") -> list:
    """Get vernacular (common) names for a taxon.

    Args:
        taxon_key: GBIF taxon key
        language: ISO 639-2 language code (default: "eng" for English)

    Returns:
        List of vernacular names
    """
    if not PYGBIF_AVAILABLE:
        raise ImportError(
            "pygbif not installed. Run: conda install -c conda-forge pygbif"
        )

    try:
        result = gbif_species.name_usage(key=taxon_key, data="vernacularNames")
        names = result.get("results", [])

        # Filter by language and extract names
        vernacular = []
        for name in names:
            if language is None or name.get("language", "").lower() == language.lower():
                vernacular.append(name.get("vernacularName"))

        return [n for n in vernacular if n]

    except Exception:
        logger.warning("GBIF vernacular lookup failed for taxon_key=%s", taxon_key)
        return []


def validate_lookup_table(csv_path: Path) -> pd.DataFrame:
    """Validate all species in the lookup table.

    Args:
        csv_path: Path to tree_asset_lookup.csv

    Returns:
        DataFrame with validation results
    """
    df = pd.read_csv(csv_path)

    results = []
    for _, row in df.iterrows():
        scientific = row.get("Scientific Name", "")
        if pd.isna(scientific) or not scientific.strip():
            continue

        print(f"Validating: {scientific}...")
        validation = validate_scientific_name(scientific)
        validation["common_name"] = row.get("Common Name", "")
        results.append(validation)

    return pd.DataFrame(results)


def enrich_lookup_table(
    input_path: Path, output_path: Optional[Path] = None
) -> pd.DataFrame:
    """Enrich lookup table with GBIF taxonomic data.

    Adds columns:
    - GBIF Taxon Key
    - Family
    - Genus
    - GBIF Status
    - GBIF Accepted Name

    Args:
        input_path: Path to tree_asset_lookup.csv
        output_path: Path for enriched output (optional)

    Returns:
        Enriched DataFrame
    """
    df = pd.read_csv(input_path)

    # Add new columns
    df["GBIF Taxon Key"] = None
    df["Family"] = None
    df["Genus"] = None
    df["GBIF Status"] = None
    df["GBIF Accepted Name"] = None
    df["GBIF Issues"] = None

    for idx, row in df.iterrows():
        scientific = row.get("Scientific Name", "")
        if pd.isna(scientific) or not scientific.strip():
            continue

        print(f"Looking up: {scientific}...")
        try:
            validation = validate_scientific_name(scientific)
            df.at[idx, "GBIF Taxon Key"] = validation.get("accepted_key")
            df.at[idx, "Family"] = validation.get("family")
            df.at[idx, "Genus"] = validation.get("genus")
            df.at[idx, "GBIF Status"] = validation.get("status")
            df.at[idx, "GBIF Accepted Name"] = validation.get("accepted_name")
            if validation.get("issues"):
                df.at[idx, "GBIF Issues"] = "; ".join(validation["issues"])
        except Exception as e:
            df.at[idx, "GBIF Issues"] = str(e)

    if output_path:
        df.to_csv(output_path, index=False)
        print(f"Enriched table saved to: {output_path}")

    return df


def lookup_species(scientific_name: str) -> None:
    """Look up a single species and print results."""
    print(f"\nLooking up: {scientific_name}")
    print("-" * 50)

    validation = validate_scientific_name(scientific_name)

    print(f"Valid:          {validation['valid']}")
    print(f"Matched Name:   {validation['matched_name']}")
    print(f"Status:         {validation['status']}")
    print(f"Accepted Name:  {validation['accepted_name']}")
    print(f"Taxon Key:      {validation['accepted_key']}")
    print(f"Family:         {validation['family']}")
    print(f"Genus:          {validation['genus']}")
    print(f"Confidence:     {validation['confidence']}%")

    if validation["issues"]:
        print(f"Issues:         {', '.join(validation['issues'])}")

    if validation.get("accepted_key"):
        vernacular = get_vernacular_names(validation["accepted_key"])
        if vernacular:
            print(f"Common Names:   {', '.join(vernacular[:5])}")


def match_species_via_gbif(
    query: str,
    lookup_df: pd.DataFrame,
    min_confidence: int = 80,
) -> Optional[pd.Series]:
    """Match an unknown species name to lookup table using GBIF.

    Uses GBIF backbone taxonomy to resolve synonyms, misspellings, and
    alternative names to find matching species in our lookup table.

    Matching strategy:
    1. Query GBIF with input name (handles fuzzy matching, synonyms)
    2. Get accepted scientific name from GBIF
    3. Match accepted name against lookup table's Scientific Name column
    4. Also try matching GBIF vernacular names against Common Name/Aliases

    Args:
        query: Species name to match (common name, scientific name, or synonym)
        lookup_df: DataFrame with species lookup data (must have Scientific Name column)
        min_confidence: Minimum GBIF match confidence (0-100, default: 80)

    Returns:
        Matching row from lookup_df, or None if no match found
    """
    if not PYGBIF_AVAILABLE:
        return None

    try:
        # Query GBIF
        validation = validate_scientific_name(query)

        if not validation["valid"] or validation["confidence"] < min_confidence:
            return None

        # Reject HIGHERRANK matches (e.g., common names matching to Kingdom/Family)
        # We only want SPECIES-level matches for accurate asset lookup
        if validation.get("match_type") == "HIGHERRANK":
            return None

        # Reject non-species rank matches
        rank = validation.get("rank", "").upper()
        if rank and rank not in ("SPECIES", "SUBSPECIES", "VARIETY", "FORM"):
            return None

        accepted_name = validation.get("accepted_name")
        if not accepted_name:
            return None

        # Try matching accepted scientific name to lookup table
        if "Scientific Name" in lookup_df.columns:
            # Exact match on scientific name
            match = lookup_df[
                lookup_df["Scientific Name"].str.lower() == accepted_name.lower()
            ]
            if not match.empty:
                return match.iloc[0]

            # Try without cultivar names (e.g., "Fraxinus excelsior 'Diversifolia'" -> "Fraxinus excelsior")
            base_name = accepted_name.split("'")[0].strip()
            if base_name != accepted_name:
                match = lookup_df[
                    lookup_df["Scientific Name"].str.lower() == base_name.lower()
                ]
                if not match.empty:
                    return match.iloc[0]

            # Try genus + species only (ignore subspecies, varieties)
            parts = accepted_name.split()
            if len(parts) >= 2:
                binomial = f"{parts[0]} {parts[1]}"
                match = lookup_df[
                    lookup_df["Scientific Name"]
                    .str.lower()
                    .str.startswith(binomial.lower())
                ]
                if not match.empty:
                    return match.iloc[0]

        # Try matching GBIF vernacular names to Common Name or Aliases
        if validation.get("accepted_key"):
            vernacular = get_vernacular_names(validation["accepted_key"])
            for v_name in vernacular[:10]:  # Check first 10 vernacular names
                v_lower = v_name.lower()

                # Match Common Name
                if "Common Name" in lookup_df.columns:
                    match = lookup_df[lookup_df["Common Name"].str.lower() == v_lower]
                    if not match.empty:
                        return match.iloc[0]

                # Match Aliases
                if "Aliases" in lookup_df.columns:
                    for _, row in lookup_df.iterrows():
                        aliases = str(row.get("Aliases", "")).lower()
                        if v_lower in [a.strip() for a in aliases.split(",")]:
                            return row

        return None

    except Exception:
        logger.warning("GBIF species matching failed for query=%s", query)
        return None


def resolve_species_list(
    species_list: list,
    lookup_df: pd.DataFrame,
    use_gbif: bool = True,
    verbose: bool = False,
) -> dict:
    """Resolve a list of species names to lookup table entries.

    Tries local matching first, then falls back to GBIF for unmatched species.

    Args:
        species_list: List of species names to resolve
        lookup_df: DataFrame with species lookup data
        use_gbif: Whether to use GBIF for unmatched species (default: True)
        verbose: Print progress and match details (default: False)

    Returns:
        Dict mapping input species name to matched row (or None if unmatched)
    """
    results = {}

    for species in species_list:
        species_lower = species.lower()
        matched = None

        # Try local matching first
        # Common Name
        if "Common Name" in lookup_df.columns:
            match = lookup_df[lookup_df["Common Name"].str.lower() == species_lower]
            if not match.empty:
                matched = match.iloc[0]

        # Standardized Name
        if matched is None and "Standardized Name" in lookup_df.columns:
            match = lookup_df[
                lookup_df["Standardized Name"].str.lower() == species_lower
            ]
            if not match.empty:
                matched = match.iloc[0]

        # Scientific Name
        if matched is None and "Scientific Name" in lookup_df.columns:
            match = lookup_df[lookup_df["Scientific Name"].str.lower() == species_lower]
            if not match.empty:
                matched = match.iloc[0]

        # Aliases
        if matched is None and "Aliases" in lookup_df.columns:
            for _, row in lookup_df.iterrows():
                aliases = str(row.get("Aliases", "")).lower()
                if species_lower in [a.strip() for a in aliases.split(",")]:
                    matched = row
                    break

        # Fall back to GBIF if local matching failed
        if matched is None and use_gbif and PYGBIF_AVAILABLE:
            if verbose:
                print(f"  GBIF lookup: {species}...")
            matched = match_species_via_gbif(species, lookup_df)
            if matched is not None and verbose:
                print(f"    -> Matched to: {matched.get('Common Name', 'Unknown')}")

        results[species] = matched

        if verbose and matched is None:
            print(f"  WARNING: No match found for '{species}'")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="GBIF species name validation and standardization"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate all species in lookup table",
    )
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Enrich lookup table with GBIF data",
    )
    parser.add_argument(
        "--species",
        type=str,
        help="Look up a single species",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("config/tree_asset_lookup.csv"),
        help="Path to lookup CSV (default: config/tree_asset_lookup.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output path for enriched CSV",
    )

    args = parser.parse_args()

    if not PYGBIF_AVAILABLE:
        print("ERROR: pygbif not installed")
        print("Install with: conda install -c conda-forge pygbif")
        return 1

    if args.species:
        lookup_species(args.species)
    elif args.validate:
        results = validate_lookup_table(args.csv)
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)

        valid_count = results["valid"].sum()
        total = len(results)
        print(f"Valid: {valid_count}/{total} ({100*valid_count/total:.1f}%)")

        issues = results[
            results["issues"].apply(
                lambda x: len(x) > 0 if isinstance(x, list) else False
            )
        ]
        if len(issues) > 0:
            print("\nSpecies with issues:")
            for _, row in issues.iterrows():
                print(f"  - {row['input']}: {', '.join(row['issues'])}")
    elif args.enrich:
        output = args.output or args.csv.with_suffix(".enriched.csv")
        enrich_lookup_table(args.csv, output)
    else:
        parser.print_help()

    return 0


if __name__ == "__main__":
    exit(main())
