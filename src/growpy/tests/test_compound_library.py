"""Tests for the shared part library and the hybrid assembly (XRFF-389/392).

Two halves of the same change:

* a compound part library shared between trees by UE package path, and the
  nearest-medoid lookup that lets a tree be assigned against one it did not
  bake itself;
* the residual 1:1 twigs, which a compound assembly has to place because a
  compound part only renders the foliage of the subtree it replaced.
"""

import pytest

from growpy.io.usd.extref_assembly import library_package_path
from growpy.tools.harvest_compound_parts import (
    DESCRIPTOR_TERMS,
    BranchRecord,
    apply_normalisation,
    assign_against_library,
    descriptor_distance,
    descriptor_vectors,
    library_asset_paths,
    normalise_descriptors,
    precompute_subtrees,
    residual_twig_asset,
    residual_twig_placements,
)


def _record(index, parent, base_radius, base_pos=(0.0, 0.0, 0.0), length=0.1):
    return BranchRecord(
        index=index,
        parent=parent,
        depth=0,
        base_radius=base_radius,
        tip_radius=base_radius * 0.5,
        length=length,
        base_pos=base_pos,
        base_dir=(0.0, 0.0, 1.0),
        node_count=2,
    )


def _link(records):
    for record in records:
        if record.parent >= 0:
            records[record.parent].children.append(record.index)
    return records


def _fan(child_count, child_length=0.1):
    records = [_record(0, -1, 0.10)]
    for i in range(child_count):
        records.append(
            _record(i + 1, 0, 0.004, base_pos=(0.2 * i, 0.0, 1.0), length=child_length)
        )
    return _link(records)


class TestDescriptorNormalisation:
    def test_terms_match_the_descriptor_width(self):
        records = _fan(4)
        metrics = precompute_subtrees(records)
        _, vectors = descriptor_vectors(records, metrics, [1, 2, 3, 4])
        assert len(vectors[0]) == len(DESCRIPTOR_TERMS)

    def test_standardises_to_zero_mean(self):
        vectors = [[1.0, 10.0], [3.0, 20.0], [5.0, 30.0]]
        normed, means, devs = normalise_descriptors(vectors)
        assert means == pytest.approx([3.0, 20.0])
        assert all(d > 0 for d in devs)
        assert sum(v[0] for v in normed) == pytest.approx(0.0)

    def test_a_constant_term_does_not_divide_by_zero(self):
        # `devs.append(math.sqrt(var) or 1.0)` is the guard, and a cut set where
        # every candidate has the same up-alignment is ordinary, not exotic.
        normed, _, devs = normalise_descriptors([[1.0, 7.0], [2.0, 7.0]])
        assert devs[1] == 1.0
        assert all(v[1] == 0.0 for v in normed)

    def test_applying_a_stored_normalisation_reproduces_it(self):
        vectors = [[1.0, 10.0], [3.0, 20.0], [5.0, 30.0]]
        normed, means, devs = normalise_descriptors(vectors)
        assert apply_normalisation(vectors, means, devs) == normed


def _library(prototypes, means=(0.0, 0.0), devs=(1.0, 1.0)):
    return {
        "schema": 1,
        "species": "test_species",
        "package_root": "/Game/CompoundLib/test_species",
        "descriptor": {"means": list(means), "devs": list(devs)},
        "prototypes": prototypes,
    }


