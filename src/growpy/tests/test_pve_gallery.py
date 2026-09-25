"""Tests for growpy.tools.pve_gallery.

The gallery exists to be looked at, so the layout is what matters: no two crowns
may overlap, the columns must read h05 -> h45 from the left, and every species
needs its label strip in front. The one refusal worth pinning is the bone cap,
because a mesh over it crashes the editor on spawn and a level holding one
crashes on every open (2026-09-25).
"""

from __future__ import annotations

import ast
import itertools

import pytest

from growpy.tools.pve_gallery import (
    MAX_BONES,
    build_ue_script,
    gallery_groups,
    gallery_layout,
    gallery_records,
    row_framings,
)


def _manifest(entries):
    return {
        "graphs": [
            {
                "graph_asset": "/Game/Assets/Trees/Graphs/PVG_X_1",
                "meshes": [
                    {
                        "mesh_name": f"SK_{sp}_{tid}",
                        "species": sp,
                        "tree_id": tid,
                        "asset": f"/Game/Assets/Trees/Catalog/{sp}/SK_{sp}_{tid}",
                    }
                    for sp, tid in entries
                ],
            }
        ]
    }


def _records(widths):
    """widths: {(species, radius, stage): width_cm}"""
    return [
        {
            "key": f"{sp}__r{rad:02d}_h{st:02d}m",
            "species": sp,
            "radius": rad,
            "stage": st,
            "width_cm": w,
        }
        for (sp, rad, st), w in sorted(widths.items())
    ]


class TestRecords:
    def test_sorted_species_radius_stage_whatever_the_manifest_order(self):
        records = gallery_records(
            _manifest(
                [
                    ("silver_fir", "r07_h10m"),
                    ("common_ash", "r10_h05m"),
                    ("common_ash", "r00_h45m"),
                    ("common_ash", "r00_h05m"),
                ]
            )
        )
        assert [r["key"] for r in records] == [
            "common_ash__r00_h05m",
            "common_ash__r00_h45m",
            "common_ash__r10_h05m",
            "silver_fir__r07_h10m",
        ]
        assert records[0]["radius"] == 0 and records[1]["stage"] == 45
        assert records[0]["species_label"] == "Common Ash"

    def test_species_filter(self):
        records = gallery_records(
            _manifest([("silver_fir", "r07_h10m"), ("common_ash", "r10_h05m")]),
            ["silver_fir"],
        )
        assert [r["species"] for r in records] == ["silver_fir"]

    def test_a_mesh_without_a_tree_id_is_refused(self):
        with pytest.raises(ValueError, match="tree_id"):
            gallery_records(_manifest([("silver_fir", "h10")]))

    def test_one_level_per_species_by_default(self):
        records = gallery_records(
            _manifest([("silver_fir", "r07_h10m"), ("common_ash", "r10_h05m")])
        )
        groups = gallery_groups(records, None)
        assert [(level, name) for level, name, _ in groups] == [
            ("/Game/Levels/TreeGallery/TreeGallery_CommonAsh", "common_ash"),
            ("/Game/Levels/TreeGallery/TreeGallery_SilverFir", "silver_fir"),
        ]
        assert all({r["species"] for r in group} == {name} for _, name, group in groups)

    def test_a_named_level_takes_every_selected_species(self):
        records = gallery_records(
            _manifest([("silver_fir", "r07_h10m"), ("common_ash", "r10_h05m")])
        )
        ((level, name, group),) = gallery_groups(records, "/Game/Levels/Firs")
        assert (level, name, len(group)) == ("/Game/Levels/Firs", "firs", 2)

    def test_a_species_over_the_bone_budget_is_split_by_stand_rows(self):
        # A Douglas fir level of ~350k wind-tree bones overflowed the skinning
        # transform buffer; ECOSENSE's ~220k renders.
        records = gallery_records(
            _manifest(
                [
                    ("douglas_fir", f"r{r:02d}_h{h:02d}m")
                    for r in (0, 7, 10)
                    for h in (5, 45)
                ]
            )
        )
        # two trees per row, each under the 32,767-bone cap
        weights = {0: 30_000, 7: 10_000, 10: 15_000}
        groups = gallery_groups(
            records, None, budget=70_000, bones_of=lambda r: weights[r["radius"]]
        )
        assert [(level.rsplit("/", 1)[1], name) for level, name, _ in groups] == [
            ("TreeGallery_DouglasFir_r00", "douglas_fir_r00"),
            ("TreeGallery_DouglasFir_r07_r10", "douglas_fir_r07_r10"),
        ]
        assert sum(len(g) for _, _, g in groups) == len(records)

    def test_a_species_under_the_budget_stays_in_one_level(self):
        records = gallery_records(_manifest([("scots_pine", "r07_h10m")]))
        ((level, _, _),) = gallery_groups(records, None, bones_of=lambda r: 5_000)
        assert level.endswith("/TreeGallery_ScotsPine")

    def test_meshes_over_the_bone_cap_do_not_count_towards_the_budget(self):
        # They are never placed, so they must not force a split.
        records = gallery_records(
            _manifest([("silver_fir", "r00_h40m"), ("silver_fir", "r07_h10m")])
        )
        groups = gallery_groups(
            records,
            None,
            budget=10_000,
            bones_of=lambda r: 51_120 if r["radius"] == 0 else 8_000,
        )
        assert len(groups) == 1


