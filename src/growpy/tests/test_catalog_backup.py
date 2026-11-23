"""growpy-catalog-backup finds the catalog root the project actually uses."""

import pytest

from growpy.config.ue_layout import LEGACY_TREES_ROOT, TREES_ROOT, content_relpath
from growpy.tools.catalog_backup import sources


def _catalog_subs(project):
    return [sub for _, sub, _ in sources(project) if sub.startswith("XRFF_Twin/")]


def test_sandbox_layout_uses_the_legacy_root(tmp_path):
    (tmp_path / content_relpath(LEGACY_TREES_ROOT)).mkdir(parents=True)
    expected = f"XRFF_Twin/{content_relpath(LEGACY_TREES_ROOT)}"
    assert _catalog_subs(tmp_path) == [expected]


def test_both_roots_are_backed_up(tmp_path):
    for root in (TREES_ROOT, LEGACY_TREES_ROOT):
        (tmp_path / content_relpath(root)).mkdir(parents=True)
    assert len(_catalog_subs(tmp_path)) == 2


def test_no_catalog_root_is_an_error(tmp_path):
    with pytest.raises(SystemExit, match="no tree catalog"):
        sources(tmp_path)
