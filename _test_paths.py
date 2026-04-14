from growpy.config.paths import _get_lookup_table, _get_lookup_table_path
from growpy.utils.yield_tables import load_lookup_table
from growpy.cli.prepare_assets import load_species_csv
from growpy.cli.create_growth_models import _resolve_species_from_csv
from growpy.cli.convert_twigs import main as convert_main
import growpy.utils.analysis  # noqa: F401
from growpy.pipelines.dataset_csv_planner import _get_dataset_species

print("lookup path:", _get_lookup_table_path())
print("lookup rows:", len(_get_lookup_table()))
print("yield lookup keys (3):", list(load_lookup_table().keys())[:3])
print("dataset species:", list(_get_dataset_species()["Common Name"]))
print("All imports OK")
