"""Tests for /connectivity, /arborization, /innervation endpoints + cypher helpers.

Where possible, cypher logic is exercised via monkeypatching of the
`regionsCypher.getRegionSynapseTable` boundary so we don't need to mock
dozens of `execute_query` calls just to check the pandas plumbing.
"""

from unittest.mock import MagicMock

import navis
import numpy as np
import pandas as pd

from fba.client import Client
from fba.server.cypher import arborization as arbCypher
from fba.server.cypher import connectivity as connCypher
from fba.server.cypher import innervation as innCypher
from fba.server.cypher._tables import payloadToDataFrame
from fba.server.schemas import (
    ArborizationRequest,
    ConnectivityRequest,
    InnervationRequest,
    MeshPayload,
    RegionSpec,
)


def _executeQueryResult(records):
    return records, MagicMock(), list(records[0].keys()) if records else []


def _regionConnectivityPayload():
    """Synthetic region synapse table with 3 synapses: 2 from A→C, 1 from B→D."""
    return {
        "columns": [
            "x", "y", "z",
            "pre_name", "pre_celltype",
            "post_name", "post_celltype",
            "neurotransmitters",
        ],
        "data": {
            "x": [0.0, 1.0, 2.0],
            "y": [0.0, 0.0, 0.0],
            "z": [0.0, 0.0, 0.0],
            "pre_name": ["A", "A", "B"],
            "pre_celltype": ["X", "X", "Y"],
            "post_name": ["C", "C", "D"],
            "post_celltype": ["Z", "Z", "W"],
            "neurotransmitters": ["ACH", "ACH", "GABA"],
        },
    }


# =====================================================================
# Connectivity — region path (most important branch)
# =====================================================================


def testRegionConnectivityTableNeuron(monkeypatch):
    monkeypatch.setattr(
        connCypher.regionsCypher,
        "getRegionSynapseTable",
        lambda *a, **kw: _regionConnectivityPayload(),
    )
    request = ConnectivityRequest(
        region=RegionSpec(neuropil="LOP"), entity="neuron", layout="table"
    )
    result = connCypher._getRegionConnectivity(MagicMock(), request)
    df = payloadToDataFrame(result)
    assert {"pre_name", "post_name", "synapse_count"} <= set(df.columns)
    ac = df[(df["pre_name"] == "A") & (df["post_name"] == "C")]
    bd = df[(df["pre_name"] == "B") & (df["post_name"] == "D")]
    assert ac["synapse_count"].iloc[0] == 2
    assert bd["synapse_count"].iloc[0] == 1


def testRegionConnectivityTableCelltype(monkeypatch):
    """Celltype rolls up by pre_celltype/post_celltype only."""
    monkeypatch.setattr(
        connCypher.regionsCypher,
        "getRegionSynapseTable",
        lambda *a, **kw: _regionConnectivityPayload(),
    )
    request = ConnectivityRequest(
        region=RegionSpec(neuropil="LOP"), entity="celltype", layout="table"
    )
    result = connCypher._getRegionConnectivity(MagicMock(), request)
    df = payloadToDataFrame(result)
    assert set(df.columns) >= {"pre_celltype", "post_celltype", "synapse_count"}
    xz = df[(df["pre_celltype"] == "X") & (df["post_celltype"] == "Z")]
    yw = df[(df["pre_celltype"] == "Y") & (df["post_celltype"] == "W")]
    assert xz["synapse_count"].iloc[0] == 2
    assert yw["synapse_count"].iloc[0] == 1


def testRegionConnectivityMatrixLayout(monkeypatch):
    monkeypatch.setattr(
        connCypher.regionsCypher,
        "getRegionSynapseTable",
        lambda *a, **kw: _regionConnectivityPayload(),
    )
    request = ConnectivityRequest(
        region=RegionSpec(neuropil="LOP"), entity="neuron", layout="matrix"
    )
    result = connCypher._getRegionConnectivity(MagicMock(), request)
    # matrix payload: first column is the pre-index, rest are post names
    assert "pre_name" in result["columns"]
    df = payloadToDataFrame(result)
    df = df.set_index("pre_name")
    assert df.loc["A", "C"] == 2
    assert df.loc["B", "D"] == 1


