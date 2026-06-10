"""Tests for growpy.io.pve_growth_defaults module."""


from growpy.io.unreal.pve_growth_defaults import (
    get_default_growth_params,
    get_hazel_growth_defaults,
    merge_growth_params,
)


class TestGetHazelGrowthDefaults:
    """Tests for the Hazel reference growth parameters."""

    def test_returns_dict(self):
        result = get_hazel_growth_defaults()
        assert isinstance(result, dict)

    def test_has_required_phyllotaxy_leaf(self):
        result = get_hazel_growth_defaults()
        assert "phyllotaxyLeaf" in result

    def test_phyllotaxy_leaf_structure(self):
        entry = get_hazel_growth_defaults()["phyllotaxyLeaf"]
        assert entry["isArray"] is True
        assert entry["type"] == "float"
        assert isinstance(entry["value"], list)
        assert len(entry["value"]) == 14

    def test_has_growth_curves(self):
        result = get_hazel_growth_defaults()
        expected_keys = [
            "phototropism",
            "phototropismChild",
            "phyllotaxy",
            "phyllotaxyChild",
            "axialElongation",
            "trunkGrowth",
            "leafGrowth",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_plant_profiles_have_101_values(self):
        result = get_hazel_growth_defaults()
        for i in range(1, 6):
            key = f"plantProfile_{i}"
            assert key in result
            assert len(result[key]["value"]) == 100

    def test_all_values_are_float_arrays(self):
        result = get_hazel_growth_defaults()
        for key, entry in result.items():
            assert entry["type"] == "float", f"{key} is not float type"
            assert isinstance(entry["value"], list), f"{key} value is not a list"


class TestGetDefaultGrowthParams:
    """Tests for get_default_growth_params with hazel toggle."""

    def test_hazel_defaults_true(self):
        result = get_default_growth_params(use_hazel_defaults=True)
        assert "phototropism" in result
        assert "trunkGrowth" in result

    def test_hazel_defaults_false(self):
        result = get_default_growth_params(use_hazel_defaults=False)
        assert "phyllotaxyLeaf" in result
        assert "phototropism" not in result

    def test_minimal_phyllotaxy_leaf_has_14_values(self):
        result = get_default_growth_params(use_hazel_defaults=False)
        assert len(result["phyllotaxyLeaf"]["value"]) == 14


class TestMergeGrowthParams:
    """Tests for merge_growth_params."""

    def test_no_overrides(self):
        defaults = get_hazel_growth_defaults()
        result = merge_growth_params(defaults)
        assert result == defaults

    def test_none_overrides(self):
        defaults = {"a": {"isArray": True, "type": "float", "value": [1.0]}}
        result = merge_growth_params(defaults, None)
        assert result == defaults

    def test_override_existing_value(self):
        defaults = {"a": {"isArray": True, "type": "float", "value": [1.0, 2.0]}}
        overrides = {"a": {"value": [3.0, 4.0]}}
        result = merge_growth_params(defaults, overrides)
        assert result["a"]["value"] == [3.0, 4.0]
        assert result["a"]["isArray"] is True  # structure preserved

    def test_add_new_key(self):
        defaults = {"a": {"type": "float", "value": [1.0]}}
        overrides = {"b": {"type": "float", "value": [2.0]}}
        result = merge_growth_params(defaults, overrides)
        assert "b" in result
        assert result["b"]["value"] == [2.0]

    def test_does_not_mutate_defaults(self):
        defaults = {"a": {"isArray": True, "type": "float", "value": [1.0]}}
        original_value = defaults["a"]["value"][:]
        merge_growth_params(defaults, {"a": {"value": [9.0]}})
        assert defaults["a"]["value"] == original_value

    def test_override_non_dict_value(self):
        defaults = {"a": {"type": "float", "value": [1.0]}}
        overrides = {"a": "replaced"}
        result = merge_growth_params(defaults, overrides)
        assert result["a"] == "replaced"
