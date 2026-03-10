"""Wrapper to run create_growth_models with correct module path."""
import sys
from pathlib import Path

# Add Grove modules to path BEFORE importing growpy
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path / "the_grove_23" / "modules"))
sys.path.insert(0, str(src_path))

# Now import and run
from growpy.cli.create_growth_models import main

sys.exit(main())
