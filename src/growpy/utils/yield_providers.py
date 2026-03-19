"""Yield table provider interface and implementations.

Ingestion-time providers that extract yield tables from external sources
(R packages, XLSX files, PDFs, parametric models) and normalize them into
a common schema compatible with the existing local CSV yield table format.

Providers run offline via ``ingest_yield_tables.py``, not during calibration.
Ingested tables are stored as CSV files that slot into the existing
``data/input/yield_tables/`` resolution path.

Normalized CSV schema (backward-compatible with existing age,height,dbh):
    age,height,dbh,species_latin,region,management,site_index,source,table_id

Usage:
    from growpy.utils.yield_providers import get_available_providers

    for provider in get_available_providers():
        for table in provider.iter_tables():
            table.to_csv(output_dir / table.filename())
"""

import csv
import logging
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalized record
# ---------------------------------------------------------------------------


@dataclass
class YieldTableRecord:
    """A single normalized yield table ready for CSV export.

    Heights are in meters. DBHs are in centimeters (matching the existing
    local CSV convention where ``load_local_yield_table`` divides by 100).
    Volumes are in m3/ha (optional).
    """

    species_latin: str
    species_common: str
    standardized_name: str
    region: str
    management: str
    site_index: float
    source: str
    table_id: str
    ages: List[float]
    heights: List[float]
    dbhs: List[float]
    volumes: List[float] = field(default_factory=list)

    def filename(self) -> str:
        """Generate a canonical filename for this table."""
        si = f"si{self.site_index:.0f}" if self.site_index else "si0"
        region = self.region.replace("-", "").replace(" ", "_").lower()
        return (
            f"{self.standardized_name}_{region}_{si}_{self.management}.csv"
        )

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to a pandas DataFrame with the normalized schema."""
        n = len(self.ages)
        df = pd.DataFrame(
            {
                "age": self.ages,
                "height": self.heights,
                "dbh": self.dbhs,
                "species_latin": [self.species_latin] * n,
                "region": [self.region] * n,
                "management": [self.management] * n,
                "site_index": [self.site_index] * n,
                "source": [self.source] * n,
                "table_id": [self.table_id] * n,
            }
        )
        if self.volumes:
            df["volume"] = self.volumes[: n]
        return df

    def to_csv(self, path: Path) -> Path:
        """Write this table as a CSV file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        self.to_dataframe().to_csv(path, index=False)
        return path

    @staticmethod
    def from_csv(path: Path) -> "YieldTableRecord":
        """Read a normalized CSV back into a record."""
        df = pd.read_csv(path)
        first = df.iloc[0]
        return YieldTableRecord(
            species_latin=str(first.get("species_latin", "")),
            species_common="",
            standardized_name="",
            region=str(first.get("region", "")),
            management=str(first.get("management", "")),
            site_index=float(first.get("site_index", 0)),
            source=str(first.get("source", "")),
            table_id=str(first.get("table_id", "")),
            ages=df["age"].tolist(),
            heights=df["height"].tolist(),
            dbhs=df["dbh"].tolist(),
            volumes=df["volume"].tolist() if "volume" in df.columns else [],
        )

    def validate(self) -> List[str]:
        """Basic quality checks. Returns list of issues (empty = OK)."""
        issues: List[str] = []
        if len(self.ages) < 2:
            issues.append("fewer than 2 age entries")
        if len(self.ages) != len(self.heights):
            issues.append("ages and heights have different lengths")
        if len(self.ages) != len(self.dbhs):
            issues.append("ages and dbhs have different lengths")
        if self.ages and list(self.ages) != sorted(self.ages):
            issues.append("ages not monotonically increasing")
        if self.heights and any(h < 0 for h in self.heights):
            issues.append("negative height values")
        if self.dbhs and any(d < 0 for d in self.dbhs):
            issues.append("negative DBH values")
        return issues


# ---------------------------------------------------------------------------
# Manifest (registry of all ingested tables)
# ---------------------------------------------------------------------------


@dataclass
class StoreManifest:
    """Registry of all ingested yield tables in the store directory."""

    entries: List[Dict[str, Any]] = field(default_factory=list)

    COLUMNS = [
        "filename",
        "standardized_name",
        "species_latin",
        "region",
        "management",
        "site_index",
        "source",
        "table_id",
        "n_rows",
    ]

    def add(self, record: YieldTableRecord, filename: str) -> None:
        self.entries.append(
            {
                "filename": filename,
                "standardized_name": record.standardized_name,
                "species_latin": record.species_latin,
                "region": record.region,
                "management": record.management,
                "site_index": record.site_index,
                "source": record.source,
                "table_id": record.table_id,
                "n_rows": len(record.ages),
            }
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.COLUMNS)
            writer.writeheader()
            for entry in self.entries:
                writer.writerow(entry)

    @classmethod
    def load(cls, path: Path) -> "StoreManifest":
        if not path.exists():
            return cls()
        manifest = cls()
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "site_index" in row:
                    row["site_index"] = float(row["site_index"])
                if "n_rows" in row:
                    row["n_rows"] = int(row["n_rows"])
                manifest.entries.append(row)
        return manifest

    def find_tables_for_species(
        self, standardized_name: str
    ) -> List[Dict[str, Any]]:
        return [
            e for e in self.entries
            if e.get("standardized_name") == standardized_name
        ]


