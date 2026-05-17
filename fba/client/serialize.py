"""Client-side request serialization: native Python objects → wire payloads.

Mirror of `fba.client.deserialize`. Used when the client needs to send a
mesh or region spec to the server (e.g., `POST /regions/synapses`).
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import navis

    from .models import Region


def meshToPayload(volume: "navis.Volume") -> dict[str, Any]:
    """Serialize a `navis.Volume` to a MeshPayload-shaped dict."""
    return {
        "name": volume.name,
        "vertices": volume.vertices.tolist(),
        "faces": volume.faces.tolist(),
    }


def regionToSpec(region: "Region") -> dict[str, Any]:
    """Serialize a `Region` to a RegionSpec-shaped dict.

    Reads through `Region`'s private fields (`_neuropil`, `_mesh`) directly so
    no mesh fetch is triggered just to serialize a neuropil-only Region.
    """
    spec: dict[str, Any] = {}
    if region._neuropil is not None:
        spec["neuropil"] = region._neuropil
    if region._mesh is not None:
        spec["volume"] = meshToPayload(region._mesh)
    return spec
