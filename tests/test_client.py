"""Tests for the client-side deserializer and object-model surface.

Server interaction is mocked at the `Client._get` boundary so the client is
exercised in isolation from FastAPI.
"""

from unittest.mock import MagicMock

import navis
import numpy as np
import pandas as pd

from fba.client import Client, Region
from fba.client.deserialize import meshFromPayload, meshListFromPayload, tableFromPayload
from fba.client.serialize import meshToPayload, regionToSpec


# ---------- deserializers ----------


def testMeshFromPayload():
    payload = {
        "name": "LOP",
        "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
        "faces": [[0, 1, 2]],
    }
    volume = meshFromPayload(payload)
    assert isinstance(volume, navis.Volume)
    assert volume.name == "LOP"
    assert np.array_equal(volume.vertices, np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]]))
    assert np.array_equal(volume.faces, np.array([[0, 1, 2]]))


def testMeshListFromPayload():
    payloads = [
        {"name": "LOP-1", "vertices": [[0, 0, 0]], "faces": [[0, 0, 0]]},
        {"name": "LOP-2", "vertices": [[1, 0, 0]], "faces": [[0, 0, 0]]},
    ]
    volumes = meshListFromPayload(payloads)
    assert [v.name for v in volumes] == ["LOP-1", "LOP-2"]


def testTableFromPayload():
    payload = {
        "columns": ["x", "pre_name", "post_name"],
        "data": {"x": [0.5, 1.5], "pre_name": ["A", "B"], "post_name": ["C", "D"]},
    }
    df = tableFromPayload(payload)
    assert list(df.columns) == ["x", "pre_name", "post_name"]
    assert df["pre_name"].tolist() == ["A", "B"]
    assert df["x"].tolist() == [0.5, 1.5]


def testTableFromPayloadEmpty():
    payload = {"columns": ["x", "y"], "data": {"x": [], "y": []}}
    df = tableFromPayload(payload)
    assert list(df.columns) == ["x", "y"]
    assert len(df) == 0


# ---------- Client + Region ----------


def _makeClientWithGet(payloadByPath):
    """Helper: create a Client whose `_get` returns a fixed payload per path."""
    client = Client("http://localhost:8000")

    def fake_get(path, **params):
        return payloadByPath[path]

    client._get = MagicMock(side_effect=fake_get)
    return client


def testClientNeuropilReturnsRegion():
    client = Client("http://localhost:8000")
    region = client.neuropil("LOP")
    assert isinstance(region, Region)
    assert region.name == "LOP"


def testRegionLazilyFetchesMesh():
    payload = {
        "name": "LOP",
        "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
        "faces": [[0, 1, 2]],
    }
    client = _makeClientWithGet({"/neuropils/LOP": payload})

    region = client.neuropil("LOP")
    assert client._get.call_count == 0

    mesh1 = region.mesh
    assert client._get.call_count == 1
    assert isinstance(mesh1, navis.Volume)
    assert mesh1.name == "LOP"

    # cache hit — no further calls
    mesh2 = region.mesh
    assert client._get.call_count == 1
    assert mesh2 is mesh1


def testRegionSubregions():
    payloads = [
        {"name": "LOP-1", "vertices": [[0, 0, 0]], "faces": [[0, 0, 0]]},
        {"name": "LOP-2", "vertices": [[1, 0, 0]], "faces": [[0, 0, 0]]},
    ]
    client = _makeClientWithGet({"/neuropils/LOP/subregions": payloads})

    region = client.neuropil("LOP")
    subs = region.subregions
    assert all(isinstance(s, Region) for s in subs)
    assert [s.name for s in subs] == ["LOP-1", "LOP-2"]

    # cached — no second HTTP call
    assert client._get.call_count == 1
    _ = region.subregions
    assert client._get.call_count == 1


def testRegionNeuronsAndCelltypes():
    client = _makeClientWithGet(
        {
            "/neuropils/LOP/neurons": ["LPLC2_R_1", "LPLC2_R_2"],
            "/neuropils/LOP/celltypes": ["LPLC2"],
        }
    )

    region = client.neuropil("LOP")
    assert region.neurons == ["LPLC2_R_1", "LPLC2_R_2"]
    assert region.celltypes == ["LPLC2"]
    # cached on second access
    _ = region.neurons
    _ = region.celltypes
    assert client._get.call_count == 2


