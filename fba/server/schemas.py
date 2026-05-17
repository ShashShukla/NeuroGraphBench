"""Pydantic request/response models for FBA endpoints.

Wire formats are deliberately primitive (lists / floats / strings) so the server
has no `navis` dependency. The client (`fba.client.deserialize`) is responsible
for hydrating these into rich Python objects.
"""

from typing import Literal

from pydantic import BaseModel, Field


# ---------- core wire types ----------


class MeshPayload(BaseModel):
    """A triangle mesh as parallel vertex and face arrays."""

    name: str | None = None
    vertices: list[list[float]] = Field(..., description="(N, 3) vertex coordinates.")
    faces: list[list[int]] = Field(..., description="(M, 3) triangle vertex indices.")


class SynapseCloudPayload(BaseModel):
    """(N, 3) point cloud of synapse locations."""

    locations: list[list[float]]


class RegionSpec(BaseModel):
    """A region specification matching the current `query.getRegion*` API.

    - Neuropil-only:   neuropil=<name>, volume=None
    - LPU:             neuropil=<name>, volume=<mesh>
    - Arbitrary volume: neuropil=None, volume=<mesh>
    """

    neuropil: str | None = None
    volume: MeshPayload | None = None


# ---------- request bodies ----------


Entity = Literal["neuron", "celltype"]
Layout = Literal["table", "matrix"]


class ConnectivityRequest(BaseModel):
    names: list[str] | list[list[str]] | None = None
    entity: Entity = "neuron"
    region: RegionSpec | None = None
    layout: Layout = "table"


class ArborizationRequest(BaseModel):
    names: list[str] | None = None
    entity: Entity = "neuron"
    region: RegionSpec | None = None
    return_data: bool = False


class InnervationRequest(BaseModel):
    names: list[str]
    entity: Entity = "neuron"
    regions: dict[str, MeshPayload] | None = None  # if None, server fetches all neuropils
    threshold: float = 0.0
    return_data: bool = False
    layout: Layout = "table"


class TractRequest(BaseModel):
    source_region: RegionSpec
    target_region: RegionSpec
    entity: Entity = "neuron"
    return_data: bool = False


# ---------- response payloads ----------


class TablePayload(BaseModel):
    """A pandas-DataFrame-compatible payload: column-oriented dict of lists."""

    columns: list[str]
    data: dict[str, list]