class TestAssignAgainstLibrary:
    """The half `cluster_prototypes` does not do: assign against someone else's.

    `cluster_prototypes` derives medoids and assignment together from one tree.
    Sharing a library means a tree has to be assigned against prototypes baked
    from a DIFFERENT tree, using that tree's normalisation.
    """

    def _tree(self):
        records = _fan(4)
        return records, precompute_subtrees(records), [1, 2, 3, 4]

    def _stored(self, records, metrics, cut, twig_totals, twigs_per_prototype):
        vectors = descriptor_vectors(records, metrics, cut, twig_totals)[1]
        normed, means, devs = normalise_descriptors(vectors)
        prototypes = [
            {
                "id": i,
                "name": f"p{i:02d}",
                "file": f"p{i:02d}_skeletal.usda",
                "package_path": f"/Game/CompoundLib/test_species/lib/p{i:02d}",
                "twigs": twigs,
                "descriptor": normed[i],
            }
            for i, twigs in enumerate(twigs_per_prototype)
        ]
        return _library(prototypes, means, devs)

    def test_every_cut_point_gets_a_prototype(self):
        records, metrics, cut = self._tree()
        twig_totals = [0] * len(records)
        library = self._stored(records, metrics, cut, twig_totals, [1, 1, 1, 1])
        assignment = assign_against_library(
            records, metrics, cut, twig_totals, library
        )
        assert len(assignment) == len(cut)
        assert all(0 <= a < 4 for a in assignment)

    def test_a_candidate_lands_on_the_prototype_baked_from_itself(self):
        records, metrics, cut = self._tree()
        # Distinct shapes so each candidate has its own nearest medoid.
        for i, branch in enumerate(cut):
            records[branch].length = 0.1 * (i + 1)
        metrics = precompute_subtrees(records)
        twig_totals = [0] * len(records)
        library = self._stored(records, metrics, cut, twig_totals, [1, 1, 1, 1])
        assignment = assign_against_library(
            records, metrics, cut, twig_totals, library
        )
        assert assignment == [0, 1, 2, 3]

    def test_normalises_with_the_librarys_statistics_not_its_own(self):
        # The point of storing means/devs. Given a shifted normalisation the
        # assignment must change; recomputing from the tree would hide that.
        records, metrics, cut = self._tree()
        for i, branch in enumerate(cut):
            records[branch].length = 0.1 * (i + 1)
        metrics = precompute_subtrees(records)
        twig_totals = [0] * len(records)
        library = self._stored(records, metrics, cut, twig_totals, [1, 1, 1, 1])

        honest = assign_against_library(records, metrics, cut, twig_totals, library)
        library["descriptor"]["means"] = [
            m + 50.0 for m in library["descriptor"]["means"]
        ]
        shifted = assign_against_library(records, metrics, cut, twig_totals, library)
        assert shifted != honest

    def test_a_leafy_subtree_never_takes_a_twigless_prototype(self):
        # XRFF-387, restated against the library: a part with no welded twigs
        # renders nothing, whatever the descriptor distance promised.
        records, metrics, cut = self._tree()
        for i, branch in enumerate(cut):
            records[branch].length = 0.1 * (i + 1)
        metrics = precompute_subtrees(records)
        twig_totals = [0] * len(records)
        for branch in cut:
            twig_totals[branch] = 5
        library = self._stored(records, metrics, cut, twig_totals, [0, 0, 0, 7])
        assignment = assign_against_library(
            records, metrics, cut, twig_totals, library
        )
        assert set(assignment) == {3}

    def test_a_fully_bare_library_is_left_alone(self):
        # With no leafy prototype to move to, the guard must not fire and must
        # not crash -- the nearest match is still the best available answer.
        records, metrics, cut = self._tree()
        twig_totals = [3] * len(records)
        library = self._stored(records, metrics, cut, twig_totals, [0, 0, 0, 0])
        assignment = assign_against_library(
            records, metrics, cut, twig_totals, library
        )
        assert len(assignment) == len(cut)


class TestLibraryPackagePaths:
    def test_matches_the_layout_ue_imports_a_library_stage_into(self):
        # Measured, not guessed: importing silver_fir_library.usda into
        # /Game/CompoundLib2/silver_fir put the parts under
        # <stage stem>/SkeletalMeshes/ with an SK_ prefix, even with
        # prim_path_folder_structure = False.
        assert library_package_path(
            "/Game/CompoundLib2/silver_fir", "silver_fir_library", "silver_fir_p00"
        ) == (
            "/Game/CompoundLib2/silver_fir/silver_fir_library/SkeletalMeshes/"
            "SK_silver_fir_p00.SK_silver_fir_p00"
        )

    def test_a_trailing_slash_on_the_destination_is_tolerated(self):
        with_slash = library_package_path("/Game/Lib/", "stage", "part")
        without = library_package_path("/Game/Lib", "stage", "part")
        assert with_slash == without

    def test_asset_paths_cover_the_parts_and_every_residual_twig(self):
        library = _library(
            [{"file": "p00_skeletal.usda", "package_path": "/Game/Lib/p00"}]
        )
        # A twig ladder puts a different variant on each of Grove's types, and
        # every one of them needs its own package path or the rewrite silently
        # drops that type's whole share of the crown.
        library["residual_twigs"] = [
            {
                "name": "fir_foliage_a",
                "file": "fir_foliage_a_skeletal.usda",
                "package_path": "/Game/Lib/fir_foliage_a",
            },
            {
                "name": "fir_foliage_c",
                "file": "fir_foliage_c_skeletal.usda",
                "package_path": "/Game/Lib/fir_foliage_c",
            },
        ]
        assert library_asset_paths(library) == {
            "p00_skeletal.usda": "/Game/Lib/p00",
            "fir_foliage_a_skeletal.usda": "/Game/Lib/fir_foliage_a",
            "fir_foliage_c_skeletal.usda": "/Game/Lib/fir_foliage_c",
        }

    def test_asset_paths_survive_a_library_with_no_residual_twig(self):
        library = _library(
            [{"file": "p00_skeletal.usda", "package_path": "/Game/Lib/p00"}]
        )
        assert library_asset_paths(library) == {"p00_skeletal.usda": "/Game/Lib/p00"}


