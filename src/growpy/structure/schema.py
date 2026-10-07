"""The canonical QSM representation every reference source is converted to.

The sources do not share a format. TreeQSM writes a ``qsm.cylinder`` struct in 2.4 and
flat arrays (``Sta``, ``Axe``, ``Rad``, ``CPar`` ...) in older versions; BioDiv-3DTrees
ships rTwig CSVs and point graphs; TreeML ships TreeQSM-derived CSVs; Czech ships
meshes only. What they have in common is the TreeQSM cylinder model, so that is the
canonical form, written in the conventions TreeQSM, rTwig and ``digital-twin-db`` already
share (``exchange.py``): one row per cylinder, ``id`` from 1, ``parent`` 0 for the base,
metres, z up, tree base at the origin. Everything the sources disagree on (branch ids,
branch orders, radius correction, metadata) is either recomputed here by one rule or kept
side by side with its provenance.

Two tables per dataset:

``cylinders``  one row per cylinder, ``CYL_COLUMNS``
``trees``      one row per tree, ``TREE_COLUMNS``: identity, species, what the source
               reported, what we measure on the cylinders with one code path, QSM
               provenance, and quality-control numbers (no pass/fail: there are no
               calibrated thresholds yet)
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# The exchange table, one row per cylinder (rTwig / TreeQSM names and index base).
# ``branch*`` hold the lab's single axis rule (``axes.assign_axes``); what the source
# said about branches is kept as ``src_*`` and is only a cross-check.
CYL_COLUMNS = [
    "id",  # from 1
    "parent",  # id of the cylinder it grows from, 0 for the base
    "start_x",
    "start_y",
    "start_z",
    "axis_x",  # unit vector from start to end
    "axis_y",
    "axis_z",
    "end_x",
    "end_y",
    "end_z",
    "length",
    "radius",  # as delivered: corrected where the source corrects (see radius_correction)
    "raw_radius",  # before any correction; empty when the source does not keep it
    "is_virtual",  # cylinder added to bridge a gap in the cloud
    "branch",  # from 1
    "branch_order",  # 0 = trunk
    "branch_position",  # from 1 at the base of the branch
    "src_branch",  # the source's own branch id, empty when it has none
    "src_order",
    "src_position",
    "src_extension",  # id of the cylinder the source says continues this one, 0 unknown
]

TIERS = {
    "A": "documented validation flags and corrected topology",
    "B": "independent destructive reference volume",
    "C": "published QSM, no strong independent check",
}

TREE_COLUMNS = [
    # identity
    "tree_uid",
    "source",
    "source_kind",  # scan | generated
    "source_tree_id",
    "tier",
    "plot",
    # species, normalised (species_raw is what the source wrote)
    "species_raw",
    "species_latin",
    "genus",
    "species_rank",  # species | genus | unknown
    "species_key",  # growpy species key, or empty
    "leaf_type",  # broadleaf | conifer
    "growth_form",  # single_stem | coppice | unknown
    # reported by the source
    "dbh_m_reported",
    "height_m_reported",
    "volume_m3_reported",  # the QSM volume the source states
    "volume_m3_reference",  # harvested reference volume, destructive datasets only
    "cpa_m2_reported",
    "x_site",
    "y_site",
    "crs_site",
    "leaf_state",  # off | on | unknown
    "valid_dbh",
    "valid_height",
    "valid_cpa",
    "valid_qsm",
    # QSM provenance
    "qsm_tool",
    "qsm_version",
    "qsm_format",
    "radius_correction",  # none | treeqsm_taper | rtwig | unknown
    # measured here on the cylinders, identical code for every source
    "base_x_src",
    "base_y_src",
    "base_z_src",
    "n_cyl",
    "n_axes",
    "max_axis_order",
    "height_m",
    "dbh_m",
    "volume_m3",
    "trunk_length_m",
    "branch_length_m",
    "crown_base_m",
    "radius_min_m",
    "length_median_m",
    "virtual_frac",
    # quality control
    "n_roots",  # bases in the source table; more than 1 means loose fragments
    "detached_cyl",  # cylinders not connected to the main base, dropped
    "detached_length_m",
    "gap_frac",  # share of cylinders whose start is clear of the parent's axis
    "thick_branch_frac",  # axis bases thicker than the cylinder they grow from
    "axis_agreement",  # our continuation rule against the source's extension
]

# growpy species keys (data/assets/presets) by Latin binomial. Genus-level names only
# resolve where growpy has one preset for the whole genus' native range.
SPECIES_KEY = {
    "Fagus sylvatica": "european_beech",
    "Quercus robur": "european_oak",
    "Quercus petraea": "european_oak",
    "Fraxinus excelsior": "common_ash",
    "Picea abies": "norway_spruce",
    "Pinus sylvestris": "scots_pine",
    "Abies alba": "silver_fir",
    "Pseudotsuga menziesii": "douglas_fir",
    "Betula pendula": "silver_birch",
    "Tilia cordata": "small_leaved_linden",
    "Acer pseudoplatanus": "sycamore_maple",
    "Prunus avium": "wild_cherry",
}
_GENUS_KEY = {"Quercus": "european_oak"}  # both native oaks share the preset
_CONIFER_GENERA = {
    "Picea",
    "Pinus",
    "Abies",
    "Larix",
    "Pseudotsuga",
    "Taxus",
    "Juniperus",
    "Cupressus",
    "Tsuga",
    "Thuja",
}
_GENUS_ONLY = {"spec", "sp", "spp", "species"}


def normalize_species(raw: str | None) -> dict:
    """Species columns from whatever a source wrote (``Fagus_sylvatica``, ``Quercus_spec``,
    ``Populus nigra 'Italica'``, ``Larix x decidua``). Unparseable input stays unknown."""
    out = {
        "species_raw": raw,
        "species_latin": None,
        "genus": None,
        "species_rank": "unknown",
        "species_key": None,
        "leaf_type": None,
    }
    if not raw or not str(raw).strip():
        return out
    words = str(raw).replace("_", " ").replace("×", " ").split()
    words = [
        w for w in words if w.lower() not in {"x"} and not w.startswith(("'", '"'))
    ]
    if not words:
        return out
    genus = words[0].capitalize()
    out["genus"] = genus
    out["leaf_type"] = "conifer" if genus in _CONIFER_GENERA else "broadleaf"
    if len(words) == 1 or words[1].lower().rstrip(".") in _GENUS_ONLY:
        out.update(
            species_latin=f"{genus} sp.",
            species_rank="genus",
            species_key=_GENUS_KEY.get(genus),
        )
        return out
    latin = f"{genus} {words[1].lower()}"
    out.update(
        species_latin=latin,
        species_rank="species",
        species_key=SPECIES_KEY.get(latin),
    )
    return out


@dataclass
class QsmTree:
    """One standardised tree: ``meta`` is a ``TREE_COLUMNS`` dict, ``cyl`` a
    ``CYL_COLUMNS`` frame in the canonical frame."""

    meta: dict
    cyl: pd.DataFrame
