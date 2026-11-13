"""Print version of the tree catalog: structure, twigs and bark materials in one A4 PDF.

    growpy-catalog-print --publish   # beside the catalog in the UE project + hub copy
    growpy-catalog-print --previews <dir> --out catalog.pdf

* Overview: per species the stand radii and heights in the structure catalog, the twig
  prototypes with renders, the bark source and its licence -- the completeness check.
* Structure: per species one page, each stand radius a row of side views at true scale.
* Twigs: per species one page of prototype renders, with leaf area, size and triangles.
* Materials: every species' bark on a 40 cm stem section, with source and licence.

Twig and bark renders come from ue_scripts/capture_catalog_previews.py (run in the
editor); structure is drawn here from the growth JSONs. Missing renders show as gaps,
which is the point. growpy-pve-export publishes after every export, so the print stays
live. Its home is the hub (owner, 2026-11-13), with a copy beside the UE catalog.
"""

import argparse
import datetime as dt
import json
import logging
import re
import shutil
import sys
import textwrap
import tomllib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from PIL import Image  # noqa: E402

logger = logging.getLogger(__name__)

A4_LANDSCAPE = (11.69, 8.27)
REPO = Path(__file__).resolve().parents[3]
FOREST = REPO / "data/output/forest"
ASSETS = REPO / "data/assets"
MATERIAL_CATALOG = REPO / "data/input/materials/catalog.toml"
CALIBRATION = REPO / "config/pve_calibration.toml"
HUB = REPO.parent / "xr-future-forests-lab/obsidian/xr-future-forests-lab"
PDF_NAME = "XRFF_TreeCatalog.pdf"
HEIGHT = re.compile(r"_r(\d\d)_h(\d\d)m_")


def ladder(forest: Path, species: str) -> dict[int, dict[int, Path]]:
    """Stand radius -> height -> growth JSON (the emitted ones, not plan copies)."""
    out: dict[int, dict[int, Path]] = {}
    for f in sorted((forest / species).glob("r??/*_full_growth_data.json")):
        m = HEIGHT.search(f.name)
        if m:
            out.setdefault(int(m.group(1)), {})[int(m.group(2))] = f
    return out


def side_view(ax, path: Path, pt_per_m: float) -> float:
    """Draw a growth JSON side-on at true scale (Y up, metres); returns its height."""
    d = json.loads(path.read_text(encoding="utf-8"))
    pos = d["points"]["positions"]
    rad = [m[0] for m in d["points"]["attributes"]["budLateralMeristem"]["values"]]
    x0 = pos[d["primitives"]["points"][0][0]][0] if d["primitives"]["points"] else 0.0
    segs, diam = [], []
    for pts in d["primitives"]["points"]:
        for a, b in zip(pts, pts[1:], strict=False):
            segs.append(((pos[a][0] - x0, pos[a][1]), (pos[b][0] - x0, pos[b][1])))
            diam.append(rad[a] + rad[b])
    ax.add_collection(
        LineCollection(
            segs,
            linewidths=[max(0.1, w * pt_per_m) for w in diam],
            colors="#5b4632",
            capstyle="round",
            rasterized=True,
        )
    )
    return max(p[1] for p in pos) - min(p[1] for p in pos)


def leaf_area(name: str, assets: Path = ASSETS) -> float | None:
    for f in list(assets.glob(f"twigs/*/{name}_leaf_area_geom.json")) + list(
        assets.glob(f"compound_parts/{name}_leaf_area_geom.json")
    ):
        return float(json.loads(f.read_text(encoding="utf-8")).get("leaf_area_m2", 0.0))
    return None


def bark_source(species: str, calibration: dict, materials: dict) -> tuple[str, str]:
    """(source, licence) of a species' bark, from its bark source and the catalog."""
    src = calibration.get("bark_source_per_species", {}).get(species)
    if not src:
        return "Grove bark texture", "Grove asset licence"
    path = src.get("material", "")
    for mid, m in materials.items():
        if m.get("instance") and path.startswith(m["instance"].split(".")[0]):
            free = (
                "redistributable"
                if m.get("redistributable", True)
                else "inside the UE project only"
            )
            return f"{mid} ({m.get('source', '?')})", f"{m.get('licence', '?')}, {free}"
    if path.startswith("/Game/00_XRFF/"):
        return path.split("/")[-1], "XRFF project material, no intake entry"
    if "/Megaplant_Library/" in path:
        return path.split("/")[-1], "MegaPlants (reference library)"
    return path.split("/")[-1], "?"


