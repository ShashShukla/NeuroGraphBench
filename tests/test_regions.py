"""Tests for /regions/synapses and the region-level dispatch logic.

Server-side unit tests target the dispatch helpers in `fba.server.cypher.regions`
directly; one integration test exercises the full HTTP path.
"""

from unittest.mock import MagicMock

from fba.server.cypher import regions as regionsCypher
from fba.server.schemas import RegionSpec


# ---------- helpers ----------


def _unitCubePayload(name: str = "cube", origin: tuple = (0.0, 0.0, 0.0)) -> dict:
    """A closed-mesh unit cube at `origin`."""
    ox, oy, oz = origin
    vertices = [
        [ox + 0, oy + 0, oz + 0],
        [ox + 1, oy + 0, oz + 0],
        [ox + 1, oy + 1, oz + 0],
        [ox + 0, oy + 1, oz + 0],
        [ox + 0, oy + 0, oz + 1],
        [ox + 1, oy + 0, oz + 1],
        [ox + 1, oy + 1, oz + 1],
        [ox + 0, oy + 1, oz + 1],
    ]
    faces = [
        [0, 1, 2], [0, 2, 3],  # bottom
        [4, 5, 6], [4, 6, 7],  # top
        [0, 1, 5], [0, 5, 4],  # front
        [2, 3, 7], [2, 7, 6],  # back
        [1, 2, 6], [1, 6, 5],  # right
        [3, 0, 4], [3, 4, 7],  # left
    ]
    return {"name": name, "vertices": vertices, "faces": faces}


def _samplePayload() -> dict:
    """A synapse table with 4 points — two inside [0,1]^3, two outside."""
    return {
        "columns": ["x", "y", "z", "pre_name", "post_name"],
        "data": {
            "x": [0.5, 0.3, 5.0, 5.5],
            "y": [0.5, 0.4, 5.0, 5.5],
            "z": [0.5, 0.4, 5.0, 5.5],
            "pre_name": ["A", "A", "B", "B"],
            "post_name": ["C", "D", "C", "D"],
        },
    }


def _executeQueryResult(records: list[dict]) -> tuple:
    return records, MagicMock(), list(records[0].keys()) if records else []


# ---------- unit tests: dispatch helpers ----------


def testFilterTablePayloadByVolumeKeepsInsidePoints():
    cube = _unitCubePayload()
    filtered = regionsCypher._filterTablePayloadByVolume(_samplePayload(), cube)
    # Only the first two rows (inside the cube) survive.
    assert filtered["data"]["x"] == [0.5, 0.3]
    assert filtered["data"]["pre_name"] == ["A", "A"]
    assert filtered["data"]["post_name"] == ["C", "D"]


def testDedupeTablePayload():
    payload = {
        "columns": ["x", "name"],
        "data": {"x": [0.0, 0.0, 1.0], "name": ["A", "A", "B"]},
    }
    deduped = regionsCypher._dedupeTablePayload(payload)
    assert deduped["data"]["x"] == [0.0, 1.0]
    assert deduped["data"]["name"] == ["A", "B"]


def testConcatTablePayloads():
    a = {"columns": ["x"], "data": {"x": [1.0, 2.0]}}
    b = {"columns": ["x"], "data": {"x": [3.0]}}
    merged = regionsCypher._concatTablePayloads([a, b])
    assert merged["data"]["x"] == [1.0, 2.0, 3.0]


def testConcatTablePayloadsEmpty():
    assert regionsCypher._concatTablePayloads([]) == {"columns": [], "data": {}}


# ---------- dispatch tests via getRegionSynapseTable ----------


def testGetRegionSynapseTableNeuropilOnly(mockDriver):
    """neuropil-only path delegates to getNeuropilSynapseTable."""
    cached = _samplePayload()
    # exists check + cache hit
    mockDriver.execute_query.side_effect = [
        _executeQueryResult([{"neuropil": {"name": "LOP"}}]),
        _executeQueryResult([{"synapse_table": {col: list(cached["data"][col]) for col in cached["columns"]}}]),
    ]
    spec = RegionSpec(neuropil="LOP")
    result = regionsCypher.getRegionSynapseTable(mockDriver, spec)
    assert result is not None
    assert result["data"]["pre_name"] == ["A", "A", "B", "B"]


