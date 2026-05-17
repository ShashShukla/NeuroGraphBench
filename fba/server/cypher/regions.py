"""Region-level (arbitrary-volume) queries.

Implements the dispatch logic from `FlyBrainAtlas/query.getRegionSynapseTable`:

- neuropil only           → return the cached neuropil synapse table.
- neuropil + volume       → fetch the neuropil table, filter rows by mesh.
- volume only             → find overlapping neuropils, fetch + filter each,
                            concatenate, de-duplicate.
- neither                 → return None (router maps to HTTP 400).

`navis.in_volume` is used for the point-in-mesh tests. This is the canonical
server-side use of navis (see `ARCHITECTURE.md` dependency rules).
"""

import navis
import numpy as np

from . import neuropils as neuropilCypher
from . import synapses as synapseCypher


def _payloadToVolume(volumePayload: dict) -> navis.Volume:
    return navis.Volume(
        vertices=np.asarray(volumePayload["vertices"], dtype=float),
        faces=np.asarray(volumePayload["faces"], dtype=int),
        name=volumePayload.get("name"),
    )


def _filterTablePayloadByVolume(payload: dict, volumePayload: dict) -> dict:
    """Filter a TablePayload's rows by an arbitrary mesh.

    Looks up `x/y/z` columns; rows whose coordinates lie inside the mesh are
    retained. Mirrors `utils.filterLocationsTableByVolume`.
    """
    data = payload["data"]
    columns = payload["columns"]
    xs = np.asarray(data["x"])
    ys = np.asarray(data["y"])
    zs = np.asarray(data["z"])
    points = np.column_stack([xs, ys, zs])
    mask = navis.in_volume(points, _payloadToVolume(volumePayload), inplace=False)
    filtered = {col: np.asarray(values)[mask].tolist() for col, values in data.items()}
    return {"columns": columns, "data": filtered}


def _overlappingNeuropils(driver, volumePayload: dict) -> list[str]:
    """Return names of neuropils whose meshes overlap the given volume.

    Implements `utils.volumeOverlaps`: test each volume vertex against every
    neuropil mesh, retain neuropils that contain at least one vertex.
    """
    region = _payloadToVolume(volumePayload)
    points = region.vertices
    all_meshes = {
        name: _payloadToVolume(payload)
        for name, payload in neuropilCypher.getAllNeuropilMeshes(driver).items()
    }
    if not all_meshes:
        return []
    booleans = navis.in_volume(points, all_meshes, inplace=False)
    return [name for name, mask in booleans.items() if bool(mask.any())]


def _concatTablePayloads(payloads: list[dict]) -> dict:
    """Concatenate a list of TablePayload dicts; preserves columns of the first."""
    if not payloads:
        return {"columns": [], "data": {}}
    columns = payloads[0]["columns"]
    merged: dict[str, list] = {col: [] for col in columns}
    for payload in payloads:
        for col in columns:
            merged[col].extend(payload["data"].get(col, []))
    return {"columns": columns, "data": merged}


def _dedupeTablePayload(payload: dict) -> dict:
    """Remove duplicate rows from a TablePayload, preserving column order."""
    data = payload["data"]
    columns = payload["columns"]
    if not data or not next(iter(data.values()), []):
        return payload
    nrows = len(next(iter(data.values())))
    seen: set[tuple] = set()
    keepIndices: list[int] = []
    for idx in range(nrows):
        key = tuple(data[col][idx] for col in columns)
        if key not in seen:
            seen.add(key)
            keepIndices.append(idx)
    deduped = {col: [data[col][i] for i in keepIndices] for col in columns}
    return {"columns": columns, "data": deduped}


def getRegionSynapseTable(driver, regionSpec) -> dict | None:
    """Dispatch over `RegionSpec` to produce a TablePayload-shaped dict.

    Returns:
        - dict on success.
        - None if (a) the named neuropil is missing, or (b) neither neuropil
          nor volume was supplied (router treats this as 400).

    `regionSpec` is the Pydantic model; access fields by attribute.
    """
    neuropilName = regionSpec.neuropil
    volume = regionSpec.volume.model_dump() if regionSpec.volume is not None else None

    if neuropilName is not None:
        table = synapseCypher.getNeuropilSynapseTable(driver, neuropilName)
        if table is None:
            return None  # neuropil not found
        if volume is not None:
            table = _filterTablePayloadByVolume(table, volume)
        return _dedupeTablePayload(table)

    if volume is not None:
        overlapping = _overlappingNeuropils(driver, volume)
        tables = []
        for name in overlapping:
            table = synapseCypher.getNeuropilSynapseTable(driver, name)
            if table is None:
                continue
            tables.append(_filterTablePayloadByVolume(table, volume))
        return _dedupeTablePayload(_concatTablePayloads(tables))

    return None  # neither neuropil nor volume specified