def testConnectivityInRegionFiltersByPreAndPostNames(monkeypatch):
    """`names=[[pre], [post]]` keeps only edges with pre∈pre AND post∈post.

    Matches the original FBA semantics: a flat `names=["A"]` requires BOTH
    pre and post to be "A" (useful for restricting to a clique), so to keep
    A→C edges we pass `[["A"], ["C"]]`.
    """
    monkeypatch.setattr(
        connCypher.regionsCypher,
        "getRegionSynapseTable",
        lambda *a, **kw: _regionConnectivityPayload(),
    )
    request = ConnectivityRequest(
        names=[["A"], ["C"]],
        region=RegionSpec(neuropil="LOP"),
        entity="neuron",
        layout="table",
    )
    result = connCypher._getConnectivityInRegion(MagicMock(), request)
    df = payloadToDataFrame(result)
    assert df["pre_name"].tolist() == ["A"]
    assert df["post_name"].tolist() == ["C"]


def testConnectivityInRegionFlatNamesFiltersCliques(monkeypatch):
    """Flat names list filters to pairs where BOTH pre and post are in the list."""
    monkeypatch.setattr(
        connCypher.regionsCypher,
        "getRegionSynapseTable",
        lambda *a, **kw: _regionConnectivityPayload(),
    )
    request = ConnectivityRequest(
        names=["A", "C"],  # interested in edges within {A, C}
        region=RegionSpec(neuropil="LOP"),
        entity="neuron",
    )
    result = connCypher._getConnectivityInRegion(MagicMock(), request)
    df = payloadToDataFrame(result)
    # A→C is the only edge both endpoints of which are in {A, C}
    assert df["pre_name"].tolist() == ["A"]
    assert df["post_name"].tolist() == ["C"]


def testConnectivityRegionMissingNeuropil(monkeypatch):
    monkeypatch.setattr(
        connCypher.regionsCypher,
        "getRegionSynapseTable",
        lambda *a, **kw: None,
    )
    request = ConnectivityRequest(region=RegionSpec(neuropil="NONE"), entity="neuron")
    assert connCypher.getConnectivity(MagicMock(), request) is None


# =====================================================================
# Arborization — region paths
# =====================================================================


def testRegionArborizationNeuron(monkeypatch):
    """Arborization counts per-neuron pre/post synapse totals.

    NOTE: the original FBA names these columns `inputs` and `outputs` but the
    aggregation maps `pre_name → inputs` and `post_name → outputs`, which is
    the *opposite* of the usual neuroscience convention (where input=
    postsynaptic). Lifted verbatim — see TODO in `arborization.py`.
    """
    monkeypatch.setattr(
        connCypher.regionsCypher,
        "getRegionSynapseTable",
        lambda *a, **kw: _regionConnectivityPayload(),
    )
    request = ArborizationRequest(
        region=RegionSpec(neuropil="LOP"), entity="neuron", return_data=True
    )
    result = arbCypher.getArborization(MagicMock(), request)
    df = payloadToDataFrame(result).set_index("name")
    # A is pre on two synapses → inputs (pre-aggregation) = 2
    assert df.loc["A", "inputs"] == 2
    assert df.loc["A", "outputs"] == 0
    # C is post on two synapses → outputs (post-aggregation) = 2
    assert df.loc["C", "outputs"] == 2
    assert df.loc["C", "inputs"] == 0


def testArborizationInRegionFiltersByNames(monkeypatch):
    monkeypatch.setattr(
        connCypher.regionsCypher,
        "getRegionSynapseTable",
        lambda *a, **kw: _regionConnectivityPayload(),
    )
    request = ArborizationRequest(
        names=["A", "C"], region=RegionSpec(neuropil="LOP"), entity="neuron"
    )
    result = arbCypher.getArborization(MagicMock(), request)
    df = payloadToDataFrame(result)
    assert set(df["name"]) == {"A", "C"}


# =====================================================================
# Innervation — server-side with mocked driver (real navis volumes)
# =====================================================================


def _unitCubePayload(origin=(0.0, 0.0, 0.0)) -> dict:
    ox, oy, oz = origin
    vertices = [
        [ox + 0, oy + 0, oz + 0], [ox + 1, oy + 0, oz + 0],
        [ox + 1, oy + 1, oz + 0], [ox + 0, oy + 1, oz + 0],
        [ox + 0, oy + 0, oz + 1], [ox + 1, oy + 0, oz + 1],
        [ox + 1, oy + 1, oz + 1], [ox + 0, oy + 1, oz + 1],
    ]
    faces = [
        [0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7],
        [0, 1, 5], [0, 5, 4], [2, 3, 7], [2, 7, 6],
        [1, 2, 6], [1, 6, 5], [3, 0, 4], [3, 4, 7],
    ]
    return {"name": "cube", "vertices": vertices, "faces": faces}