def testGetRegionSynapseTableNeuropilPlusVolumeFilters(mockDriver):
    """neuropil + volume → fetch neuropil table, then volume-filter."""
    cached = _samplePayload()
    mockDriver.execute_query.side_effect = [
        _executeQueryResult([{"neuropil": {"name": "LOP"}}]),
        _executeQueryResult([{"synapse_table": {col: list(cached["data"][col]) for col in cached["columns"]}}]),
    ]
    spec = RegionSpec(neuropil="LOP", volume=_unitCubePayload())
    result = regionsCypher.getRegionSynapseTable(mockDriver, spec)
    assert result is not None
    # Volume filter retains only the two points inside the unit cube.
    assert result["data"]["x"] == [0.5, 0.3]


def testGetRegionSynapseTableNeuropilNotFound(mockDriver):
    """neuropil-only path returns None when neuropil is missing."""
    mockDriver.execute_query.return_value = _executeQueryResult([])  # exists check fails
    spec = RegionSpec(neuropil="NONEXISTENT")
    assert regionsCypher.getRegionSynapseTable(mockDriver, spec) is None


def testGetRegionSynapseTableVolumeOnly(mockDriver):
    """volume-only path: overlap-detect, fetch per-neuropil, filter, concat."""
    cubeA = _unitCubePayload(name="LOP", origin=(0.0, 0.0, 0.0))
    cubeB = _unitCubePayload(name="MB", origin=(10.0, 10.0, 10.0))
    queryVolume = _unitCubePayload(name="query", origin=(0.25, 0.25, 0.25))
    cached = _samplePayload()
    # Three queries from getAllNeuropilMeshes, then per-neuropil exists+cache.
    mockDriver.execute_query.side_effect = [
        # getAllNeuropilMeshes
        _executeQueryResult([
            {"name": "LOP", "mesh": _meshNodeFromPayload(cubeA)},
            {"name": "MB", "mesh": _meshNodeFromPayload(cubeB)},
        ]),
        # LOP exists check
        _executeQueryResult([{"neuropil": {"name": "LOP"}}]),
        # LOP cache hit
        _executeQueryResult([{"synapse_table": {col: list(cached["data"][col]) for col in cached["columns"]}}]),
    ]
    spec = RegionSpec(volume=queryVolume)
    result = regionsCypher.getRegionSynapseTable(mockDriver, spec)
    assert result is not None
    # Only LOP overlaps the query volume; only inside-cube points survive.
    assert result["data"]["x"] == [0.5, 0.3]


def testGetRegionSynapseTableNeitherSpecified(mockDriver):
    """Empty region (no neuropil, no volume) returns None."""
    spec = RegionSpec()
    assert regionsCypher.getRegionSynapseTable(mockDriver, spec) is None


def _meshNodeFromPayload(payload: dict) -> dict:
    """Reverse of `_meshFromRecord`: build a neo4j-shaped mesh node from MeshPayload."""
    vs = payload["vertices"]
    fs = payload["faces"]
    return {
        "x": [v[0] for v in vs], "y": [v[1] for v in vs], "z": [v[2] for v in vs],
        "i": [f[0] for f in fs], "j": [f[1] for f in fs], "k": [f[2] for f in fs],
    }


# ---------- integration: HTTP path ----------


def testPostRegionsSynapsesNeuropilOnly(client, mockDriver):
    cached = _samplePayload()
    mockDriver.execute_query.side_effect = [
        _executeQueryResult([{"neuropil": {"name": "LOP"}}]),
        _executeQueryResult([{"synapse_table": {col: list(cached["data"][col]) for col in cached["columns"]}}]),
    ]
    response = client.post("/regions/synapses", json={"neuropil": "LOP"})
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["pre_name"] == ["A", "A", "B", "B"]


def testPostRegionsSynapsesInvalidReturns400(client, mockDriver):
    response = client.post("/regions/synapses", json={})
    assert response.status_code == 400


def testPostRegionsSynapsesMissingNeuropilReturns404(client, mockDriver):
    mockDriver.execute_query.return_value = _executeQueryResult([])
    response = client.post("/regions/synapses", json={"neuropil": "NONEXISTENT"})
    assert response.status_code == 404
