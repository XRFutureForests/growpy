"""Catalog print: bark licence mapping, ladder parsing and a PDF from a tiny forest."""

import json

from growpy.tools import catalog_print as cp

MATERIALS = {
    "fab_oak_bark": {
        "instance": "/Game/Generated/Trees/Materials/Bark/MI_fab_oak_bark.MI",
        "source": "fab",
        "licence": "Fab Standard",
        "redistributable": False,
    }
}


def test_bark_source_flags_fab_materials_as_project_only():
    cal = {
        "bark_source_per_species": {
            "oak": {"material": "/Game/Generated/Trees/Materials/Bark/MI_fab_oak_bark"},
            "lime": {"material": "/Game/00_XRFF/Materials/MI_Lime"},
        }
    }
    assert cp.bark_source("oak", cal, MATERIALS) == (
        "fab_oak_bark (fab)",
        "Fab Standard, inside the UE project only",
    )
    assert cp.bark_source("lime", cal, MATERIALS)[1].startswith("XRFF project")
    assert cp.bark_source("ash", cal, MATERIALS)[0] == "Grove bark texture"


def _growth_json(path, height):
    path.write_text(
        json.dumps(
            {
                "points": {
                    "positions": [[0, 0, 0], [0, height, 0]],
                    "attributes": {
                        "budLateralMeristem": {"values": [[0.2] * 6, [0.01] * 6]}
                    },
                },
                "primitives": {"points": [[0, 1]]},
            }
        ),
        encoding="utf-8",
    )


def test_build_draws_the_ladder_and_leaves_gaps_for_missing_renders(tmp_path):
    forest = tmp_path / "forest"
    for r, h in ((7, 5), (7, 10), (10, 5)):
        d = forest / "test_tree" / f"r{r:02d}"
        d.mkdir(parents=True, exist_ok=True)
        _growth_json(d / f"TestTree_r{r:02d}_h{h:02d}m_full_growth_data.json", h)
    assert {r: sorted(h) for r, h in cp.ladder(forest, "test_tree").items()} == {
        7: [5, 10],
        10: [5],
    }
    out = tmp_path / "print.pdf"
    pages = cp.build(tmp_path / "no_previews", out, forest)
    assert out.stat().st_size > 0
    assert pages == 4  # overview, structure, twigs (empty), materials
    rows = cp.overview_rows(["test_tree"], forest, tmp_path / "no_previews", {}, {})
    assert rows[0][1:3] == ("r07: h05-h10 (2); r10: h05-h05 (1)", "no renders")
    assert "| test tree |" in cp.hub_note(rows, cp.PDF_NAME)
