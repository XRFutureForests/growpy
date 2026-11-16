"""growpy-structure-regrow --table: config table values in a seed's copied config."""

import pytest

from growpy.tools.structure_regrow import set_table_key

TEXT = (
    "[surround]\nradii = [7, 10]\n\n[surround.freeze_height_per_species]\n# cleared\n"
    '\n[export]\nmode = "unreal"\n'
)


def test_sets_a_key_inside_an_existing_table_only():
    table = "surround.freeze_height_per_species"
    out = set_table_key(TEXT, table, "norway_spruce", "20")
    _, rest = out.split(f"[{table}]\n", 1)
    assert rest.startswith("norway_spruce = 20\n") and "[export]" in rest
    again = set_table_key(out, table, "norway_spruce", "25")
    assert again.count("norway_spruce") == 1 and "norway_spruce = 25" in again


def test_creates_a_missing_per_species_table_the_loader_reads():
    table = "surround.freeze_height_per_species_radius.norway_spruce"
    out = set_table_key(TEXT, table, "r07", "20")
    assert out.endswith(f"[{table}]\nr07 = 20\n")


def test_refuses_an_unknown_table():
    with pytest.raises(SystemExit, match="refusing to guess"):
        set_table_key(TEXT, "surround.no_such_table", "x", "1")
