# utils/file_handler.py

import pandas as pd


def load_dataset(path: str) -> pd.DataFrame:
    """Loads a CSV or Excel file into a DataFrame based on its extension."""

    extension = path.rsplit(".", 1)[-1].lower()

    if extension == "csv":
        return pd.read_csv(path)

    if extension in ("xlsx", "xls"):
        return pd.read_excel(path)

    raise ValueError(f"Unsupported file format: .{extension}")