def testRegionSynapseTable():
    payload = {
        "columns": ["x", "pre_name", "post_name"],
        "data": {"x": [0.1, 0.2], "pre_name": ["A", "A"], "post_name": ["B", "C"]},
    }
    client = _makeClientWithGet({"/neuropils/LOP/synapses": payload})

    region = client.neuropil("LOP")
    df = region.synapseTable()
    assert isinstance(df, pd.DataFrame)
    assert df["pre_name"].tolist() == ["A", "A"]
    # cached on second access
    df2 = region.synapseTable()
    assert df2 is df
    assert client._get.call_count == 1


def testRegionRequiresNeuropilOrVolume():
    client = Client("http://localhost:8000")
    try:
        Region(client=client)
    except ValueError:
        pass
    else:
        raise AssertionError("Region() with no args should raise ValueError")


# ---------- serializers ----------


def testMeshToPayloadRoundTrip():
    payload = {
        "name": "LOP",
        "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
        "faces": [[0, 1, 2]],
    }
    volume = meshFromPayload(payload)
    roundtrip = meshToPayload(volume)
    assert roundtrip["name"] == "LOP"
    assert roundtrip["vertices"] == [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert roundtrip["faces"] == [[0, 1, 2]]


def testRegionToSpecNeuropilOnly():
    client = Client("http://localhost:8000")
    region = client.neuropil("LOP")
    spec = regionToSpec(region)
    assert spec == {"neuropil": "LOP"}


def testRegionToSpecVolumeOnly():
    import navis
    import numpy as np

    volume = navis.Volume(
        vertices=np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
        faces=np.array([[0, 1, 2]]),
        name="query",
    )
    client = Client("http://localhost:8000")
    region = client.region(volume=volume)
    spec = regionToSpec(region)
    assert "neuropil" not in spec
    assert spec["volume"]["name"] == "query"
    assert spec["volume"]["vertices"] == [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert spec["volume"]["faces"] == [[0, 1, 2]]


def testRegionToSpecNeuropilPlusVolume():
    import navis
    import numpy as np

    volume = navis.Volume(
        vertices=np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
        faces=np.array([[0, 1, 2]]),
        name="lpu",
    )
    client = Client("http://localhost:8000")
    region = client.region(neuropil="LOP", volume=volume)
    spec = regionToSpec(region)
    assert spec["neuropil"] == "LOP"
    assert spec["volume"]["name"] == "lpu"


def testRegionToSpecDoesNotFetchMesh():
    """Serializing a neuropil-only Region must not trigger a mesh fetch."""
    client = Client("http://localhost:8000")
    client._get = MagicMock(side_effect=AssertionError("should not be called"))
    region = client.neuropil("LOP")
    spec = regionToSpec(region)
    assert spec == {"neuropil": "LOP"}
    client._get.assert_not_called()


# ---------- Region.synapseTable with volume case ----------


def testRegionSynapseTableVolumeCaseUsesPost():
    """When the Region carries a volume, synapseTable hits POST /regions/synapses."""
    import navis
    import numpy as np

    payload = {
        "columns": ["x", "pre_name"],
        "data": {"x": [0.1, 0.2], "pre_name": ["A", "B"]},
    }
    volume = navis.Volume(
        vertices=np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
        faces=np.array([[0, 1, 2]]),
        name="query",
    )
    client = Client("http://localhost:8000")
    client._post = MagicMock(return_value=payload)
    client._get = MagicMock(side_effect=AssertionError("GET should not be called"))

    region = client.region(volume=volume)
    df = region.synapseTable()
    assert df["pre_name"].tolist() == ["A", "B"]
    client._post.assert_called_once()
    posted_path, kwargs = client._post.call_args.args[0], client._post.call_args.kwargs
    assert posted_path == "/regions/synapses"
    assert kwargs["json"]["volume"]["name"] == "query"