class TestResidualTwigAsset:
    def test_a_static_assembly_keeps_the_static_twig(self, tmp_path):
        static = tmp_path / "fir_foliage_static.usda"
        static.write_text("#usda 1.0\n")
        assert residual_twig_asset(static, skeletal=False) == static

    def test_a_skeletal_assembly_resolves_the_skeletal_sibling(self, tmp_path):
        static = tmp_path / "fir_foliage_static.usda"
        static.write_text("#usda 1.0\n")
        skeletal = tmp_path / "fir_foliage_skeletal.usda"
        skeletal.write_text("#usda 1.0\n")
        assert residual_twig_asset(static, skeletal=True) == skeletal

    def test_a_missing_skeletal_sibling_is_fatal(self, tmp_path):
        # Handed a static prototype, UE logs "Failed to find Skeletal Mesh
        # asset" and silently builds no assembly at all (F2/XRFF-366), so this
        # must fail here rather than there.
        static = tmp_path / "fir_foliage_static.usda"
        static.write_text("#usda 1.0\n")
        with pytest.raises(SystemExit):
            residual_twig_asset(static, skeletal=True)


def _grove_id(walker_index):
    """`face_attribute_branch_id` for a branch record.

    Grove's face attribute is `walker_index + 1`, and the whole point of
    `subtree_branch_ids` is that the two id spaces are not the same one.
    """
    return walker_index + 1


class _FakeModel:
    """The attribute surface `extract_twig_placements_from_model` reads.

    Twig faces are given in face order, and Grove's living-twig arrays are
    indexed by position in that order -- the coupling the real model has.
    `branch_of_face` carries Grove face-attribute ids, not walker indices.
    """

    def __init__(self, twig_faces, branch_of_face, bone_of_point=None):
        # twig_faces: list of (type, branch id); one quad per entry, plus one
        # plain woody face at the end so the mesh is not all markers.
        self.faces = [
            [4 * i, 4 * i + 1, 4 * i + 2, 4 * i + 3]
            for i in range(len(twig_faces) + 1)
        ]
        self.points = [(0.0, 0.0, 0.0)] * (4 * len(self.faces))
        self.face_attribute_branch_id = branch_of_face
        for name in ("twig_long", "twig_short", "twig_upward", "twig_dead"):
            setattr(
                self,
                f"face_attribute_{name}",
                [1 if t == name else 0 for t, _ in twig_faces] + [0],
            )
        count = len(twig_faces)
        self.get_twig_locations = lambda: [
            float(i) for i in range(count) for _ in range(3)
        ]
        self.get_twig_directions = lambda: [0.0, 0.0, 1.0] * count
        self.get_twig_orientations = lambda: [1.0, 0.0, 0.0, 0.0] * count
        if bone_of_point is not None:
            self.point_attribute_bone_id = bone_of_point


