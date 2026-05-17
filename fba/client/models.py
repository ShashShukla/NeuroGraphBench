"""Object-relational layer over the raw FBA client.

Exposes connectomic entities as Python objects with relationships, so users
can write::

    neuron  = client.neuron("LPLC2_R_1")
    region  = client.neuropil("LOP")
    segment = neuron.segmentIn(region)
    syns    = segment.synapses                 # pandas.DataFrame
    parts   = neuron.partners(region=region)   # list[Neuron]

Both surfaces co-exist: raw methods on `Client` return DataFrames / navis
objects directly; the object model wraps those for richer relational access
and lazy fetching with attribute-level caching.

All classes hold a reference to the originating `Client` and lazily fetch
data on first access. Method names follow camelCase per project convention.

Classes (to be implemented across the first and follow-up slices):
    Region    — neuropil, subregion, or arbitrary volume   [first slice: neuropil case]
    Celltype  — named celltype, collection of Neurons      [TODO]
    Neuron    — single neuron with skeleton + synapses     [TODO]
    Segment   — neurite subset of a Neuron                  [TODO]
    Synapse   — single synapse record                       [TODO]
    Column    — retinotopic hex coordinate                  [TODO]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import navis
    import pandas as pd

    from .http import Client


class Region:
    """A region — neuropil, subregion, or arbitrary volume.

    Construction::

        region = client.neuropil("LOP")    # named neuropil
        # later slices: Region(client, volume=mesh) for arbitrary volumes

    Lazy properties (each fetched on first access and cached):
        name        — region name
        mesh        — bounding mesh (navis.Volume)
        subregions  — list[Region] of named subregions
        neurons     — list[str] of neurons arborizing here
        celltypes   — list[str] of celltypes arborizing here

    Methods:
        synapseTable() — pandas.DataFrame of synapses in the region
    """

    def __init__(
        self,
        client: Client,
        *,
        neuropil: str | None = None,
        volume: navis.Volume | None = None,
    ):
        if neuropil is None and volume is None:
            raise ValueError("Region requires `neuropil` or `volume`.")
        self._client = client
        self._neuropil = neuropil
        self._mesh: navis.Volume | None = volume
        self._subregions: list[Region] | None = None
        self._neurons: list[str] | None = None
        self._celltypes: list[str] | None = None
        self._synapseTable: pd.DataFrame | None = None

    @property
    def name(self) -> str:
        if self._neuropil is not None:
            return self._neuropil
        assert self._mesh is not None
        return self._mesh.name

    @property
    def mesh(self) -> navis.Volume:
        """Return the region's bounding mesh; lazily fetched on first access."""
        if self._mesh is None:
            assert self._neuropil is not None
            self._mesh = self._client.getNeuropilMesh(self._neuropil)
        return self._mesh

    @property
    def subregions(self) -> list[Region]:
        """Return the named subregions of this neuropil.

        Only valid for neuropil-backed regions; arbitrary volumes have no
        named subregions in the schema.
        """
        if self._subregions is None:
            if self._neuropil is None:
                raise ValueError("subregions are only defined for named neuropils")
            meshes = self._client.listSubregions(self._neuropil)
            self._subregions = [Region(self._client, volume=mesh) for mesh in meshes]
        return self._subregions

    @property
    def neurons(self) -> list[str]:
        """Return names of neurons arborizing in this region."""
        if self._neurons is None:
            if self._neuropil is None:
                raise NotImplementedError(
                    "`neurons` for volume-defined regions is not yet implemented"
                )
            self._neurons = self._client.listNeuronsInNeuropil(self._neuropil)
        return self._neurons

    @property
    def celltypes(self) -> list[str]:
        """Return distinct celltypes arborizing in this region."""
        if self._celltypes is None:
            if self._neuropil is None:
                raise NotImplementedError(
                    "`celltypes` for volume-defined regions is not yet implemented"
                )
            self._celltypes = self._client.listCelltypesInNeuropil(self._neuropil)
        return self._celltypes

    def synapseTable(self) -> pd.DataFrame:
        """Return the synapse table for this region (cached on first call).

        Dispatches based on the Region's specification:
        - neuropil only      → hits `/neuropils/{name}/synapses` (cheaper, cached).
        - volume present     → POST `/regions/synapses` (volume filter on server).
        """
        if self._synapseTable is None:
            if self._mesh is None and self._neuropil is not None:
                # Fast path: avoid a POST + volume serialization for the common
                # "named neuropil, no extra volume" case.
                self._synapseTable = self._client.getNeuropilSynapseTable(self._neuropil)
            else:
                self._synapseTable = self._client.getRegionSynapseTable(self)
        return self._synapseTable

    # ---- regional analysis ----

    def connectivity(
        self,
        names: "list[str] | list[list[str]] | None" = None,
        entity: str = "neuron",
        layout: str = "table",
    ) -> pd.DataFrame:
        """Connectivity within this region, optionally restricted to `names`."""
        return self._client.getConnectivity(
            names=names, entity=entity, region=self, layout=layout
        )

    def arborization(
        self,
        names: "list[str] | None" = None,
        entity: str = "neuron",
    ) -> pd.DataFrame:
        """Arborization counts within this region, optionally restricted to `names`."""
        return self._client.getArborization(names=names, entity=entity, region=self)

    def __repr__(self) -> str:
        return f"Region(name={self.name!r})"
