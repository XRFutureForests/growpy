from pathlib import Path
from growpy.io.usd.overview import generate_overview_markdown

result = generate_overview_markdown(
    forest_dir=Path("data/output/forest"),
    preset_dir=Path("data/assets/presets"),
    models_dir=Path("data/assets/growth_models"),
)
print("Written:", result)
