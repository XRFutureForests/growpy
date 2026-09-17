"""Tests for PVE's compound branch layer (XRFF-360).

The reference values here were read off the 17 MegaPlants presets shipped with
UE 5.8 under
``Engine/Plugins/Experimental/ProceduralVegetationEditor/Content/SampleAssets``.
They are quoted rather than recomputed: the plugin is not a test dependency.
"""

import pytest

from growpy.io.unreal.pve_hierarchy_builder import (
    DEFAULT_MAX_COMPOUND_GENERATION,
    _bucket_generations,
    build_compound_hierarchy,
)

# Beech_01: branchGeneration histogram {1:3, 2:68, 3:69, 4:41, 5:11, 6:3}
# collapses to compoundBranchGeneration {1:3, 2:137, 3:55}.
BEECH_01_MAP = {1: 1, 2: 2, 3: 2, 4: 3, 5: 3, 6: 3}
# Broadleaf_Hazel_05: {1:1, 2:2, 3:3, 4:3}.
HAZEL_05_MAP = {1: 1, 2: 2, 3: 3, 4: 3}
# Beech_04 splits its middle the other way -- {1:1, 2:2, 3:2, 4:3} where the
# rule here gives {1:1, 2:2, 3:3, 4:3}. Recorded rather than matched: Epic's own
# presets disagree about where the rounding lands, so no single rule fits all 17.
BEECH_04_MAP = {1: 1, 2: 2, 3: 2, 4: 3}
# The identity cases: whenever branchGeneration already fits under the cap,
# compoundBranchGeneration equals it. True of 10 of the 17 shipped presets.
IDENTITY_MAPS = {
    "Broadleaf_Hazel_01": {1: 1, 2: 2, 3: 3},
    "Broadleaf_Hazel_02": {1: 1, 2: 2},
    "QuakingAspen_04": {1: 1, 2: 2, 3: 3},
    "NorwayMaple_03": {1: 1, 2: 2, 3: 3, 4: 3},
}


class TestBucketGenerations:
    """The compound generation is a monotone step function of branchGeneration."""

    def test_empty(self):
        assert _bucket_generations([], 3) == []

    def test_shifts_grove_zero_based_depth_to_pve_one_based(self):
        # Grove calls the trunk generation 0; PVE calls it compound generation 1.
        assert _bucket_generations([0], 3) == [1]

    def test_identity_when_range_already_fits_under_the_cap(self):
        assert _bucket_generations([0, 1, 2], 3) == [1, 2, 3]

    def test_reproduces_beech_01(self):
        depths = list(BEECH_01_MAP)  # 1..6 as PVE axis order
        grove_depths = [d - 1 for d in depths]
        result = _bucket_generations(grove_depths, 3)
        assert dict(zip(depths, result, strict=True)) == BEECH_01_MAP

    def test_reproduces_hazel_05(self):
        depths = list(HAZEL_05_MAP)
        result = _bucket_generations([d - 1 for d in depths], 3)
        assert dict(zip(depths, result, strict=True)) == HAZEL_05_MAP

    def test_reproduces_the_identity_cases(self):
        # 10 of the 17 presets need no collapsing at all: their branchGeneration
        # range already fits under compoundMaxBranchGeneration.
        for name, mapping in IDENTITY_MAPS.items():
            depths = list(mapping)
            result = _bucket_generations([d - 1 for d in depths], 3)
            assert dict(zip(depths, result, strict=True)) == mapping, name

    def test_beech_04_is_a_documented_divergence(self):
        # Epic maps {1:1, 2:2, 3:2, 4:3}; the rule here gives {1:1, 2:2, 3:3, 4:3}.
        # Both are valid collapses -- this pins that we know we differ, and that
        # the range and cap still agree.
        depths = list(BEECH_04_MAP)
        result = _bucket_generations([d - 1 for d in depths], 3)
        ours = dict(zip(depths, result, strict=True))
        assert ours != BEECH_04_MAP
        assert max(ours.values()) == max(BEECH_04_MAP.values()) == 3
        assert ours[1] == BEECH_04_MAP[1] == 1

    def test_never_exceeds_the_cap(self):
        deep = list(range(40))
        for cap in (1, 2, 3, 5):
            result = _bucket_generations(deep, cap)
            assert max(result) <= cap
            assert min(result) == 1

    def test_is_monotone_non_decreasing(self):
        result = _bucket_generations(list(range(25)), 3)
        # Deliberately offset by one, so the two sides differ in length.
        assert all(a <= b for a, b in zip(result, result[1:], strict=False))

    def test_trunk_axis_keeps_a_bucket_to_itself(self):
        # Every shipped preset maps branchGeneration 1 to compound generation 1
        # alone, however deep the rest of the tree runs.
        result = _bucket_generations(list(range(30)), 3)
        assert result[0] == 1
        assert result[1] != 1


