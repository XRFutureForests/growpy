"""
Forest growth simulation module.

This module provides atomic functions for forest simulation including:
- CSV data loading and validation
- Height curve generation and age prediction
- Grove creation and tree growth simulation
- Data processing utilities

For high-level forest creation workflows, see generate_forest.py.
"""

import logging
import pickle
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

"""
Forest growth simulation module (refactored).
This module now only imports atomic modules for simulation workflows.
"""

# Core utilities
from .core.tree_utils import calculate_tree_height

# Data loading and validation
from .data.loader import load_and_validate_csv
from .data.validation import ValidationError

# Grove creation and simulation
from .grove.grove_creation import create_groves_from_data
from .grove.simulation import simulate_forest_growth

# File I/O
from .io.csv_io import save_dataframe_to_csv, save_height_curves_to_csv

# Height curve generation and prediction models
from .modeling.height_curves import generate_height_curves
from .modeling.models import (
    add_predicted_cycles_to_data,
    create_cycle_prediction_models,
    predict_cycles_from_height,
)

DEFAULT_OUTPUT_PATH = DEFAULT_DATA_PATH / "output"
