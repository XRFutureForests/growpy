"""
Forest data validation utilities.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    pass


def validate_forest_data(data: pd.DataFrame) -> None:
    coordinate_cols = ["x", "y", "z"]
    for col in coordinate_cols:
        if col in data.columns:
            if not data[col].apply(lambda x: np.isfinite(x)).all():
                raise ValidationError(
                    f"Column '{col}' contains invalid values (inf/nan)"
                )
    if "height" in data.columns:
        if (data["height"] <= 0).any():
            raise ValidationError("Tree heights must be positive")
        if (data["height"] > 200).any():
            logger.warning("Some trees have heights > 200m, which may be unrealistic")
    if len(coordinate_cols) == 3 and all(
        col in data.columns for col in coordinate_cols
    ):
        duplicates = data.duplicated(subset=coordinate_cols, keep=False)
        if duplicates.any():
            num_duplicates = duplicates.sum()
            logger.warning(f"Found {num_duplicates} trees with duplicate positions")