def _chain(depth):
    """A single unbranched chain of `depth` branches, root first."""
    parents = [0] + list(range(depth - 1))
    generations = list(range(depth))
    return parents, generations


class TestBuildCompoundHierarchy:
    """The three laws verified against the shipped presets."""

    def test_empty(self):
        result = build_compound_hierarchy([], [])
        assert result["compound_count"] == 0
        assert result["compound_generation"] == []
        assert result["compound_number"] == []
        assert result["compound_parent_number"] == []

    def test_single_root_branch(self):
        result = build_compound_hierarchy([0], [0])
        assert result["compound_generation"] == [1]
        assert result["compound_number"] == [0]
        # A root cluster points at itself, as it does in all 17 presets.
        assert result["compound_parent_number"] == [0]
        assert result["compound_count"] == 1

    def test_branches_sharing_a_compound_generation_share_a_cluster(self):
        # A 6-deep chain buckets to compound generations 1,2,2,3,3,3, so the
        # clusters are {0}, {1,2} and {3,4,5}.
        parents, generations = _chain(6)
        result = build_compound_hierarchy(parents, generations)
        assert result["compound_generation"] == [1, 2, 2, 3, 3, 3]
        assert result["compound_number"] == [0, 1, 1, 2, 2, 2]
        assert result["compound_count"] == 3

    def test_compound_generation_is_constant_within_a_cluster(self):
        parents, generations = _chain(9)
        result = build_compound_hierarchy(parents, generations)
        per_cluster = {}
        for cluster, generation in zip(
            result["compound_number"], result["compound_generation"]
        , strict=True):
            per_cluster.setdefault(cluster, set()).add(generation)
        assert all(len(g) == 1 for g in per_cluster.values())

    def test_a_cluster_generation_is_its_parent_cluster_generation_plus_one(self):
        parents, generations = _chain(9)
        result = build_compound_hierarchy(parents, generations)
        generation_of = dict(
            zip(result["compound_number"], result["compound_generation"], strict=True)
        )
        parent_of = dict(
            zip(
                result["compound_number"],
                result["compound_parent_number"],
                strict=True,
            )
        )
        for cluster, parent in parent_of.items():
            if parent == cluster:
                continue  # root cluster
            assert generation_of[cluster] == generation_of[parent] + 1

    def test_compound_parent_number_names_the_cluster_above(self):
        # Not merely "constant within a cluster" -- that is structural, since
        # compound_parent_number is built as a lookup keyed on the cluster id and
        # so cannot vary within one. The real requirement is that the value
        # identifies the cluster containing the parent of the branch through
        # which the cluster is entered.
        parents = [0, 0, 0, 1, 2]
        generations = [0, 1, 1, 2, 2]
        result = build_compound_hierarchy(parents, generations)
        numbers = result["compound_number"]
        parent_numbers = result["compound_parent_number"]
        for branch, parent in enumerate(parents):
            if parent == branch:
                continue
            if numbers[branch] != numbers[parent]:
                assert parent_numbers[branch] == numbers[parent]

    def test_a_root_cluster_is_the_only_one_pointing_at_itself(self):
        parents = [0, 0, 1, 2]
        generations = [0, 1, 2, 3]
        result = build_compound_hierarchy(parents, generations)
        self_referencing = {
            c
            for c, p in zip(
                result["compound_number"], result["compound_parent_number"], strict=True
            )
            if c == p
        }
        roots = {
            c
            for c, g in zip(
                result["compound_number"], result["compound_generation"], strict=True
            )
            if g == 1
        }
        assert self_referencing == roots

    def test_compound_number_is_zero_based_and_contiguous(self):
        parents = [0, 0, 0, 1, 2, 3, 4, 5]
        generations = [0, 1, 1, 2, 2, 3, 3, 4]
        result = build_compound_hierarchy(parents, generations)
        numbers = set(result["compound_number"])
        assert numbers == set(range(len(numbers)))
        assert result["compound_count"] == len(numbers)

    def test_multi_stem_roots_each_get_their_own_root_cluster(self):
        # Broadleaf_Hazel_01 has 15 root clusters, every one self-referencing.
        parents = [0, 1, 2]
        generations = [0, 0, 0]
        result = build_compound_hierarchy(parents, generations)
        assert result["compound_number"] == [0, 1, 2]
        assert result["compound_parent_number"] == [0, 1, 2]

    def test_collapses_deep_topology_below_the_cap(self):
        # The point of the compound layer: branchGeneration runs to 20 while
        # compoundBranchGeneration stays at 3.
        parents, generations = _chain(20)
        result = build_compound_hierarchy(parents, generations)
        assert max(generations) == 19
        assert result["max_compound_generation"] == DEFAULT_MAX_COMPOUND_GENERATION
        assert result["compound_count"] == DEFAULT_MAX_COMPOUND_GENERATION

    def test_is_deterministic(self):
        parents = [0, 0, 1, 1, 2, 3, 4, 0, 7]
        generations = [0, 1, 2, 2, 3, 3, 4, 1, 2]
        first = build_compound_hierarchy(parents, generations)
        second = build_compound_hierarchy(parents, generations)
        assert first == second

    def test_tolerates_out_of_range_and_negative_parents(self):
        # `_derive_parents_from_skeleton` returns -1 for roots and callers pad
        # `num_branches` beyond the poly_line count.
        result = build_compound_hierarchy([-1, 0, 99], [0, 1, 2])
        assert result["compound_count"] >= 1
        assert len(result["compound_number"]) == 3

    @pytest.mark.parametrize("cap", [1, 2, 3, 4])
    def test_respects_an_explicit_cap(self, cap):
        parents, generations = _chain(12)
        result = build_compound_hierarchy(parents, generations, cap)
        assert result["max_compound_generation"] <= cap


