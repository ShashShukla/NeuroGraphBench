"""HTTP transport for the FBA client.

`Client` wraps a `requests.Session` with a base URL and exposes one Python
method per implemented REST endpoint, plus object-model factories.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import requests

from .deserialize import meshFromPayload, meshListFromPayload, tableFromPayload

if TYPE_CHECKING:
    import navis
    import pandas as pd

    from .models import Region


class Client:
    """Client for the FlyBrainAtlas REST API.

    Two co-existing surfaces:

    - **Raw methods** — return primitive Python types (lists, navis objects,
      pandas DataFrames). Use when you want full control over the data.
    - **Object factories** (`neuropil`, `neuron`, ...) — return entities from
      `fba.client.models`. Use for relational access with lazy fetching.

    Example::

        client = Client("http://localhost:8000")
        names  = client.listNeuropils()
        lop    = client.neuropil("LOP")  # Region
        mesh   = lop.mesh                # navis.Volume (lazily fetched)
    """

    def __init__(self, base_url: str = "http://localhost:8000", *, timeout: float = 30.0):
        self._baseUrl = base_url.rstrip("/")
        self._session = requests.Session()
        self._timeout = timeout

    # ---- transport ----

    def _get(self, path: str, **params: Any) -> Any:
        response = self._session.get(
            f"{self._baseUrl}{path}", params=params or None, timeout=self._timeout
        )
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, json: Any) -> Any:
        response = self._session.post(
            f"{self._baseUrl}{path}", json=json, timeout=self._timeout
        )
        response.raise_for_status()
        return response.json()

    # ---- raw methods: /neuropils ----

    def listNeuropils(self) -> list[str]:
        """Return the names of all neuropils in the database."""
        return self._get("/neuropils")

    def getNeuropilMesh(self, name: str) -> navis.Volume:
        """Return a single neuropil's mesh as a `navis.Volume`."""
        return meshFromPayload(self._get(f"/neuropils/{name}"))

    def listSubregions(self, name: str) -> list[navis.Volume]:
        """Return the subregion meshes of a neuropil."""
        return meshListFromPayload(self._get(f"/neuropils/{name}/subregions"))

    def listNeuronsInNeuropil(self, name: str) -> list[str]:
        """Return neurons arborizing in the given neuropil."""
        return self._get(f"/neuropils/{name}/neurons")

    def listCelltypesInNeuropil(self, name: str) -> list[str]:
        """Return distinct celltypes arborizing in the given neuropil."""
        return self._get(f"/neuropils/{name}/celltypes")

    def getNeuropilSynapseTable(self, name: str) -> pd.DataFrame:
        """Return the cached synapse table for a neuropil."""
        return tableFromPayload(self._get(f"/neuropils/{name}/synapses"))

    # ---- raw methods: /regions ----

    def getRegionSynapseTable(self, region: "Region") -> pd.DataFrame:
        """Return the synapse table for an arbitrary region (neuropil and/or volume)."""
        from .serialize import regionToSpec

        spec = regionToSpec(region)
        return tableFromPayload(self._post("/regions/synapses", json=spec))

    # ---- raw methods: /connectivity, /arborization, /innervation ----

    def getConnectivity(
        self,
        names: list[str] | list[list[str]] | None = None,
        entity: str = "neuron",
        region: "Region | None" = None,
        layout: str = "table",
    ) -> pd.DataFrame:
        """Connectivity table (or matrix) for a set of neurons/celltypes and/or region."""
        body = self._buildRegionalRequest(names, entity, region, layout=layout)
        df = tableFromPayload(self._post("/connectivity", json=body))
        return self._setMatrixIndex(df, layout, entity, kind="pre")

    def getArborization(
        self,
        names: list[str] | None = None,
        entity: str = "neuron",
        region: "Region | None" = None,
    ) -> pd.DataFrame:
        """Arborization (input/output) counts for neurons/celltypes and/or region."""
        body = self._buildRegionalRequest(names, entity, region)
        return tableFromPayload(self._post("/arborization", json=body))

    def getInnervation(
        self,
        names: list[str],
        entity: str = "neuron",
        regions: "dict[str, navis.Volume] | None" = None,
        threshold: float = 0.0,
        layout: str = "table",
    ) -> pd.DataFrame:
        """Per-region neurite counts for a circuit. `regions` omitted → all neuropils."""
        from .serialize import meshToPayload

        body: dict = {
            "names": names,
            "entity": entity,
            "threshold": threshold,
            "layout": layout,
        }
        if regions is not None:
            body["regions"] = {name: meshToPayload(vol) for name, vol in regions.items()}
        df = tableFromPayload(self._post("/innervation", json=body))
        if layout == "matrix" and entity in ("neuron", "celltype"):
            name_col = "name" if entity == "neuron" else "celltype"
            if name_col in df.columns:
                df = df.set_index(name_col)
        return df

    # ---- helpers ----

    def _buildRegionalRequest(
        self,
        names,
        entity: str,
        region: "Region | None",
        **extra,
    ) -> dict:
        from .serialize import regionToSpec

        body: dict = {"entity": entity, **extra}
        if names is not None:
            body["names"] = names
        if region is not None:
            body["region"] = regionToSpec(region)
        return body

    @staticmethod
    def _setMatrixIndex(df: pd.DataFrame, layout: str, entity: str, *, kind: str):
        if layout != "matrix":
            return df
        prefix = "pre" if kind == "pre" else "post"
        index_col = f"{prefix}_name" if entity == "neuron" else f"{prefix}_celltype"
        if index_col in df.columns:
            df = df.set_index(index_col)
        return df

    # ---- object factories ----

    def neuropil(self, name: str) -> Region:
        """Return a `Region` representing a named neuropil."""
        from .models import Region

        return Region(client=self, neuropil=name)

    def region(
        self,
        *,
        neuropil: str | None = None,
        volume: "navis.Volume | None" = None,
    ) -> Region:
        """Construct a `Region` from a neuropil name, a mesh, or both (LPU)."""
        from .models import Region

        return Region(client=self, neuropil=neuropil, volume=volume)
