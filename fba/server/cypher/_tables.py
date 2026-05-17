"""Shared helpers for serializing pandas DataFrames to TablePayload dicts.

The server uses pandas internally for groupby/pivot logic (lifted from
FlyBrainAtlas/query.py) but emits primitive JSON over the wire. This module
keeps that conversion in one place.
"""

from typing import Any

import pandas as pd


def dataFrameToPayload(df: pd.DataFrame, include_index: bool = False) -> dict[str, Any]:
    """Convert a DataFrame to a TablePayload-shaped dict.

    If `include_index` is True, the DataFrame's index is reset and emitted as
    the first column (used for matrix-layout responses where the row labels
    are part of the data).
    """
    if include_index:
        df = df.reset_index()
    columns = [str(c) for c in df.columns]
    data = {str(col): df[col].tolist() for col in df.columns}
    return {"columns": columns, "data": data}


def payloadToDataFrame(payload: dict[str, Any]) -> pd.DataFrame:
    """Inverse for tests and internal pipelines."""
    return pd.DataFrame(payload["data"], columns=payload.get("columns"))