def select_best_table(
    tables: List[Dict[str, Any]],
    preferred_region: Optional[str] = None,
    preferred_site_index: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Pick the best table from a list of manifest entries.

    Selection logic:
        1. Filter by preferred_region if given.
        2. Pick by preferred_site_index if given, else pick middle site index.
    """
    if not tables:
        return None

    candidates = tables
    if preferred_region:
        region_match = [
            t for t in candidates
            if t.get("region", "").lower() == preferred_region.lower()
        ]
        if region_match:
            candidates = region_match

    if preferred_site_index is not None:
        candidates.sort(
            key=lambda t: abs(float(t.get("site_index", 0)) - preferred_site_index)
        )
        return candidates[0]

    candidates.sort(key=lambda t: float(t.get("site_index", 0)))
    return candidates[len(candidates) // 2]


# ---------------------------------------------------------------------------
# Species name mapping helpers
# ---------------------------------------------------------------------------


def load_species_mapping(project_root: Path) -> Dict[str, Dict[str, str]]:
    """Load tree_asset_lookup.csv and build Latin name -> project name mappings.

    Returns:
        Dict keyed by lowercase Latin name with values:
        {"common_name": ..., "standardized_name": ..., "yield_search": ...}
    """
    lookup_path = project_root / "src" / "growpy" / "config" / "tree_asset_lookup.csv"
    if not lookup_path.exists():
        logger.error("Asset lookup not found: %s", lookup_path)
        return {}

    df = pd.read_csv(lookup_path)
    mapping: Dict[str, Dict[str, str]] = {}
    for _, row in df.iterrows():
        latin = str(row.get("Scientific Name", "")).strip()
        if not latin:
            continue
        mapping[latin.lower()] = {
            "common_name": str(row["Common Name"]),
            "standardized_name": str(row.get("Standardized Name", "")),
            "yield_search": str(row.get("Yield Search", "")).strip(),
        }
    return mapping


# ---------------------------------------------------------------------------
# Provider abstract base class
# ---------------------------------------------------------------------------


class YieldProvider(ABC):
    """Abstract base class for yield table data sources."""

    name: str = "base"
    description: str = ""

    @abstractmethod
    def available(self) -> bool:
        """Check whether this provider can run (dependencies installed, files present)."""

    @abstractmethod
    def iter_tables(
        self, project_root: Path, config: Optional[Dict[str, Any]] = None
    ) -> Iterable[YieldTableRecord]:
        """Yield normalized table records from this source.

        Args:
            project_root: Repository root for resolving paths.
            config: Provider-specific settings from [yield_sources.<name>] in TOML.
        """

    def status_message(self) -> str:
        """Human-readable availability status."""
        if self.available():
            return "available"
        return "not available"


# ---------------------------------------------------------------------------
# Provider: ForestElementsR (R package)
# ---------------------------------------------------------------------------


class ForestElementsProvider(YieldProvider):
    """Extract yield tables from the ForestElementsR R package.

    Requires R and the ForestElementsR package to be installed.
    Calls an R script via subprocess that dumps tables to intermediate CSV.
    """

    name = "forest_elements"
    description = "ForestElementsR: Central European classical yield tables (Wiedemann, Schober, etc.)"

    def available(self) -> bool:
        return _r_package_available("ForestElementsR")

    def iter_tables(
        self, project_root: Path, config: Optional[Dict[str, Any]] = None
    ) -> Iterable[YieldTableRecord]:
        r_script = project_root / "src" / "scripts" / "extract_forest_elements.R"
        if not r_script.exists():
            logger.error("R script not found: %s", r_script)
            return

        species_map = load_species_mapping(project_root)
        yield from _run_r_extraction(r_script, "forest_elements", species_map)

    def status_message(self) -> str:
        if self.available():
            return "available (R + ForestElementsR installed)"
        if shutil.which("Rscript"):
            return "R found but ForestElementsR package not installed"
        return "R not found on PATH"


# ---------------------------------------------------------------------------
# Provider: et.nwfva (R package)
# ---------------------------------------------------------------------------


class EtNwfvaProvider(YieldProvider):
    """Extract yield tables from the et.nwfva R package.

    Provides modern yield tables for spruce, pine, beech, oak, Douglas-fir
    for north-west Germany.
    """

    name = "et_nwfva"
    description = "et.nwfva: NW-FVA yield tables for NW Germany (spruce, pine, beech, oak, Douglas-fir)"

    def available(self) -> bool:
        return _r_package_available("et.nwfva")

    def iter_tables(
        self, project_root: Path, config: Optional[Dict[str, Any]] = None
    ) -> Iterable[YieldTableRecord]:
        r_script = project_root / "src" / "scripts" / "extract_et_nwfva.R"
        if not r_script.exists():
            logger.error("R script not found: %s", r_script)
            return

        species_map = load_species_mapping(project_root)
        yield from _run_r_extraction(r_script, "et_nwfva", species_map)

    def status_message(self) -> str:
        if self.available():
            return "available (R + et.nwfva installed)"
        if shutil.which("Rscript"):
            return "R found but et.nwfva package not installed"
        return "R not found on PATH"


# ---------------------------------------------------------------------------
# Provider: Kohlenstoff-Ertragstafeln XLSX (OpenAgrar)
# ---------------------------------------------------------------------------


class CarbonEtXlsxProvider(YieldProvider):
    """Parse Schober-based yield tables from C_ET_pub.xlsx (OpenAgrar).

    User must download the file from:
    https://www.openagrar.de/receive/openagrar_mods_00096138

    Covers spruce, pine, beech, oak, Douglas-fir with age-structured tables.
    """

    name = "carbon_et_xlsx"
    description = "Kohlenstoff-Ertragstafeln: Schober tables in XLSX (spruce, pine, beech, oak, Douglas-fir)"

    def available(self) -> bool:
        try:
            import openpyxl  # noqa: F401
            return True
        except ImportError:
            return False

    def iter_tables(
        self, project_root: Path, config: Optional[Dict[str, Any]] = None
    ) -> Iterable[YieldTableRecord]:
        config = config or {}
        xlsx_path = Path(
            config.get("xlsx_path", "data/input/yield_sources/C_ET_pub.xlsx")
        )
        if not xlsx_path.is_absolute():
            xlsx_path = project_root / xlsx_path

        if not xlsx_path.exists():
            logger.warning(
                "XLSX file not found: %s — download from "
                "https://www.openagrar.de/receive/openagrar_mods_00096138",
                xlsx_path,
            )
            return

        species_map = load_species_mapping(project_root)
        yield from _parse_carbon_et_xlsx(xlsx_path, species_map)

    def status_message(self) -> str:
        if not self.available():
            return "openpyxl not installed (pip install openpyxl)"
        return "available (openpyxl installed)"


# ---------------------------------------------------------------------------
# Provider: Forest Yield UK PDF (Forestry Commission Booklet 48)
# ---------------------------------------------------------------------------


class ForestYieldPdfProvider(YieldProvider):
    """Extract yield tables from UK Forest Yield (FC Booklet 48) PDF.

    User must download the PDF from:
    https://cdn.forestresearch.gov.uk/2016/03/fcbk048.pdf
    """

    name = "forest_yield_uk"
    description = "UK Forest Yield (FC Booklet 48): British species yield tables"

    def available(self) -> bool:
        return _tabula_available()

    def iter_tables(
        self, project_root: Path, config: Optional[Dict[str, Any]] = None
    ) -> Iterable[YieldTableRecord]:
        config = config or {}
        pdf_path = Path(
            config.get("pdf_path", "data/input/yield_sources/fcbk048.pdf")
        )
        if not pdf_path.is_absolute():
            pdf_path = project_root / pdf_path

        if not pdf_path.exists():
            logger.warning(
                "PDF not found: %s — download from "
                "https://cdn.forestresearch.gov.uk/2016/03/fcbk048.pdf",
                pdf_path,
            )
            return

        species_map = load_species_mapping(project_root)
        yield from _parse_forest_yield_pdf(pdf_path, species_map)

    def status_message(self) -> str:
        if not self.available():
            return "tabula-py not installed (pip install tabula-py; requires Java)"
        return "available (tabula-py installed)"


# ---------------------------------------------------------------------------
# Provider: Pryor wild cherry PDF (FC Bulletin 75)
# ---------------------------------------------------------------------------


class PryorPdfProvider(YieldProvider):
    """Extract wild cherry yield tables from Pryor FC Bulletin 75."""

    name = "pryor_cherry"
    description = "Pryor: Wild cherry (Prunus avium) yield tables from FC Bulletin 75"

    def available(self) -> bool:
        return _tabula_available()

    def iter_tables(
        self, project_root: Path, config: Optional[Dict[str, Any]] = None
    ) -> Iterable[YieldTableRecord]:
        config = config or {}
        pdf_path = Path(
            config.get("pdf_path", "data/input/yield_sources/Pryor.pdf")
        )
        if not pdf_path.is_absolute():
            pdf_path = project_root / pdf_path

        if not pdf_path.exists():
            logger.warning(
                "PDF not found: %s — download Pryor FC Bulletin 75 PDF",
                pdf_path,
            )
            return

        species_map = load_species_mapping(project_root)
        yield from _parse_pryor_pdf(pdf_path, species_map)

    def status_message(self) -> str:
        if not self.available():
            return "tabula-py not installed"
        return "available (tabula-py installed)"


# ---------------------------------------------------------------------------
# Provider: Nova Scotia softwood yield tables PDF
# ---------------------------------------------------------------------------


class NovaScotiaPdfProvider(YieldProvider):
    """Extract yield tables from Nova Scotia softwood report PDF."""

    name = "nova_scotia"
    description = "Nova Scotia: Revised normal yield tables for Canadian softwoods"

    def available(self) -> bool:
        return _tabula_available()

    def iter_tables(
        self, project_root: Path, config: Optional[Dict[str, Any]] = None
    ) -> Iterable[YieldTableRecord]:
        config = config or {}
        pdf_path = Path(
            config.get(
                "pdf_path", "data/input/yield_sources/nova_scotia_report22.pdf"
            )
        )
        if not pdf_path.is_absolute():
            pdf_path = project_root / pdf_path

        if not pdf_path.exists():
            logger.warning(
                "PDF not found: %s — download from "
                "https://novascotia.ca/natr/library/forestry/reports/report22.pdf",
                pdf_path,
            )
            return

        species_map = load_species_mapping(project_root)
        yield from _parse_nova_scotia_pdf(pdf_path, species_map)

    def status_message(self) -> str:
        if not self.available():
            return "tabula-py not installed"
        return "available (tabula-py installed)"


# ---------------------------------------------------------------------------
# Provider: USDA Forest Stocking and Yield Tables PDF
# ---------------------------------------------------------------------------


class UsdaStockingPdfProvider(YieldProvider):
    """Extract yield tables from USDA stocking/yield tables PDF.

    Note: USDA tables are mostly volume/stock. H/D values may be absent
    and marked for enrichment via parametric models.
    """

    name = "usda_stocking"
    description = "USDA: Forest stocking and yield tables (hardwood/softwood)"

    def available(self) -> bool:
        return _tabula_available()

    def iter_tables(
        self, project_root: Path, config: Optional[Dict[str, Any]] = None
    ) -> Iterable[YieldTableRecord]:
        config = config or {}
        pdf_path = Path(
            config.get("pdf_path", "data/input/yield_sources/treetable2.pdf")
        )
        if not pdf_path.is_absolute():
            pdf_path = project_root / pdf_path

        if not pdf_path.exists():
            logger.warning(
                "PDF not found: %s — download from "
                "https://efotg.sc.egov.usda.gov/references/public/NC/treetable2.pdf",
                pdf_path,
            )
            return

        species_map = load_species_mapping(project_root)
        yield from _parse_usda_pdf(pdf_path, species_map)

    def status_message(self) -> str:
        if not self.available():
            return "tabula-py not installed"
        return "available (tabula-py installed)"


# ---------------------------------------------------------------------------
# Provider: Parametric growth models
# ---------------------------------------------------------------------------


class ParametricModelProvider(YieldProvider):
    """Generate synthetic yield tables from parametric growth model parameters.

    Reads JSON model files from a configured directory. Each file defines a
    growth function (Chapman-Richards, Korf, Lundqvist) with fitted parameters
    and a valid age range. The provider evaluates the model on an age grid to
    produce H-D-A tables.

    Model JSON format:
        {
            "species_latin": "Picea abies",
            "region": "DE-Central",
            "source_reference": "Author et al. (2020)",
            "height_model": {
                "type": "chapman_richards",
                "A": 38.5,
                "k": 0.025,
                "p": 1.3,
                "y0": 0.5
            },
            "dbh_model": {
                "type": "chapman_richards",
                "A": 55.0,
                "k": 0.018,
                "p": 1.1,
                "y0": 0.0
            },
            "age_range": [0, 200],
            "age_step": 5,
            "site_index": 32.0
        }
    """

    name = "parametric_models"
    description = "Parametric: Synthetic tables from published H-D-A growth model equations"

    def available(self) -> bool:
        return True

    def iter_tables(
        self, project_root: Path, config: Optional[Dict[str, Any]] = None
    ) -> Iterable[YieldTableRecord]:
        config = config or {}
        models_dir = Path(
            config.get("models_dir", "data/input/yield_models")
        )
        if not models_dir.is_absolute():
            models_dir = project_root / models_dir

        if not models_dir.exists():
            logger.info("Parametric models dir not found: %s", models_dir)
            return

        species_map = load_species_mapping(project_root)
        import json

        for model_file in sorted(models_dir.glob("*.json")):
            try:
                with open(model_file) as f:
                    model_def = json.load(f)
                record = _evaluate_parametric_model(model_def, species_map)
                if record:
                    yield record
            except Exception as e:
                logger.warning("Error processing %s: %s", model_file.name, e)


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------


ALL_PROVIDERS: List[YieldProvider] = [
    ForestElementsProvider(),
    EtNwfvaProvider(),
    CarbonEtXlsxProvider(),
    ForestYieldPdfProvider(),
    PryorPdfProvider(),
    NovaScotiaPdfProvider(),
    UsdaStockingPdfProvider(),
    ParametricModelProvider(),
]


def get_all_providers() -> List[YieldProvider]:
    """Return all registered providers."""
    return list(ALL_PROVIDERS)


def get_available_providers() -> List[YieldProvider]:
    """Return only providers whose dependencies are met."""
    return [p for p in ALL_PROVIDERS if p.available()]


def get_provider_by_name(name: str) -> Optional[YieldProvider]:
    """Look up a provider by its short name."""
    for p in ALL_PROVIDERS:
        if p.name == name:
            return p
    return None


# ---------------------------------------------------------------------------
# Internal helpers: dependency checks
# ---------------------------------------------------------------------------


def _r_package_available(package_name: str) -> bool:
    """Check whether R and a specific R package are installed."""
    rscript = shutil.which("Rscript")
    if not rscript:
        return False
    try:
        result = subprocess.run(
            [rscript, "-e", f'library({package_name})'],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _tabula_available() -> bool:
    """Check whether tabula-py is installed."""
    try:
        import tabula  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Internal helpers: R extraction
# ---------------------------------------------------------------------------


def _run_r_extraction(
    r_script: Path,
    source_name: str,
    species_map: Dict[str, Dict[str, str]],
) -> Iterable[YieldTableRecord]:
    """Run an R script and parse its CSV output into YieldTableRecords."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_csv = Path(tmpdir) / "output.csv"
        try:
            result = subprocess.run(
                ["Rscript", str(r_script), str(output_csv)],
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            logger.error("R script timed out: %s", r_script)
            return
        except FileNotFoundError:
            logger.error("Rscript not found on PATH")
            return

        if result.returncode != 0:
            logger.error(
                "R script failed (exit %d): %s\n%s",
                result.returncode, r_script, result.stderr[:2000],
            )
            return

        if not output_csv.exists():
            logger.error("R script produced no output: %s", r_script)
            return

        df = pd.read_csv(output_csv)

        required = {"species_latin", "age", "site_index"}
        if not required.issubset(df.columns):
            logger.error(
                "R output missing columns: %s (has: %s)",
                required - set(df.columns), list(df.columns),
            )
            return

        # Group by (species_latin, region, management, site_index, table_id)
        group_cols = ["species_latin"]
        for col in ["region", "management", "site_index", "table_id"]:
            if col in df.columns:
                group_cols.append(col)

        for group_key, group_df in df.groupby(group_cols):
            if not isinstance(group_key, tuple):
                group_key = (group_key,)

            group_df = group_df.sort_values("age").reset_index(drop=True)
            latin = str(group_key[0])
            region = str(group_key[group_cols.index("region")])  if "region" in group_cols else ""
            management = str(group_key[group_cols.index("management")]) if "management" in group_cols else "normal"
            si = float(group_key[group_cols.index("site_index")]) if "site_index" in group_cols else 0.0
            tid = str(group_key[group_cols.index("table_id")]) if "table_id" in group_cols else ""

            # Map Latin name to project species
            mapped = species_map.get(latin.lower(), {})
            common_name = mapped.get("common_name", "")
            std_name = mapped.get("standardized_name", "")

            heights = group_df["height"].tolist() if "height" in group_df.columns else [0.0] * len(group_df)
            dbhs = group_df["dbh"].tolist() if "dbh" in group_df.columns else [0.0] * len(group_df)
            volumes = group_df["volume"].tolist() if "volume" in group_df.columns else []

            record = YieldTableRecord(
                species_latin=latin,
                species_common=common_name,
                standardized_name=std_name,
                region=region,
                management=management,
                site_index=si,
                source=source_name,
                table_id=tid,
                ages=group_df["age"].tolist(),
                heights=heights,
                dbhs=dbhs,
                volumes=volumes,
            )

            issues = record.validate()
            if issues:
                logger.warning(
                    "Skipping %s/%s (si=%.0f): %s",
                    source_name, latin, si, "; ".join(issues),
                )
                continue

            yield record


# ---------------------------------------------------------------------------
# Internal helpers: XLSX parsing
# ---------------------------------------------------------------------------

# German species name -> Latin name mapping for the Kohlenstoff-Ertragstafeln
_CARBON_ET_SPECIES = {
    "fichte": "Picea abies",
    "kiefer": "Pinus sylvestris",
    "buche": "Fagus sylvatica",
    "eiche": "Quercus robur",
    "douglasie": "Pseudotsuga menziesii",
    "spruce": "Picea abies",
    "pine": "Pinus sylvestris",
    "beech": "Fagus sylvatica",
    "oak": "Quercus robur",
    "douglas fir": "Pseudotsuga menziesii",
    "douglas-fir": "Pseudotsuga menziesii",
}


def _parse_carbon_et_xlsx(
    xlsx_path: Path,
    species_map: Dict[str, Dict[str, str]],
) -> Iterable[YieldTableRecord]:
    """Parse yield tables from C_ET_pub.xlsx (Kohlenstoff-Ertragstafeln)."""
    try:
        xl = pd.ExcelFile(xlsx_path, engine="openpyxl")
    except Exception as e:
        logger.error("Failed to open XLSX: %s — %s", xlsx_path, e)
        return

    for sheet_name in xl.sheet_names:
        sheet_lower = sheet_name.lower().strip()

        # Try to identify species from sheet name
        latin = None
        for key, value in _CARBON_ET_SPECIES.items():
            if key in sheet_lower:
                latin = value
                break
        if not latin:
            logger.debug("Skipping unrecognised sheet: %s", sheet_name)
            continue

        try:
            df = xl.parse(sheet_name)
        except Exception as e:
            logger.warning("Error parsing sheet %s: %s", sheet_name, e)
            continue

        # Normalise column names: lowercase, strip whitespace
        df.columns = [str(c).strip().lower() for c in df.columns]

        # Find age column
        age_col = None
        for candidate in ["alter", "age", "a"]:
            if candidate in df.columns:
                age_col = candidate
                break
        if age_col is None:
            logger.debug("No age column in sheet %s", sheet_name)
            continue

        # Find height column
        height_col = None
        for candidate in ["ho", "h100", "h_q_m", "hg", "height", "h"]:
            if candidate in df.columns:
                height_col = candidate
                break

        # Find DBH column
        dbh_col = None
        for candidate in ["dg", "d_q_cm", "dbh", "d"]:
            if candidate in df.columns:
                dbh_col = candidate
                break

        # Find volume column
        vol_col = None
        for candidate in ["vfm", "v", "volume", "v_m3_ha"]:
            if candidate in df.columns:
                vol_col = candidate
                break

        if height_col is None and dbh_col is None:
            logger.debug("No height or DBH column in sheet %s", sheet_name)
            continue

        # Extract site index / yield class from sheet name or columns
        site_index = 0.0
        ek_col = None
        for candidate in ["ek", "ekl", "ertragsklasse", "yield_class", "si"]:
            if candidate in df.columns:
                ek_col = candidate
                break

        # Drop rows with NaN age
        df = df.dropna(subset=[age_col])
        df[age_col] = pd.to_numeric(df[age_col], errors="coerce")
        df = df.dropna(subset=[age_col])

        if ek_col:
            # Group by yield class
            for ek_val, ek_df in df.groupby(ek_col):
                ek_df = ek_df.sort_values(age_col).reset_index(drop=True)
                si = float(ek_val) if pd.notna(ek_val) else 0.0

                record = _build_xlsx_record(
                    ek_df, age_col, height_col, dbh_col, vol_col,
                    latin, si, sheet_name, species_map,
                )
                if record:
                    yield record
        else:
            df = df.sort_values(age_col).reset_index(drop=True)
            record = _build_xlsx_record(
                df, age_col, height_col, dbh_col, vol_col,
                latin, site_index, sheet_name, species_map,
            )
            if record:
                yield record


def _build_xlsx_record(
    df: pd.DataFrame,
    age_col: str,
    height_col: Optional[str],
    dbh_col: Optional[str],
    vol_col: Optional[str],
    species_latin: str,
    site_index: float,
    sheet_name: str,
    species_map: Dict[str, Dict[str, str]],
) -> Optional[YieldTableRecord]:
    """Build a YieldTableRecord from a single XLSX table block."""
    ages = df[age_col].tolist()
    heights = df[height_col].tolist() if height_col else [0.0] * len(ages)
    dbhs = df[dbh_col].tolist() if dbh_col else [0.0] * len(ages)
    volumes = df[vol_col].tolist() if vol_col else []

    # Convert any non-numeric to 0
    heights = [float(h) if pd.notna(h) else 0.0 for h in heights]
    dbhs = [float(d) if pd.notna(d) else 0.0 for d in dbhs]
    ages = [float(a) for a in ages]

    mapped = species_map.get(species_latin.lower(), {})

    record = YieldTableRecord(
        species_latin=species_latin,
        species_common=mapped.get("common_name", ""),
        standardized_name=mapped.get("standardized_name", ""),
        region="DE",
        management="normal",
        site_index=site_index,
        source="carbon_et_xlsx",
        table_id=f"C_ET_{sheet_name}",
        ages=ages,
        heights=heights,
        dbhs=dbhs,
        volumes=volumes,
    )

    issues = record.validate()
    if issues:
        logger.debug(
            "Skipping XLSX %s (si=%.0f): %s",
            species_latin, site_index, "; ".join(issues),
        )
        return None

    return record


# ---------------------------------------------------------------------------
# Internal helpers: PDF parsing
# ---------------------------------------------------------------------------


def _parse_forest_yield_pdf(
    pdf_path: Path,
    species_map: Dict[str, Dict[str, str]],
) -> Iterable[YieldTableRecord]:
    """Parse UK Forest Yield (FC Booklet 48) PDF.

    The PDF has a very regular table structure. Tables are organized by species
    with columns for age, top height, DBH, and volume across yield classes.

    This is a best-effort parser — extracted tables may need manual review.
    """
    try:
        import tabula
    except ImportError:
        logger.error("tabula-py not installed")
        return

    logger.info("Extracting tables from Forest Yield PDF (this may take a minute)...")

    try:
        tables = tabula.read_pdf(
            str(pdf_path), pages="all", multiple_tables=True, lattice=True,
        )
    except Exception as e:
        logger.error("Failed to extract tables from PDF: %s", e)
        return

    # FC Booklet 48 species sections — page ranges are approximate and may
    # need adjustment based on the exact PDF edition. Users should verify
    # extracted data against the source.
    _FC_SPECIES = {
        "Sitka spruce": "Picea sitchensis",
        "Norway spruce": "Picea abies",
        "Scots pine": "Pinus sylvestris",
        "Corsican pine": "Pinus nigra subsp. laricio",
        "Lodgepole pine": "Pinus contorta",
        "Douglas fir": "Pseudotsuga menziesii",
        "Japanese larch": "Larix kaempferi",
        "European larch": "Larix decidua",
        "Western hemlock": "Tsuga heterophylla",
        "Western red cedar": "Thuja plicata",
        "Oak": "Quercus robur",
        "Beech": "Fagus sylvatica",
        "Sycamore": "Acer pseudoplatanus",
        "Ash": "Fraxinus excelsior",
        "Birch": "Betula pendula",
        "Poplar": "Populus spp.",
    }

    for table_df in tables:
        if table_df is None or table_df.empty:
            continue

        # Normalize column names
        table_df.columns = [str(c).strip().lower() for c in table_df.columns]

        # Try to identify species from table content or nearby text
        # This is heuristic — PDF extraction doesn't preserve section headers well
        record = _try_parse_fc_table(table_df, _FC_SPECIES, species_map)
        if record:
            yield record


def _try_parse_fc_table(
    df: pd.DataFrame,
    fc_species: Dict[str, str],
    species_map: Dict[str, Dict[str, str]],
) -> Optional[YieldTableRecord]:
    """Attempt to parse a single extracted table from FC Booklet 48.

    Returns None if the table doesn't match the expected format.
    """
    # Look for age column
    age_col = None
    for candidate in ["age", "age (years)", "years"]:
        if candidate in df.columns:
            age_col = candidate
            break
    if age_col is None:
        return None

    # Look for top height column
    height_col = None
    for candidate in ["top height", "top ht", "height", "top height (m)", "ht"]:
        if candidate in df.columns:
            height_col = candidate
            break

    # Look for DBH column
    dbh_col = None
    for candidate in ["dbh", "mean dbh", "dbh (cm)", "mean dbh (cm)"]:
        if candidate in df.columns:
            dbh_col = candidate
            break

    if height_col is None and dbh_col is None:
        return None

    # Clean numeric data
    df = df.copy()
    df[age_col] = pd.to_numeric(df[age_col], errors="coerce")
    df = df.dropna(subset=[age_col])
    if df.empty:
        return None

    if height_col:
        df[height_col] = pd.to_numeric(df[height_col], errors="coerce")
    if dbh_col:
        df[dbh_col] = pd.to_numeric(df[dbh_col], errors="coerce")

    df = df.sort_values(age_col).reset_index(drop=True)

    ages = df[age_col].tolist()
    heights = df[height_col].fillna(0).tolist() if height_col else [0.0] * len(ages)
    dbhs = df[dbh_col].fillna(0).tolist() if dbh_col else [0.0] * len(ages)

    # Try to detect species from non-numeric cells in the first few rows
    species_latin = "Unknown"
    for col in df.columns:
        for val in df[col].head(5).astype(str):
            for name, latin in fc_species.items():
                if name.lower() in val.lower():
                    species_latin = latin
                    break
            if species_latin != "Unknown":
                break
        if species_latin != "Unknown":
            break

    if species_latin == "Unknown":
        return None

    mapped = species_map.get(species_latin.lower(), {})

    record = YieldTableRecord(
        species_latin=species_latin,
        species_common=mapped.get("common_name", ""),
        standardized_name=mapped.get("standardized_name", ""),
        region="UK",
        management="normal",
        site_index=0.0,
        source="forest_yield_uk",
        table_id="FC_BK48",
        ages=ages,
        heights=heights,
        dbhs=dbhs,
    )

    issues = record.validate()
    if issues:
        return None
    return record


def _parse_pryor_pdf(
    pdf_path: Path,
    species_map: Dict[str, Dict[str, str]],
) -> Iterable[YieldTableRecord]:
    """Parse wild cherry yield tables from Pryor FC Bulletin 75."""
    try:
        import tabula
    except ImportError:
        logger.error("tabula-py not installed")
        return

    logger.info("Extracting tables from Pryor PDF...")

    try:
        tables = tabula.read_pdf(
            str(pdf_path), pages="all", multiple_tables=True, lattice=True,
        )
    except Exception as e:
        logger.error("Failed to extract tables from PDF: %s", e)
        return

    latin = "Prunus avium"
    mapped = species_map.get(latin.lower(), {})
    table_idx = 0

    for table_df in tables:
        if table_df is None or table_df.empty:
            continue

        table_df.columns = [str(c).strip().lower() for c in table_df.columns]

        age_col = None
        for candidate in ["age", "age (years)", "years"]:
            if candidate in table_df.columns:
                age_col = candidate
                break
        if age_col is None:
            continue

        height_col = None
        for candidate in ["top height", "height", "ht", "top height (m)"]:
            if candidate in table_df.columns:
                height_col = candidate
                break

        dbh_col = None
        for candidate in ["dbh", "mean dbh", "dbh (cm)"]:
            if candidate in table_df.columns:
                dbh_col = candidate
                break

        if height_col is None and dbh_col is None:
            continue

        table_df = table_df.copy()
        table_df[age_col] = pd.to_numeric(table_df[age_col], errors="coerce")
        table_df = table_df.dropna(subset=[age_col])
        if table_df.empty:
            continue
        if height_col:
            table_df[height_col] = pd.to_numeric(table_df[height_col], errors="coerce")
        if dbh_col:
            table_df[dbh_col] = pd.to_numeric(table_df[dbh_col], errors="coerce")

        table_df = table_df.sort_values(age_col).reset_index(drop=True)
        table_idx += 1

        record = YieldTableRecord(
            species_latin=latin,
            species_common=mapped.get("common_name", ""),
            standardized_name=mapped.get("standardized_name", ""),
            region="UK",
            management="normal",
            site_index=0.0,
            source="pryor_cherry",
            table_id=f"FC_B75_t{table_idx}",
            ages=table_df[age_col].tolist(),
            heights=table_df[height_col].fillna(0).tolist() if height_col else [0.0] * len(table_df),
            dbhs=table_df[dbh_col].fillna(0).tolist() if dbh_col else [0.0] * len(table_df),
        )

        issues = record.validate()
        if not issues:
            yield record


def _parse_nova_scotia_pdf(
    pdf_path: Path,
    species_map: Dict[str, Dict[str, str]],
) -> Iterable[YieldTableRecord]:
    """Parse Nova Scotia softwood yield tables."""
    try:
        import tabula
    except ImportError:
        logger.error("tabula-py not installed")
        return

    logger.info("Extracting tables from Nova Scotia PDF...")

    _NS_SPECIES = {
        "balsam fir": "Abies balsamea",
        "red spruce": "Picea rubens",
        "black spruce": "Picea mariana",
        "white spruce": "Picea glauca",
        "eastern hemlock": "Tsuga canadensis",
        "jack pine": "Pinus banksiana",
        "red pine": "Pinus resinosa",
        "eastern white pine": "Pinus strobus",
    }

    try:
        tables = tabula.read_pdf(
            str(pdf_path), pages="all", multiple_tables=True, lattice=True,
        )
    except Exception as e:
        logger.error("Failed to extract tables from PDF: %s", e)
        return

    for table_df in tables:
        if table_df is None or table_df.empty:
            continue

        table_df.columns = [str(c).strip().lower() for c in table_df.columns]

        age_col = None
        for candidate in ["age", "age (years)", "years"]:
            if candidate in table_df.columns:
                age_col = candidate
                break
        if age_col is None:
            continue

        height_col = None
        for candidate in ["height", "dom. height", "dominant height", "ht", "avg ht"]:
            if candidate in table_df.columns:
                height_col = candidate
                break

        dbh_col = None
        for candidate in ["dbh", "avg dbh", "mean dbh"]:
            if candidate in table_df.columns:
                dbh_col = candidate
                break

        if height_col is None and dbh_col is None:
            continue

        table_df = table_df.copy()
        table_df[age_col] = pd.to_numeric(table_df[age_col], errors="coerce")
        table_df = table_df.dropna(subset=[age_col])
        if table_df.empty:
            continue
        if height_col:
            table_df[height_col] = pd.to_numeric(table_df[height_col], errors="coerce")
        if dbh_col:
            table_df[dbh_col] = pd.to_numeric(table_df[dbh_col], errors="coerce")

        table_df = table_df.sort_values(age_col).reset_index(drop=True)

        # Try to identify species from table
        species_latin = None
        for col in table_df.columns:
            for val in table_df[col].head(3).astype(str):
                for name, latin in _NS_SPECIES.items():
                    if name in val.lower():
                        species_latin = latin
                        break
                if species_latin:
                    break
            if species_latin:
                break

        if not species_latin:
            continue

        mapped = species_map.get(species_latin.lower(), {})

        # Convert feet to meters, inches to cm if needed
        heights_raw = table_df[height_col].fillna(0).tolist() if height_col else [0.0] * len(table_df)
        dbhs_raw = table_df[dbh_col].fillna(0).tolist() if dbh_col else [0.0] * len(table_df)

        # Heuristic: if max height > 60, assume feet
        max_h = max(heights_raw) if heights_raw else 0
        if max_h > 60:
            heights_raw = [h * 0.3048 for h in heights_raw]
        # Heuristic: if max DBH > 100, assume mm -> cm
        max_d = max(dbhs_raw) if dbhs_raw else 0
        if max_d > 100:
            dbhs_raw = [d / 10.0 for d in dbhs_raw]
        # If max DBH < 1, assume meters -> cm
        if 0 < max_d < 1:
            dbhs_raw = [d * 100.0 for d in dbhs_raw]

        record = YieldTableRecord(
            species_latin=species_latin,
            species_common=mapped.get("common_name", ""),
            standardized_name=mapped.get("standardized_name", ""),
            region="CA-NS",
            management="normal",
            site_index=0.0,
            source="nova_scotia",
            table_id="NS_Report22",
            ages=table_df[age_col].tolist(),
            heights=heights_raw,
            dbhs=dbhs_raw,
        )

        issues = record.validate()
        if not issues:
            yield record


def _parse_usda_pdf(
    pdf_path: Path,
    species_map: Dict[str, Dict[str, str]],
) -> Iterable[YieldTableRecord]:
    """Parse USDA forest stocking and yield tables.

    Note: Many USDA tables contain only volume/stock data. Height and DBH
    may be absent. Such records are emitted with zero H/D values and a warning.
    """
    try:
        import tabula
    except ImportError:
        logger.error("tabula-py not installed")
        return

    logger.info("Extracting tables from USDA stocking PDF...")

    try:
        tables = tabula.read_pdf(
            str(pdf_path), pages="all", multiple_tables=True, stream=True,
        )
    except Exception as e:
        logger.error("Failed to extract tables from PDF: %s", e)
        return

    table_idx = 0
    for table_df in tables:
        if table_df is None or table_df.empty:
            continue

        table_df.columns = [str(c).strip().lower() for c in table_df.columns]

        age_col = None
        for candidate in ["age", "age (years)", "stand age"]:
            if candidate in table_df.columns:
                age_col = candidate
                break
        if age_col is None:
            continue

        table_df = table_df.copy()
        table_df[age_col] = pd.to_numeric(table_df[age_col], errors="coerce")
        table_df = table_df.dropna(subset=[age_col])
        if table_df.empty:
            continue

        table_df = table_df.sort_values(age_col).reset_index(drop=True)

        height_col = None
        for candidate in ["height", "avg height", "site index", "ht"]:
            if candidate in table_df.columns:
                height_col = candidate
                break

        dbh_col = None
        for candidate in ["dbh", "avg dbh", "mean dbh"]:
            if candidate in table_df.columns:
                dbh_col = candidate
                break

        vol_col = None
        for candidate in ["volume", "vol", "yield", "cu ft/acre", "bd ft/acre"]:
            if candidate in table_df.columns:
                vol_col = candidate
                break

        if height_col is None and dbh_col is None and vol_col is None:
            continue

        if height_col:
            table_df[height_col] = pd.to_numeric(table_df[height_col], errors="coerce")
        if dbh_col:
            table_df[dbh_col] = pd.to_numeric(table_df[dbh_col], errors="coerce")

        heights = table_df[height_col].fillna(0).tolist() if height_col else [0.0] * len(table_df)
        dbhs = table_df[dbh_col].fillna(0).tolist() if dbh_col else [0.0] * len(table_df)
        volumes = []
        if vol_col:
            table_df[vol_col] = pd.to_numeric(table_df[vol_col], errors="coerce")
            volumes = table_df[vol_col].fillna(0).tolist()

        # Convert imperial units
        max_h = max(heights) if heights else 0
        if max_h > 60:
            heights = [h * 0.3048 for h in heights]
        max_d = max(dbhs) if dbhs else 0
        if max_d > 0 and max_d < 3:
            # Likely inches
            dbhs = [d * 2.54 for d in dbhs]

        table_idx += 1

        record = YieldTableRecord(
            species_latin="Unknown",
            species_common="",
            standardized_name="",
            region="US",
            management="normal",
            site_index=0.0,
            source="usda_stocking",
            table_id=f"USDA_t{table_idx}",
            ages=table_df[age_col].tolist(),
            heights=heights,
            dbhs=dbhs,
            volumes=volumes,
        )

        if height_col is None and dbh_col is None:
            logger.debug(
                "USDA table %d: volume-only (no H/D) — mark for parametric enrichment",
                table_idx,
            )

        issues = record.validate()
        if not issues:
            yield record


# ---------------------------------------------------------------------------
# Internal helpers: Parametric model evaluation
# ---------------------------------------------------------------------------

# Supported model types and their evaluation functions
_MODEL_TYPES = {
    "chapman_richards": lambda t, params: (
        params.get("y0", 0.0)
        + (params["A"] - params.get("y0", 0.0))
        * (1.0 - np.exp(-params["k"] * t)) ** params["p"]
    ),
    "korf": lambda t, params: (
        params["A"]
        * np.exp(-params["k"] * np.where(t > 0, t, 0.001) ** (-params["p"]))
    ),
    "lundqvist": lambda t, params: (
        params["A"]
        * np.exp(-params["k"] * np.where(t > 0, t, 0.001) ** params["p"])
    ),
}


def _evaluate_parametric_model(
    model_def: Dict[str, Any],
    species_map: Dict[str, Dict[str, str]],
) -> Optional[YieldTableRecord]:
    """Evaluate a parametric growth model on an age grid."""
    latin = model_def.get("species_latin", "")
    if not latin:
        logger.warning("Model missing species_latin")
        return None

    age_range = model_def.get("age_range", [0, 200])
    age_step = model_def.get("age_step", 5)
    ages = list(range(int(age_range[0]), int(age_range[1]) + 1, int(age_step)))
    ages_arr = np.array(ages, dtype=float)

    # Evaluate height model
    h_model = model_def.get("height_model")
    heights = [0.0] * len(ages)
    if h_model:
        model_type = h_model.get("type", "chapman_richards")
        eval_fn = _MODEL_TYPES.get(model_type)
        if eval_fn:
            params = {k: v for k, v in h_model.items() if k != "type"}
            heights = np.maximum(eval_fn(ages_arr, params), 0.0).tolist()

    # Evaluate DBH model
    d_model = model_def.get("dbh_model")
    dbhs = [0.0] * len(ages)
    if d_model:
        model_type = d_model.get("type", "chapman_richards")
        eval_fn = _MODEL_TYPES.get(model_type)
        if eval_fn:
            params = {k: v for k, v in d_model.items() if k != "type"}
            dbhs = np.maximum(eval_fn(ages_arr, params), 0.0).tolist()

    mapped = species_map.get(latin.lower(), {})

    record = YieldTableRecord(
        species_latin=latin,
        species_common=mapped.get("common_name", ""),
        standardized_name=mapped.get("standardized_name", ""),
        region=model_def.get("region", ""),
        management="modeled",
        site_index=model_def.get("site_index", 0.0),
        source="parametric_models",
        table_id=model_def.get("source_reference", ""),
        ages=ages,
        heights=heights,
        dbhs=dbhs,
    )

    issues = record.validate()
    if issues:
        logger.warning(
            "Parametric model for %s has issues: %s",
            latin, "; ".join(issues),
        )
        return None

    return record
