"""/regions resources.

Endpoints:
    POST /regions/synapses                — synapse table for an arbitrary region (mesh in body)

POST because the region spec can carry a `navis.Volume` mesh that does not fit
cleanly in a URL.
"""

from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver

from ..cypher import regions as cypher
from ..neo4j_driver import getDriver
from ..schemas import RegionSpec, TablePayload

router = APIRouter(prefix="/regions", tags=["regions"])


@router.post(
    "/synapses",
    response_model=TablePayload,
    summary="Get the synapse table for an arbitrary region (neuropil and/or volume)",
)
def getRegionSynapses(
    region: RegionSpec, driver: Driver = Depends(getDriver)
) -> TablePayload:
    if region.neuropil is None and region.volume is None:
        raise HTTPException(
            status_code=400, detail="Region requires `neuropil` or `volume`."
        )
    payload = cypher.getRegionSynapseTable(driver, region)
    if payload is None:
        raise HTTPException(
            status_code=404, detail=f"Neuropil {region.neuropil!r} not found."
        )
    return TablePayload(**payload)