class TestCompoundLayerIsNotAnAliasOfTheBranchLayer:
    """XRFF-360's actual bug: the compound fields were copies."""

    def test_compound_generation_differs_from_branch_generation(self):
        parents, generations = _chain(8)
        result = build_compound_hierarchy(parents, generations)
        assert result["compound_generation"] != generations

    def test_compound_number_is_not_one_id_per_branch(self):
        parents, generations = _chain(8)
        result = build_compound_hierarchy(parents, generations)
        assert result["compound_count"] < len(generations)
        assert result["compound_number"] != list(range(len(generations)))

    def test_returned_lists_are_not_the_input_lists(self):
        # The old code assigned by reference, so mutating one attribute
        # silently mutated two others.
        parents, generations = _chain(6)
        result = build_compound_hierarchy(parents, generations)
        assert result["compound_generation"] is not generations
        assert result["compound_parent_number"] is not parents


class TestApplyCompoundGlobals:
    """The two globals count clusters, not branches.

    Without this, reinstating the exact XRFF-360 stub leaves the whole suite
    bit-identical: nothing else reads the emitted values.
    """

    def _pve(self, numbers, generations, branches=None):
        n = branches if branches is not None else len(numbers)
        return {
            "globalAttributes": {
                "compoundMaxBranchNumber": {"value": n},
                "compoundMaxBranchGeneration": {"value": 99},
                "maxBranchNumber": {"value": n},
            },
            "primitives": {
                "attributes": {
                    "compoundBranchNumber": {"values": numbers},
                    "compoundBranchGeneration": {"values": generations},
                }
            },
        }

    def _apply(self, pve):
        from growpy.io.unreal.pve_grove_mapper import _apply_compound_globals

        _apply_compound_globals(pve)
        return pve["globalAttributes"]

    def test_max_branch_number_becomes_the_cluster_count(self):
        # Beech_01 ships 88 clusters over 195 branches; the stub emitted 195.
        pve = self._pve([0, 0, 1, 1, 2], [1, 1, 2, 2, 3])
        assert self._apply(pve)["compoundMaxBranchNumber"]["value"] == 3

    def test_max_branch_generation_becomes_the_compound_range(self):
        # Not topological depth: every shipped preset holds this at 2-3 while
        # branchGeneration runs to 6.
        pve = self._pve([0, 1, 2], [1, 2, 3])
        assert self._apply(pve)["compoundMaxBranchGeneration"]["value"] == 3

    def test_leaves_unrelated_globals_alone(self):
        pve = self._pve([0, 1], [1, 2], branches=17)
        assert self._apply(pve)["maxBranchNumber"]["value"] == 17

    def test_is_a_no_op_when_the_primitives_carry_no_compound_layer(self):
        pve = {
            "globalAttributes": {"compoundMaxBranchNumber": {"value": 42}},
            "primitives": {"attributes": {}},
        }
        assert self._apply(pve)["compoundMaxBranchNumber"]["value"] == 42

    def test_tolerates_a_missing_primitives_section(self):
        pve = {"globalAttributes": {"compoundMaxBranchNumber": {"value": 42}}}
        from growpy.io.unreal.pve_grove_mapper import _apply_compound_globals

        _apply_compound_globals(pve)  # must not raise

    def test_cluster_count_is_distinct_ids_not_the_maximum_id(self):
        # Non-contiguous ids would overcount if max() were used instead.
        pve = self._pve([0, 0, 5, 5], [1, 1, 2, 2])
        assert self._apply(pve)["compoundMaxBranchNumber"]["value"] == 2


