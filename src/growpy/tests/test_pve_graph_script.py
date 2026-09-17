"""Tests for growpy.io.unreal.pve_graph_script.

Regression coverage for XRFF-330. The graph builder ran green through a
whole admission-audit round while wiring nothing: it could not reach the
inner ProceduralVegetationGraph on UE 5.7, logged the failure, and then
printed "Done." and returned normally -- which Remote Execution reports as
success. These tests pin down the three things that made that possible:

* the inner graph is looked up as a named subobject, not as a property
  (``Graph`` is a bare UPROPERTY, so reflection denies the read) nor via
  ``GetGraph`` (plain C++, never a UFUNCTION);
* the per-variant chain names node classes that actually exist in the
  plugin -- ``PVCurveSettings`` never did, so the first node of every
  chain was silently skipped by the ``hasattr`` guard;
* a wiring failure raises instead of returning.

The script only ever runs inside UE, so it is checked by parsing and
inspecting the generated source rather than by executing it.
"""

import ast
from pathlib import Path

import pytest

from growpy.io.unreal.pve_graph_script import generate_pve_graph_script


@pytest.fixture
def script_source(tmp_path):
    path = generate_pve_graph_script(
        tmp_path,
        Path("data/output/forest"),
        import_base="/Game/Assets/TheGrove_r3",
        species_twig_map={"common_ash": "common_ash_twigs_combined_skeletal"},
    )
    assert path == tmp_path / "growpy_pve_graph_builder.py"
    return path.read_text(encoding="utf-8")


def _function(source, name):
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name}() not found in generated script")


class TestGeneratedScript:
    def test_is_valid_python(self, script_source):
        """A syntax error here would only surface as an opaque remote-exec
        failure, since the script is never imported on this side."""
        ast.parse(script_source)

    def test_bakes_caller_arguments(self, script_source):
        assert "/Game/Assets/TheGrove_r3" in script_source
        assert "common_ash_twigs_combined_skeletal" in script_source

    def test_calls_main(self, script_source):
        """Without the trailing call the script defines everything, does
        nothing, and still reports success to Remote Execution."""
        calls = [
            node
            for node in ast.parse(script_source).body
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "id", None) == "main"
        ]
        assert len(calls) == 1


class TestInnerGraphAccess:
    """The UE 5.7 replacement for the unreachable Graph accessor."""

    def test_looks_the_graph_up_as_a_named_subobject(self, script_source):
        assert 'INNER_GRAPH_NAME = "ProceduralVegetationGraph"' in script_source
        assert "finder(graph_asset, INNER_GRAPH_NAME)" in script_source
        assert "unreal.find_object" in script_source

    def test_does_not_call_the_removed_getgraph_method(self, script_source):
        """GetGraph() is not a UFUNCTION in any version of the plugin, so
        call_method could only ever produce a misleading warning."""
        assert 'call_method("GetGraph")' not in script_source


class TestNodeChain:
    def test_uses_the_node_class_the_plugin_actually_ships(self, script_source):
        assert '"PVCarveSettings"' in script_source
        assert "PVCurveSettings" not in script_source

    def test_reads_every_edge_back(self, script_source):
        """AddEdge returns the To node whether or not the edge was made."""
        assert "_add_verified_edge" in script_source
        assert "pin.is_connected()" in script_source

    def test_checks_the_variant_pin_exists_before_wiring(self, script_source):
        assert '_pin_named(loader_node, "output_pins", vname)' in script_source


class TestFailuresAreLoud:
    def test_main_raises(self, script_source):
        raises = [
            n
            for n in ast.walk(_function(script_source, "main"))
            if isinstance(n, ast.Raise)
        ]
        assert raises, "main() must raise so Remote Execution reports failure"

    def test_done_is_printed_only_after_the_failure_check(self, script_source):
        main = _function(script_source, "main")
        done = script_source.splitlines().index('    unreal.log("[PVE-G] Done.")')
        last_raise = max(n.lineno for n in ast.walk(main) if isinstance(n, ast.Raise))
        assert done + 1 > last_raise

    def test_graph_builder_reports_a_boolean(self, script_source):
        returns = {
            ast.unparse(n.value)
            for n in ast.walk(_function(script_source, "_create_pve_graph"))
            if isinstance(n, ast.Return) and n.value is not None
        }
        assert returns <= {"True", "False", "ok"}, returns