def overview_page(pdf, species, forest, previews, calibration, materials):
    fig = plt.figure(figsize=A4_LANDSCAPE)
    fig.suptitle(
        "XR Future Forests tree catalog: overview", fontsize=14, x=0.05, ha="left"
    )
    rows = [
        [sp, struct, twigs, textwrap.fill(src, 34), textwrap.fill(lic, 30)]
        for sp, struct, twigs, src, lic in overview_rows(
            species, forest, previews, calibration, materials
        )
    ]
    ax = fig.add_axes((0.03, 0.05, 0.94, 0.85))
    ax.axis("off")
    table = ax.table(
        cellText=rows,
        colLabels=[
            "Species",
            "Structure (stand radius: heights)",
            "Twig renders",
            "Bark source",
            "Bark licence",
        ],
        loc="upper left",
        cellLoc="left",
        colWidths=[0.13, 0.30, 0.09, 0.26, 0.22],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7.5)
    table.scale(1, 2.4)
    pdf.savefig(fig)
    plt.close(fig)


def structure_page(pdf, sp, forest):
    lad = ladder(forest, sp)
    if not lad:
        return
    heights = sorted({h for hs in lad.values() for h in hs})
    top = max(heights) + 3
    fig, axes = plt.subplots(
        len(lad), len(heights), figsize=A4_LANDSCAPE, squeeze=False, sharey=True
    )
    fig.suptitle(
        f"Structure: {sp.replace('_', ' ')} (side view, true scale, metres)",
        fontsize=12,
        x=0.05,
        ha="left",
    )
    for ax in axes.flat:
        ax.set_xlim(-8, 8)
        ax.set_ylim(0, top)
    fig.canvas.draw()  # once: every panel has the same width, so one scale fits all
    pt_per_m = axes[0][0].get_window_extent().width * 72 / fig.dpi / 16.0
    for r_i, (r, hs) in enumerate(sorted(lad.items())):
        for c_i, h in enumerate(heights):
            ax = axes[r_i][c_i]
            ax.set_xticks([-5, 0, 5])
            ax.tick_params(labelsize=6)
            ax.grid(alpha=0.15)
            ax.set_title(f"r{r:02d} h{h:02d}", fontsize=8)
            if h in hs:
                side_view(ax, hs[h], pt_per_m)
            else:
                ax.text(0, top / 2, "missing", ha="center", color="0.5", fontsize=7)
    pdf.savefig(fig, dpi=200)  # the rasterised branch lines
    plt.close(fig)


def image_grid(pdf, title, items):
    """items: (image path or None, caption); 4 x 3 per page."""
    for start in range(0, max(len(items), 1), 12):
        fig, axes = plt.subplots(3, 4, figsize=A4_LANDSCAPE)
        fig.suptitle(title, fontsize=12, x=0.05, ha="left")
        for ax, item in zip(
            axes.flat, items[start : start + 12] + [None] * 12, strict=False
        ):
            ax.axis("off")
            if item is None:
                continue
            path, caption = item
            if path is not None and path.is_file():
                ax.imshow(np.asarray(Image.open(path).convert("RGB")))
            else:
                ax.text(
                    0.5,
                    0.5,
                    "no render",
                    ha="center",
                    va="center",
                    color="0.5",
                    transform=ax.transAxes,
                )
            ax.set_title(caption, fontsize=6.5)
        pdf.savefig(fig)
        plt.close(fig)


def twig_items(previews: Path, sp: str):
    idx = previews / sp / "index.json"
    if not idx.is_file():
        return []
    items = []
    for t in json.loads(idx.read_text(encoding="utf-8"))["twigs"]:
        la = leaf_area(t["name"])
        size = " x ".join(f"{v:.0f}" for v in t.get("size_cm", [])) + " cm"
        tri = f", {t['triangles'] / 1000:.0f}k tri" if t.get("triangles") else ""
        area = f", {la:.3f} m2 leaves" if la is not None else ""
        items.append((previews / sp / t["png"], f"{t['name']}\n{size}{area}{tri}"))
    return items


def overview_rows(species, forest, previews, calibration, materials):
    """(species, structure, twig renders, bark source, bark licence), unwrapped."""
    rows = []
    for sp in species:
        lad = ladder(forest, sp)
        struct = (
            "; ".join(
                f"r{r:02d}: h{min(h):02d}-h{max(h):02d} ({len(h)})"
                for r, h in sorted(lad.items())
            )
            or "none"
        )
        idx = previews / sp / "index.json"
        twigs = (
            len(json.loads(idx.read_text(encoding="utf-8"))["twigs"])
            if idx.is_file()
            else 0
        )
        src, lic = bark_source(sp, calibration, materials)
        rows.append(
            (
                sp.replace("_", " "),
                struct,
                str(twigs) if twigs else "no renders",
                src,
                lic,
            )
        )
    return rows


