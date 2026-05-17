"""Smoke tests for the /neuropils endpoints."""

from unittest.mock import MagicMock


def _executeQueryResult(records: list[dict]) -> tuple:
    """Build a (records, summary, keys) tuple matching neo4j's `execute_query`."""
    return records, MagicMock(), list(records[0].keys()) if records else []


def _meshRecord(vertices, faces, name=None):
    """Build a single neo4j VolumeMesh record (parallel x/y/z + i/j/k)."""
    mesh = {
        "x": [v[0] for v in vertices],
        "y": [v[1] for v in vertices],
        "z": [v[2] for v in vertices],
        "i": [f[0] for f in faces],
        "j": [f[1] for f in faces],
        "k": [f[2] for f in faces],
    }
    if name is None:
        return {"mesh": mesh}
    return {"name": name, "mesh": mesh}


# ---------------------------------------------------------------------------
# /neuropils  +  /neuropils/{name}
# ---------------------------------------------------------------------------


def testListNeuropilsReturnsNames(client, mockDriver):
    mockDriver.execute_query.return_value = _executeQueryResult(
        [{"name": "LO"}, {"name": "LOP"}, {"name": "MB"}]
    )
    response = client.get("/neuropils")
    assert response.status_code == 200
    assert response.json() == ["LO", "LOP", "MB"]


def testListNeuropilsEmptyDatabase(client, mockDriver):
    mockDriver.execute_query.return_value = _executeQueryResult([])
    response = client.get("/neuropils")
    assert response.status_code == 200
    assert response.json() == []


def testGetNeuropilReturnsMesh(client, mockDriver):
    mockDriver.execute_query.return_value = _executeQueryResult(
        [_meshRecord([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]])]
    )
    response = client.get("/neuropils/LOP")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "LOP"
    assert body["vertices"] == [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert body["faces"] == [[0, 1, 2]]


def testGetNeuropilNotFoundReturns404(client, mockDriver):
    mockDriver.execute_query.return_value = _executeQueryResult([])
    response = client.get("/neuropils/NONEXISTENT")
    assert response.status_code == 404
    assert "NONEXISTENT" in response.json()["detail"]


# ---------------------------------------------------------------------------
# /neuropils/{name}/subregions
# ---------------------------------------------------------------------------


def testListSubregionsReturnsMeshes(client, mockDriver):
    mockDriver.execute_query.side_effect = [
        _executeQueryResult([{"r": {"name": "LOP"}}]),  # neuropil exists
        _executeQueryResult(
            [
                _meshRecord([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]], name="LOP-1"),
                _meshRecord([[0, 0, 0], [0, 1, 0], [0, 0, 1]], [[0, 1, 2]], name="LOP-2"),
            ]
        ),
    ]
    response = client.get("/neuropils/LOP/subregions")
    assert response.status_code == 200
    body = response.json()
    assert [m["name"] for m in body] == ["LOP-1", "LOP-2"]
    assert body[0]["vertices"] == [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]


def testListSubregionsEmptyForNeuropilWithoutSubregions(client, mockDriver):
    mockDriver.execute_query.side_effect = [
        _executeQueryResult([{"r": {"name": "MB"}}]),  # exists
        _executeQueryResult([]),                       # no subregions
    ]
    response = client.get("/neuropils/MB/subregions")
    assert response.status_code == 200
    assert response.json() == []


def testListSubregions404(client, mockDriver):
    mockDriver.execute_query.return_value = _executeQueryResult([])  # exists check fails
    response = client.get("/neuropils/NONEXISTENT/subregions")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# /neuropils/{name}/neurons
# ---------------------------------------------------------------------------


def testListNeuronsInNeuropil(client, mockDriver):
    mockDriver.execute_query.side_effect = [
        _executeQueryResult([{"r": {"name": "LOP"}}]),
        _executeQueryResult([{"name": "LPLC2_R_1"}, {"name": "LPLC2_R_2"}]),
    ]
    response = client.get("/neuropils/LOP/neurons")
    assert response.status_code == 200
    assert response.json() == ["LPLC2_R_1", "LPLC2_R_2"]


def testListNeuronsInNeuropil404(client, mockDriver):
    mockDriver.execute_query.return_value = _executeQueryResult([])
    response = client.get("/neuropils/NONE/neurons")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# /neuropils/{name}/celltypes
# ---------------------------------------------------------------------------


def testListCelltypesInNeuropil(client, mockDriver):
    mockDriver.execute_query.side_effect = [
        _executeQueryResult([{"r": {"name": "LOP"}}]),
        _executeQueryResult([{"celltype": "LPLC2"}, {"celltype": "T4a"}]),
    ]
    response = client.get("/neuropils/LOP/celltypes")
    assert response.status_code == 200
    assert response.json() == ["LPLC2", "T4a"]


def testListCelltypesInNeuropil404(client, mockDriver):
    mockDriver.execute_query.return_value = _executeQueryResult([])
    response = client.get("/neuropils/NONE/celltypes")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# /neuropils/{name}/synapses
# ---------------------------------------------------------------------------


def testGetNeuropilSynapsesCachedPath(client, mockDriver):
    """Cached SynapseTable found — no fallback fetch."""
    cachedTable = {
        "x": [0.0, 1.0],
        "y": [0.0, 1.0],
        "z": [0.0, 1.0],
        "pre_name": ["A", "A"],
        "pre_celltype": ["X", "X"],
        "post_name": ["B", "C"],
        "post_celltype": ["Y", "Y"],
        "neurotransmitters": ["GABA", "GABA"],
    }
    mockDriver.execute_query.side_effect = [
        _executeQueryResult([{"neuropil": {"name": "LOP"}}]),  # exists check
        _executeQueryResult([{"synapse_table": cachedTable}]),  # cache hit
    ]
    response = client.get("/neuropils/LOP/synapses")
    assert response.status_code == 200
    body = response.json()
    assert body["columns"] == list(cachedTable.keys())
    assert body["data"]["pre_name"] == ["A", "A"]
    assert body["data"]["post_name"] == ["B", "C"]


def testGetNeuropilSynapsesFetchFallback(client, mockDriver):
    """No cached SynapseTable — server runs the heavy fetch path."""
    mockDriver.execute_query.side_effect = [
        _executeQueryResult([{"neuropil": {"name": "LOP"}}]),  # exists check
        _executeQueryResult([]),                                # cache miss
        _executeQueryResult(                                    # fetch
            [
                {
                    "rss": {"ids": [0, 1]},
                    "sc": {"x": [0.0, 1.0, 2.0], "y": [0.0, 1.0, 2.0], "z": [0.0, 1.0, 2.0]},
                    "pre_neuron": {"name": "A", "celltype": "X", "neurotransmitters": ["ACH"]},
                    "post_neuron": {"name": "B", "celltype": "Y", "neurotransmitters": ["GABA"]},
                }
            ]
        ),
        _executeQueryResult([{"neuron": {"neurotransmitters": ["ACH"]}}]),  # NT detection
    ]
    response = client.get("/neuropils/LOP/synapses")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["x"] == [0.0, 1.0]
    assert body["data"]["pre_name"] == ["A", "A"]
    assert body["data"]["post_name"] == ["B", "B"]
    assert body["data"]["neurotransmitters"] == ["ACH", "ACH"]


def testGetNeuropilSynapses404(client, mockDriver):
    mockDriver.execute_query.return_value = _executeQueryResult([])  # exists check fails
    response = client.get("/neuropils/NONE/synapses")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


def testHealthEndpoint(client, mockDriver):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