class TestMapperEmitsTheCompoundLayer:
    """The mapper's WIRING, not just the helper.

    Reinstating the exact XRFF-360 stub -- compoundBranchGeneration copied from
    branchGeneration and compoundBranchNumber set to range(num_branches) --
    passed the entire suite until this class existed, because every other test
    exercises `build_compound_hierarchy` directly.
    """

    def _primitives(self, depth=9):
        from types import SimpleNamespace

        from growpy.io.unreal.pve_grove_mapper import _map_primitives_from_skeleton
        from growpy.io.unreal.pve_schema import create_empty_pve_preset

        # An unbranched chain: branch i starts on the last point of branch i-1,
        # which is how _derive_parents_from_skeleton recognises a parent.
        poly_lines = [[2 * i, 2 * i + 1, 2 * i + 2] for i in range(depth)]
        points = [(0.0, 0.0, float(i)) for i in range(2 * depth + 2)]
        skeleton = SimpleNamespace(poly_lines=poly_lines, points=points)

        # A truthy model with no foliage: branchGeneration is gated on `model`
        # being truthy, and the foliage extractor reads these arrays.
        model = SimpleNamespace(
            faces=[],
            points=[],
            uvs=[],
            get_twig_locations=lambda: [],
            get_twig_directions=lambda: [],
            get_twig_orientations=lambda: [],
            face_attribute_branch_id=[],
            face_attribute_twig_long=[],
            face_attribute_twig_short=[],
            face_attribute_twig_upward=[],
            face_attribute_twig_dead=[],
        )

        template = create_empty_pve_preset()["primitives"]
        return _map_primitives_from_skeleton(
            skeleton, template, model, [], "european_beech", depth
        )

    def _values(self, primitives, name):
        entry = primitives["attributes"][name]
        return entry.get("values", entry.get("value"))

    def test_compound_generation_is_not_a_copy_of_branch_generation(self):
        primitives = self._primitives()
        branch = self._values(primitives, "branchGeneration")
        compound = self._values(primitives, "compoundBranchGeneration")
        assert compound != branch
        assert max(compound) <= 3 < max(branch) + 1

    def test_compound_number_is_a_cluster_id_not_one_per_branch(self):
        primitives = self._primitives()
        compound = self._values(primitives, "compoundBranchNumber")
        assert compound != list(range(len(compound)))
        assert len(set(compound)) < len(compound)

    def test_compound_parent_number_is_not_a_copy_of_branch_parent_number(self):
        primitives = self._primitives()
        assert self._values(primitives, "compoundBranchParentNumber") != self._values(
            primitives, "branchParentNumber"
        )

    def test_the_three_compound_arrays_are_not_the_branch_list_objects(self):
        # The original stub assigned by reference, so mutating one silently
        # mutated the others.
        primitives = self._primitives()
        for compound_name, branch_name in (
            ("compoundBranchGeneration", "branchGeneration"),
            ("compoundBranchParentNumber", "branchParentNumber"),
        ):
            assert self._values(primitives, compound_name) is not self._values(
                primitives, branch_name
            )

    def test_the_emitted_layer_obeys_the_reference_laws(self):
        primitives = self._primitives()
        numbers = self._values(primitives, "compoundBranchNumber")
        generations = self._values(primitives, "compoundBranchGeneration")
        parents = self._values(primitives, "compoundBranchParentNumber")

        per_cluster = {}
        for cluster, generation, parent in zip(
            numbers, generations, parents, strict=True
        ):
            per_cluster.setdefault(cluster, set()).add((generation, parent))
        assert all(len(v) == 1 for v in per_cluster.values())
        assert set(numbers) == set(range(len(set(numbers))))
