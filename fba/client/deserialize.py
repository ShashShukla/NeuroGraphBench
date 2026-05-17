"""Client-side response hydration.

Maps wire payloads from `fba.server.schemas` to native Python objects.
"""

from typing import Any

import navis
import numpy as np
import pandas as pd


def meshFromPayload(payload: dict[str, Any]) -> navis.Volume:
    """Hydrate a MeshPayload dict into a navis.Volume."""
    vertices = np.asarray(payload["vertices"], dtype=float)
    faces = np.asarray(payload["faces"], dtype=int)
    return navis.Volume(vertices=vertices, faces=faces, name=payload.get("name"))


def meshListFromPayload(payloads: list[dict[str, Any]]) -> list[navis.Volume]:
    """Hydrate a list of MeshPayload dicts into a list of navis.Volume."""
    return [meshFromPayload(p) for p in payloads]


def tableFromPayload(payload: dict[str, Any]) -> pd.DataFrame:
    """Hydrate a TablePayload dict into a pandas DataFrame, preserving column order."""
    data = payload["data"]
    columns = payload.get("columns") or list(data.keys())
    return pd.DataFrame(data, columns=columns)