def testInnervationCountsNeuritesInsideRegion():
    """Single neuron with 3 nodes — 2 inside the unit cube, 1 outside."""
    driver = MagicMock()
    # `_fetchNeuronSkeleton` runs a single execute_query
    driver.execute_query.return_value = _executeQueryResult([
        {
            "skeleton": {
                "x": [0.5, 0.3, 5.0],
                "y": [0.5, 0.5, 5.0],
                "z": [0.5, 0.5, 5.0],
                "r": [1.0, 1.0, 1.0],
                "parent": [-1, 1, 2],
            }
        }
    ])
    cube = _unitCubePayload()
    request = InnervationRequest(
        names=["X"],
        entity="neuron",
        regions={"cube": MeshPayload(**cube)},
        layout="table",
    )
    result = innCypher.getInnervation(driver, request)
    df = payloadToDataFrame(result)
    assert df.loc[df["region"] == "cube", "neurite_count"].iloc[0] == 2


# =====================================================================
# Client-side: regional analysis methods
# =====================================================================


def testClientGetConnectivityBuildsRequest():
    """Client.getConnectivity should POST a well-formed body."""
    client = Client("http://localhost:8000")
    response_payload = {
        "columns": ["pre_name", "post_name", "synapse_count"],
        "data": {"pre_name": ["A"], "post_name": ["B"], "synapse_count": [5]},
    }
    client._post = MagicMock(return_value=response_payload)
    region = client.neuropil("LOP")

    df = client.getConnectivity(names=["A", "B"], region=region, entity="neuron")
    assert df["synapse_count"].iloc[0] == 5

    posted_path = client._post.call_args.args[0]
    body = client._post.call_args.kwargs["json"]
    assert posted_path == "/connectivity"
    assert body["names"] == ["A", "B"]
    assert body["entity"] == "neuron"
    assert body["region"] == {"neuropil": "LOP"}


def testClientGetConnectivityMatrixSetsIndex():
    client = Client("http://localhost:8000")
    response_payload = {
        "columns": ["pre_name", "B", "C"],
        "data": {"pre_name": ["A"], "B": [1], "C": [2]},
    }
    client._post = MagicMock(return_value=response_payload)
    df = client.getConnectivity(names=["A", "B", "C"], layout="matrix")
    assert df.index.name == "pre_name"
    assert df.loc["A", "B"] == 1


def testRegionConnectivityMethod():
    """Region.connectivity delegates to Client.getConnectivity with itself as region."""
    client = Client("http://localhost:8000")
    response_payload = {
        "columns": ["pre_name", "post_name", "synapse_count"],
        "data": {"pre_name": [], "post_name": [], "synapse_count": []},
    }
    client._post = MagicMock(return_value=response_payload)
    region = client.neuropil("LOP")
    _ = region.connectivity()
    body = client._post.call_args.kwargs["json"]
    assert body["region"] == {"neuropil": "LOP"}


def testRegionArborizationMethod():
    client = Client("http://localhost:8000")
    response_payload = {
        "columns": ["name", "inputs", "outputs"],
        "data": {"name": ["A"], "inputs": [10], "outputs": [20]},
    }
    client._post = MagicMock(return_value=response_payload)
    region = client.neuropil("LOP")
    df = region.arborization()
    assert df["inputs"].iloc[0] == 10
    assert client._post.call_args.args[0] == "/arborization"


def testClientGetInnervationBuildsRegionsBody():
    client = Client("http://localhost:8000")
    response_payload = {
        "columns": ["name", "region", "neurite_count"],
        "data": {"name": ["X"], "region": ["cube"], "neurite_count": [3]},
    }
    client._post = MagicMock(return_value=response_payload)
    cube = navis.Volume(
        vertices=np.asarray(_unitCubePayload()["vertices"]),
        faces=np.asarray(_unitCubePayload()["faces"]),
        name="cube",
    )
    df = client.getInnervation(names=["X"], regions={"cube": cube})
    assert df["neurite_count"].iloc[0] == 3
    body = client._post.call_args.kwargs["json"]
    assert "regions" in body
    assert body["regions"]["cube"]["name"] == "cube"
