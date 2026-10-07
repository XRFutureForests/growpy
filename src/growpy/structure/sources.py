"""Per-dataset adapters: find the files, read the metadata, yield standardised trees.

Each adapter knows where one published dataset keeps its species, DBH, height and
validity flags, and maps them onto the shared ``TREE_COLUMNS``. A value a dataset does not
provide stays empty (Ghent has no species), never a guess. Reported values keep their
provenance in the column name; the same quantities measured on the cylinders are in
``dbh_m`` / ``height_m`` for every source.

Adapters take paths into ``data/input/reference_qsm/<dataset>/`` and yield ``QsmTree``;
a tree that fails to parse is reported and skipped, not silently dropped.
"""

from __future__ import annotations

import csv
import re
import sys
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path

import pandas as pd

from growpy.structure.readers import (
    read_graphml,
    read_growth_json,
    read_rtwig_csv,
    read_treeml_csv,
    read_treeqsm_mat,
)
from growpy.structure.schema import SPECIES_KEY, QsmTree, normalize_species
from growpy.structure.standardize import standardize


def _float(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None  # NaN -> None


def _scale(value: float | None, factor: float) -> float | None:
    return None if value is None else value * factor


def _bool(value) -> bool | None:
    return {"true": True, "false": False}.get(str(value).strip().lower())


def _guard(label: str, build: Callable[[], QsmTree]) -> QsmTree | None:
    try:
        return build()
    except Exception as exc:  # noqa: BLE001 - one bad file must not end a 3,000 tree run
        print(f"skip {label}: {exc}", file=sys.stderr)
        return None


def _mat_members(zip_path: Path) -> Iterator[tuple[str, bytes]]:
    with zipfile.ZipFile(zip_path) as z:
        for name in sorted(z.namelist()):
            if name.endswith(".mat"):
                yield name, z.read(name)


# --- Kew Wakehurst: TreeQSM struct, species and habitat in kew-wakehurst-agc.csv -------


def kew(dataset_dir: Path) -> Iterator[QsmTree]:
    """``broadleaf_qsm.zip`` / ``conifer_qsm.zip`` / ``coppice_qsm.zip`` plus the csv.

    A tree id such as ``0038_T0`` is only unique within a plot: it recurs in several plot
    folders and zips for different trees (285 of 2,676 ids), and the csv repeats it with
    different species and sizes. The uid therefore carries the zip and plot folder, and
    the csv row is used only when it is the single row for that id and habitat; an
    ambiguous id keeps its cylinders but gets no species or reported values."""
    table: dict[tuple[str, str], list[dict]] = {}
    with open(
        dataset_dir / "kew-wakehurst-agc.csv", newline="", encoding="utf-8"
    ) as fh:
        for r in csv.DictReader(fh):
            table.setdefault((r["habitat"], r["tree"]), []).append(r)
    for zip_name in ("broadleaf_qsm.zip", "conifer_qsm.zip", "coppice_qsm.zip"):
        subset = zip_name.split("_")[0]
        for member, data in _mat_members(dataset_dir / zip_name):
            tree_id = Path(member).stem
            candidates = table.get((subset, tree_id), [])
            row = candidates[0] if len(candidates) == 1 else {}
            meta = {
                "tree_uid": f"kew:{subset}/{member.removesuffix('.mat')}",
                "source": "kew",
                "source_kind": "scan",
                "source_tree_id": tree_id,
                "tier": "C",
                "plot": Path(member).parent.name or None,
                "growth_form": "coppice"
                if zip_name.startswith("coppice")
                else "single_stem",
                "leaf_state": "off",
                "dbh_m_reported": _float(row.get("DBHqsm_m")),
                "height_m_reported": _float(row.get("height_m")),
                "volume_m3_reported": _float(row.get("TotalVolume_m3")),
                "x_site": _float(row.get("x")),
                "y_site": _float(row.get("y")),
                "crs_site": "EPSG:27700" if row else None,
                **normalize_species(row.get("species")),
            }
            # the csv's habitat is only a fallback: some conifer-habitat rows name an oak
            if meta["leaf_type"] is None and row.get("habitat") in (
                "conifer",
                "broadleaf",
            ):
                meta["leaf_type"] = row["habitat"]
            tree = _guard(
                member, lambda d=data, m=meta: standardize(read_treeqsm_mat(d), m)
            )
            if tree:
                yield tree


# --- Belgium destructive: TreeQSM struct, reference volume in the harvest csv ----------

_BELGIUM_SPECIES = {
    "FEXC": "Fraxinus excelsior",
    "FSYL": "Fagus sylvatica",
    "LXDC": "Larix decidua",
    "PSYLA": "Pinus sylvestris",
    "PSYLB": "Pinus sylvestris",
}


def belgium(dataset_dir: Path) -> Iterator[QsmTree]:
    """``optimal_QSMs.zip`` plus ``Destructive_and_qsm_data_DEMOL.csv`` (DBH in cm, volumes
    in dm3, i.e. litres)."""
    with open(
        dataset_dir / "Destructive_and_qsm_data_DEMOL.csv", newline="", encoding="utf-8"
    ) as fh:
        harvest = {
            (r["site_name"], int(r["tree_name"].rsplit("-", 1)[1])): r
            for r in csv.DictReader(fh)
        }
    for member, data in _mat_members(dataset_dir / "optimal_QSMs.zip"):
        tree_id = Path(member).stem
        site, number = re.fullmatch(r"([A-Z]+)(\d+)", tree_id).groups()
        row = harvest.get((site, int(number)), {})
        meta = {
            "tree_uid": f"belgium:{tree_id}",
            "source": "belgium",
            "source_kind": "scan",
            "source_tree_id": tree_id,
            "tier": "B",
            "plot": site,
            "growth_form": "single_stem",
            "leaf_state": "off",
            "dbh_m_reported": _scale(_float(row.get("DBH")), 0.01),
            "height_m_reported": _float(row.get("TH_felled")),
            "volume_m3_reported": _scale(_float(row.get("qsm_mean_volume")), 0.001),
            "volume_m3_reference": _scale(
                _float(row.get("Volume_total_tree_harvested")), 0.001
            ),
            "qsm_version": "2.3",  # as documented on the Zenodo record; the file is the 2.4 layout
            **normalize_species(_BELGIUM_SPECIES.get(site)),
        }
        tree = _guard(
            member, lambda d=data, m=meta: standardize(read_treeqsm_mat(d), m)
        )
        if tree:
            yield tree


# --- Ghent pulse-frequency: flat TreeQSM layout, no species ----------------------------

# plots: AUS (Austria), GAB (Gabon, tropical), BEoff / BEon (Belgium, leaf-off / leaf-on);
# Austria and Gabon names carry a scan number after the tree number
_GHENT = re.compile(
    r"(?P<plot>[A-Za-z]+)_(?P<khz>\d+)kHz_(?P<tree>\d+)(?:_(?P<scan>\d\d)(?=_))?"
)


_GHENT_LEAF = {"BEoff": "off", "BEon": "on"}  # the other plots do not say


def ghent(dataset_dir: Path) -> Iterator[QsmTree]:
    """``optimal_QSMs.zip``: the file name carries plot, pulse frequency and tree number.
    The same tree appears once per pulse frequency, so ``source_tree_id`` keeps the
    frequency. No species, DBH or height is published with the models. The plots are
    Austria, Gabon (tropical, not a European reference) and Belgium scanned leaf-off and
    leaf-on; ``leaf_state`` follows the plot."""
    for member, data in _mat_members(dataset_dir / "optimal_QSMs.zip"):
        parts = _GHENT.match(Path(member).name)
        tree_id = (
            "_".join(g for g in parts.group("plot", "khz", "tree", "scan") if g)
            if parts
            else Path(member).stem
        )
        meta = {
            "tree_uid": f"ghent:{tree_id}",
            "source": "ghent",
            "source_kind": "scan",
            "source_tree_id": tree_id,
            "tier": "C",
            "plot": parts.group("plot") if parts else None,
            "growth_form": "unknown",
            "leaf_state": _GHENT_LEAF.get(
                parts.group("plot") if parts else "", "unknown"
            ),
            **normalize_species(None),
        }
        tree = _guard(
            member, lambda d=data, m=meta: standardize(read_treeqsm_mat(d), m)
        )
        if tree:
            yield tree


# --- growpy catalog: generated Grove trees, the other side of every comparison --------

_CATALOG = re.compile(r"_r(?P<radius>\d+)_h(?P<height>\d+)m_d(?P<dbh>\d+)cm")
_LATIN_OF_KEY = {key: latin for latin, key in reversed(SPECIES_KEY.items())}


def growpy_forest(forest_dir: Path) -> Iterator[QsmTree]:
    """``data/output/forest/<species_key>/r<radius>/<name>_r07_h05m_d06cm_*_growth_data.json``.
    The file name carries the catalog cell: surround radius, height stage and the
    yield-table DBH realised at export (the json's own radii are Grove's raw ones)."""
    for path in sorted(forest_dir.glob("*/*/*_growth_data.json")):
        cell = _CATALOG.search(path.name)
        species_key = path.parts[-3]
        tree_id = path.name.removesuffix("_growth_data.json")
        meta = {
            "tree_uid": f"growpy:{species_key}:{tree_id}",
            "source": "growpy",
            "source_kind": "generated",
            "source_tree_id": tree_id,
            "plot": f"r{cell.group('radius')}" if cell else None,
            "growth_form": "single_stem",
            "dbh_m_reported": int(cell.group("dbh")) / 100 if cell else None,
            "height_m_reported": float(cell.group("height")) if cell else None,
            **normalize_species(_LATIN_OF_KEY.get(species_key)),
        }
        tree = _guard(
            path.name, lambda p=path, m=meta: standardize(read_growth_json(p), m)
        )
        if tree:
            yield tree


# --- TreeML-Data (Munich street trees): optcsv cylinders, species in the QSM table -------


def treeml(dataset_dir: Path) -> Iterator[QsmTree]:
    """``Dataset_QSM.zip`` (``<project>/optcsv/OptQSM_<treeID>.csv``) plus
    ``TreeML_Dataset_QSM.csv`` (botanical name, DBH, height, volume in litres)."""
    # the table has 1,168 columns (crown widths per direction); read the few we map
    wanted = [
        "treeID",
        "projectID",
        "botanical_name",
        "DBH_m_",
        "treeHeight_m_",
        "crownProjectionArea_m2_",
        "totalVolume_L_",
        "location_latitude",
        "location_longitude",
    ]
    table = (
        pd.read_csv(
            dataset_dir / "TreeML_Dataset_QSM.csv",
            usecols=wanted,
            encoding="cp1252",  # not utf-8: 'Platanus × acerifolia' carries a latin-1 ×
            dtype=str,
            keep_default_na=False,
        )
        .set_index("treeID", drop=False)
        .to_dict("index")
    )
    with zipfile.ZipFile(dataset_dir / "Dataset_QSM.zip") as z:
        for name in sorted(
            n for n in z.namelist() if "/optcsv/" in n and n.endswith(".csv")
        ):
            tree_id = Path(name).stem.removeprefix("OptQSM_")
            row = table.get(tree_id, {})
            meta = {
                "tree_uid": f"treeml:{tree_id}",
                "source": "treeml",
                "source_kind": "scan",
                "source_tree_id": tree_id,
                "tier": "C",
                "plot": row.get("projectID") or Path(name).parts[1],
                "growth_form": "single_stem",
                "leaf_state": "off",
                "dbh_m_reported": _float(row.get("DBH_m_")),
                "height_m_reported": _float(row.get("treeHeight_m_")),
                "volume_m3_reported": _scale(_float(row.get("totalVolume_L_")), 0.001),
                "cpa_m2_reported": _float(row.get("crownProjectionArea_m2_")),
                "x_site": _float(row.get("location_longitude")),
                "y_site": _float(row.get("location_latitude")),
                "crs_site": "EPSG:4326" if row else None,
                **normalize_species(row.get("botanical_name")),
            }
            data = z.read(name)
            tree = _guard(
                name, lambda d=data, m=meta: standardize(read_treeml_csv(d), m)
            )
            if tree:
                yield tree


# --- BioDiv-3DTrees: graphs (and, once downloaded, corrected csv), labels.csv ----------


def biodiv_labels(labels_csv: Path) -> dict[str, dict]:
    with open(labels_csv, newline="", encoding="utf-8") as fh:
        return {r["treeID"]: r for r in csv.DictReader(fh)}


def biodiv_meta(tree_id: str, label: dict) -> dict:
    valid = _bool(label.get("validQSM"))
    return {
        "tree_uid": f"biodiv:{tree_id}",
        "source": "biodiv",
        "source_kind": "scan",
        "source_tree_id": tree_id,
        "tier": "A" if valid else "C",
        "plot": label.get("ep"),
        "growth_form": "single_stem",
        "leaf_state": "off",
        "dbh_m_reported": _scale(_float(label.get("dTLS")), 0.01),  # cm in the file
        "height_m_reported": _float(label.get("hTLS")),
        "volume_m3_reported": _float(label.get("volQSM")),  # unit checked in the tests
        "cpa_m2_reported": _float(label.get("cpaHTLS")),
        "valid_dbh": _bool(label.get("validDBH")),
        "valid_height": _bool(label.get("validH")),
        "valid_cpa": _bool(label.get("validCPA")),
        "valid_qsm": valid,
        **normalize_species(label.get("species")),
    }


def biodiv(corrected_dir: Path, labels_csv: Path) -> Iterator[QsmTree]:
    """The rTwig-corrected QSMs, ``QSM/corrected/<treeID>_cor.csv``, and the labels table.
    Tier A only where ``validQSM`` is true; the rest are kept as tier C."""
    labels = biodiv_labels(labels_csv)
    for path in sorted(corrected_dir.glob("*_cor.csv")):
        tree_id = path.name.removesuffix("_cor.csv")
        meta = biodiv_meta(tree_id, labels.get(tree_id, {}))
        tree = _guard(
            path.name, lambda p=path, m=meta: standardize(read_rtwig_csv(p), m)
        )
        if tree:
            yield tree


def biodiv_graphs(graph_dir: Path, labels_csv: Path) -> Iterator[QsmTree]:
    """GraphML files named ``<treeID>_cor_graph.graphml`` and the labels table."""
    labels = biodiv_labels(labels_csv)
    for path in sorted(graph_dir.glob("*.graphml")):
        tree_id = path.name.replace("_cor_graph.graphml", "").replace(".graphml", "")
        meta = biodiv_meta(tree_id, labels.get(tree_id, {}))
        tree = _guard(path.name, lambda p=path, m=meta: standardize(read_graphml(p), m))
        if tree:
            yield tree