def hub_note(rows, pdf_name: str) -> str:
    """The hub's generated overview note: the PDF's first page as a Markdown table."""
    lines = [
        "---",
        "title: Tree catalog overview",
        f"updated: {dt.date.today():%Y-%m-%d}",
        "generated: growpy-catalog-print --publish after each export; do not edit",
        "---",
        "",
        "# Tree catalog overview",
        "",
        "Structure (skeleton ladder per stand radius), twigs (rendered prototypes) and",
        "bark material (source, licence) behind every tree asset. The print version",
        "below shows every skeleton, twig and bark; the same PDF sits beside the",
        "catalog in the UE project (`Content/Generated/Trees/`).",
        "",
        "| Species | Structure (stand radius: heights) | Twig renders "
        "| Bark source | Bark licence |",
        "|---|---|---|---|---|",
    ]
    lines += [
        "| " + " | ".join(c.replace("|", "/") for c in row) + " |" for row in rows
    ]
    lines += [
        "",
        f"![[{pdf_name}]]",
        "",
        "Related: [[04-LOGIC-TIER/tree-catalog-architecture-2026-11]]",
        "",
    ]
    return "\n".join(lines)


def publish(project: Path, hub: Path | None = HUB) -> Path:
    """Rebuild the print beside the UE catalog; copy it and a note to the hub."""
    previews = project / "Saved" / "growpy_catalog_previews"
    out = project / "Content" / "Generated" / "Trees" / PDF_NAME
    build(previews, out)
    if hub is not None and hub.is_dir():
        shutil.copy2(out, hub / "Pics" / PDF_NAME)
        calibration = tomllib.loads(CALIBRATION.read_text(encoding="utf-8")).get(
            "pve_calibration", {}
        )
        materials = (
            tomllib.loads(MATERIAL_CATALOG.read_text(encoding="utf-8")).get(
                "materials", {}
            )
            if MATERIAL_CATALOG.is_file()
            else {}
        )
        species = sorted(
            p.name for p in FOREST.iterdir() if p.is_dir() and any(p.glob("r??"))
        )
        rows = overview_rows(species, FOREST, previews, calibration, materials)
        (hub / "04-LOGIC-TIER" / "tree-catalog-overview.md").write_text(
            hub_note(rows, PDF_NAME), encoding="utf-8"
        )
    return out


def build(previews: Path, out: Path, forest: Path = FOREST) -> int:
    calibration = tomllib.loads(CALIBRATION.read_text(encoding="utf-8")).get(
        "pve_calibration", {}
    )
    materials = (
        tomllib.loads(MATERIAL_CATALOG.read_text(encoding="utf-8")).get("materials", {})
        if MATERIAL_CATALOG.is_file()
        else {}
    )
    species = sorted(
        p.name for p in forest.iterdir() if p.is_dir() and any(p.glob("r??"))
    )
    pages = 0
    with PdfPages(out) as pdf:
        overview_page(pdf, species, forest, previews, calibration, materials)
        for sp in species:
            structure_page(pdf, sp, forest)
        for sp in species:
            image_grid(pdf, f"Twigs: {sp.replace('_', ' ')}", twig_items(previews, sp))
        bark = []
        for sp in species:
            src, lic = bark_source(sp, calibration, materials)
            bark.append(
                (previews / sp / "bark", f"{sp.replace('_', ' ')}\n{src}\n{lic}")
            )
        image_grid(pdf, "Materials: bark on a 40 cm stem section", bark)
        pages = pdf.get_pagecount()
    return pages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--previews", type=Path, help="capture_catalog_previews.py output folder"
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="write beside the catalog in the UE project and copy it to the hub",
    )
    parser.add_argument(
        "--project",
        type=Path,
        help="UE project folder (default: [unreal] uproject or the running editor)",
    )
    parser.add_argument("--forest", type=Path, default=FOREST)
    parser.add_argument(
        "--out", type=Path, default=Path("data/output/catalog_print/tree_catalog.pdf")
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.publish:
        project = args.project
        if project is None:
            from growpy.tools.pve_export import _find_log_path

            project = _find_log_path(None).parents[2]  # <project>/Saved/Logs/<name>.log
        logger.info("published -> %s", publish(project))
        return 0
    if args.previews is None:
        parser.error("--previews is required without --publish")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    pages = build(args.previews, args.out, args.forest)
    logger.info("%d pages -> %s", pages, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
