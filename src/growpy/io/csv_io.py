"""
File I/O operations for forest data.
"""

from pathlib import Path

import pandas as pd


def save_dataframe_to_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False)


def save_height_curves_to_csv(height_curves: pd.DataFrame, path: Path) -> None:
    height_curves.to_csv(path)
