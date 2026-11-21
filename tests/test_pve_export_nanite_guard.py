"""The PVE export must not report success for a mesh saved without Nanite."""

import inspect

from growpy.io.unreal.pve_graph_plan import plan_pve_graphs
from growpy.tools.pve_export import _NANITE_BUILD_ERROR


def test_guard_matches_engine_errors():
    for line in (
        "LogStaticMesh: Error: Merged Nanite assembly has too many "
        "transforms (68809). Max is 65535.",
        "LogSkeletalMesh: Error: Failed to build Nanite for skeletal mesh.",
    ):
        assert _NANITE_BUILD_ERROR.search(line)
    assert not _NANITE_BUILD_ERROR.search("LogStaticMesh: NaniteBuild [6.58s]")


def test_default_instance_cap_stays_under_the_hierarchy_limit():
    # 50,970 instances already overflowed the 16-bit hierarchy node index.
    params = inspect.signature(plan_pve_graphs).parameters
    assert params["max_assembly_instances"].default < 50_970