class TestLayout:
    WIDTHS = {
        ("beech", 0, 5): 400.0,
        ("beech", 0, 25): 2400.0,
        ("beech", 0, 45): 3000.0,
        ("beech", 7, 5): 300.0,
        ("beech", 7, 25): 1200.0,
        ("fir", 10, 5): 250.0,
        ("fir", 10, 45): 900.0,
    }

    def _layout(self, gap=800.0, block_gap=3000.0):
        records = _records(self.WIDTHS)
        return records, gallery_layout(records, gap, block_gap)

    def test_every_record_is_placed(self):
        records, layout = self._layout()
        assert set(layout["positions"]) == {r["key"] for r in records}

    def test_no_two_crowns_overlap(self):
        records, layout = self._layout(gap=0.0)
        for a, b in itertools.combinations(records, 2):
            ax, ay = layout["positions"][a["key"]]
            bx, by = layout["positions"][b["key"]]
            need = (a["width_cm"] + b["width_cm"]) / 2.0
            # apart along at least one axis by the two half-widths
            assert abs(ax - bx) >= need - 1e-6 or abs(ay - by) >= need - 1e-6, (a, b)

    def test_columns_run_by_stage_from_the_left(self):
        _, layout = self._layout()
        ys = [layout["columns"][s]["y"] for s in sorted(layout["columns"])]
        assert ys == sorted(ys)
        assert sorted(layout["columns"]) == [5, 25, 45]

    def test_a_column_is_as_wide_as_its_widest_crown_plus_the_gap(self):
        _, layout = self._layout(gap=800.0)
        col = layout["columns"][45]
        assert col["y1"] - col["y0"] == pytest.approx(3000.0 + 800.0)

    def test_each_block_has_its_label_strip_in_front(self):
        _, layout = self._layout(block_gap=3000.0)
        previous_end = 0.0
        for block in layout["blocks"]:
            assert block["x0"] - previous_end == pytest.approx(3000.0)
            assert previous_end < block["label_x"] < block["x0"]
            assert all(block["x0"] < row["x"] < block["x1"] for row in block["rows"])
            previous_end = block["x1"]
        assert [b["species"] for b in layout["blocks"]] == ["beech", "fir"]
        assert [r["radius"] for r in layout["blocks"][0]["rows"]] == [0, 7]


class TestScript:
    def _script(self):
        return build_ue_script(
            [
                {
                    "key": "beech__r00_h05m",
                    "species": "beech",
                    "species_label": "Beech",
                    "tree_id": "r00_h05m",
                    "radius": 0,
                    "stage": 5,
                    "asset": "/Game/Assets/Trees/Catalog/beech/SK_Beech_r00_h05m",
                }
            ],
            level="/Game/Levels/TreeGallery/TreeGallery_Beech",
        )

    def test_the_generated_script_parses(self):
        ast.parse(self._script())

    def test_the_bone_cap_guards_every_spawn(self):
        script = self._script()
        assert f"MAX_BONES = {MAX_BONES}" in script
        assert MAX_BONES == 32767
        # the only mesh spawn sits after the cap check in the placement loop
        loop = script.split("# 4. trees", 1)[1]
        assert loop.index('rec["bones"] > MAX_BONES') < loop.index("wind_tree(meshes")

    def test_trees_are_placed_the_way_pcg_trees_spawns_them(self):
        # A SkeletalMeshActor renders the tree but never moves; PVE wind needs an
        # instanced skinned mesh component with the wind transform provider.
        script = self._script()
        assert "unreal.InstancedSkinnedMeshComponent" in script
        assert "set_transform_provider(wind)" in script
        assert "Wind_TransformProvider" in script
        assert "add_instance(" in script
        # the static fallback only past the level's wind budget
        loop = script.split("# 4. trees", 1)[1]
        assert loop.index('rec["bones"] <= wind_left') < loop.index(
            "spawn_actor_from_object"
        )

    def test_it_refuses_to_switch_away_from_unsaved_work(self):
        assert "get_dirty_map_packages" in self._script()

    def test_the_layout_it_embeds_is_this_one(self):
        assert (
            "def gallery_layout(records, gap_cm=800.0, block_gap_cm=3000.0):"
            in self._script()
        )


class TestFramings:
    REPORT = {
        "placed": [
            {
                "species": "fir",
                "radius": 7,
                "stage": 45,
                "height_cm": 4500.0,
                "x": 10000.0,
            },
            {
                "species": "fir",
                "radius": 7,
                "stage": 5,
                "height_cm": 500.0,
                "x": 10000.0,
            },
            {
                "species": "fir",
                "radius": 0,
                "stage": 45,
                "height_cm": 4400.0,
                "x": 8000.0,
            },
        ],
        "columns": {
            "5": {"y0": 0.0, "y1": 1000.0},
            "45": {"y0": 1000.0, "y1": 2000.0},
        },
    }

    def test_the_camera_backs_off_until_the_tallest_tree_fits(self):
        framings = row_framings(self.REPORT, "fir", 7, aspect=16 / 9)
        assert set(framings) == {"short", "tall"}
        (x, _, z), _ = framings["tall"]
        back = 10000.0 - x
        # the part of the tallest tree above the camera fits the vertical view
        assert (4500.0 - z) <= back / (16 / 9) + 1e-6

    def test_a_framing_covers_only_its_own_stages(self):
        (_, y, z), _ = row_framings(self.REPORT, "fir", 7)["short"]
        assert y == pytest.approx(500.0)  # centre of the h05 column only
        assert z == pytest.approx(0.4 * 500.0)  # sized to the h05 tree, not the h45

    def test_each_row_is_framed_from_in_front_of_itself(self):
        (x_open, _, _), _ = row_framings(self.REPORT, "fir", 0)["tall"]
        (x_dense, _, _), _ = row_framings(self.REPORT, "fir", 7)["tall"]
        assert x_open < 8000.0 and x_dense < 10000.0

    def test_a_row_with_nothing_placed_gets_no_framing(self):
        assert row_framings(self.REPORT, "fir", 10) == {}