class TestResidualTwigPlacements:
    """The twigs a compound assembly used to render nowhere (XRFF-392).

    A part renders the foliage of the subtree it replaced, so a twig on a
    branch that stayed in the base mesh is in no part -- and the base mesh drops
    every twig marker face. Measured on an 18-cycle silver_fir: 58 of 3,204
    living twigs, all on the trunk and the leader, which is the bare apex.
    """

    def _tree(self):
        # 0 = trunk (never harvestable), 1 and 2 = thin children.
        records = _fan(2)
        return records

    def test_twigs_inside_a_harvested_subtree_are_not_placed_again(self):
        records = self._tree()
        model = _FakeModel(
            twig_faces=[("twig_long", _grove_id(1)), ("twig_long", _grove_id(2))],
            branch_of_face=[_grove_id(1), _grove_id(2), _grove_id(0)],
        )
        residual = residual_twig_placements(model, records, cut=[1, 2])
        assert residual == {}

    def test_a_twig_on_a_surviving_branch_is_placed(self):
        records = self._tree()
        model = _FakeModel(
            twig_faces=[("twig_long", _grove_id(1)), ("twig_long", _grove_id(0))],
            branch_of_face=[_grove_id(1), _grove_id(0), _grove_id(0)],
        )
        residual = residual_twig_placements(model, records, cut=[1, 2])
        assert list(residual) == ["twig_long"]
        assert len(residual["twig_long"]) == 1
        # The SECOND twig face, so Grove's second location slot.
        assert residual["twig_long"][0].position == (1.0, 1.0, 1.0)

    def test_selection_uses_grove_ids_not_walker_indices(self):
        # `harvested_branch_ids` speaks `walker_index + 1`. Read as walker
        # indices, the harvested set {2, 3} here would exclude the twig on
        # record 2 (Grove id 3) and admit the one on record 1 -- both wrong,
        # and both entirely plausible-looking.
        records = self._tree()
        model = _FakeModel(
            twig_faces=[("twig_long", _grove_id(0)), ("twig_long", _grove_id(2))],
            branch_of_face=[_grove_id(0), _grove_id(2), _grove_id(0)],
        )
        residual = residual_twig_placements(model, records, cut=[2])
        # Record 0 survives, record 2 is harvested: exactly one twig left.
        assert len(residual["twig_long"]) == 1
        assert residual["twig_long"][0].position == (0.0, 0.0, 0.0)

    def test_the_trunk_apex_twig_is_recovered(self):
        # `find_cut_set_adaptive` requires `rec.parent >= 0` and a Grove trunk
        # is ONE branch record, so an upward twig on it can never be harvested.
        records = self._tree()
        model = _FakeModel(
            twig_faces=[("twig_upward", _grove_id(0)), ("twig_long", _grove_id(1))],
            branch_of_face=[_grove_id(0), _grove_id(1), _grove_id(0)],
        )
        residual = residual_twig_placements(model, records, cut=[1, 2])
        assert list(residual) == ["twig_upward"]

    def test_every_residual_twig_names_its_prototype_explicitly(self):
        # None means "any", and `assembly_export` then draws at random -- right
        # for a uniform 1:1 twig set, wrong here where the compound parts share
        # the same instancer (XRFF-365).
        records = self._tree()
        model = _FakeModel(
            twig_faces=[("twig_long", _grove_id(0)), ("twig_short", _grove_id(0))],
            branch_of_face=[_grove_id(0), _grove_id(0), _grove_id(0)],
        )
        residual = residual_twig_placements(model, records, cut=[1, 2])
        placed = [p for items in residual.values() for p in items]
        assert placed and all(p.prototype == 0 for p in placed)

    def test_bone_ids_are_remapped_through_the_base_meshs_bone_map(self):
        # `build_tree_mesh` renumbers the bones the base mesh keeps, so a raw
        # Grove bone id is not an index into the authored joint list (F12).
        records = self._tree()
        model = _FakeModel(
            twig_faces=[("twig_long", _grove_id(0))],
            branch_of_face=[_grove_id(0), _grove_id(0)],
            bone_of_point=[7] * 8,
        )
        residual = residual_twig_placements(
            model, records, cut=[1, 2], bone_map={7: 2}
        )
        assert residual["twig_long"][0].bone_id == 2

    def test_a_bone_the_base_mesh_dropped_becomes_none(self):
        # `create_assembly` then falls back to the skeleton's own root joint.
        # An unresolvable token would discard the WHOLE instancer (F11).
        records = self._tree()
        model = _FakeModel(
            twig_faces=[("twig_long", _grove_id(0))],
            branch_of_face=[_grove_id(0), _grove_id(0)],
            bone_of_point=[7] * 8,
        )
        residual = residual_twig_placements(
            model, records, cut=[1, 2], bone_map={3: 0}
        )
        assert residual["twig_long"][0].bone_id is None

    def test_dead_twigs_are_left_out(self):
        # There is no dead-twig asset to place them with; the 1:1 path skips
        # them too.
        records = self._tree()
        model = _FakeModel(
            twig_faces=[("twig_dead", _grove_id(0))],
            branch_of_face=[_grove_id(0), _grove_id(0)],
        )
        assert residual_twig_placements(model, records, cut=[1, 2]) == {}


class TestDescriptorDistance:
    def test_is_symmetric_and_zero_on_itself(self):
        a = [1.0, -2.0, 0.5]
        assert descriptor_distance(a, a) == 0.0
        b = [0.0, 1.0, 1.0]
        assert descriptor_distance(a, b) == descriptor_distance(b, a)
