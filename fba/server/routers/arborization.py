"""/arborization resource.

Endpoints:
    POST /arborization                    — by names and/or region; entity=neuron|celltype
"""

from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver

from ..cypher import arborization as cypher
from ..neo4j_driver import getDriver
from ..schemas import ArborizationRequest, TablePayload

router = APIRouter(prefix="/arborization", tags=["arborization"])


@router.post(
    "",
    response_model=TablePayload,
    summary="Arborization counts by neurons/celltypes and/or region",
)
def postArborization(
    request: ArborizationRequest, driver: Driver = Depends(getDriver)
) -> TablePayload:
    if request.region is None and request.names is None:
        raise HTTPException(
            status_code=400, detail="`region` and `names` cannot both be None."
        )
    try:
        payload = cypher.getArborization(driver, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if payload is None:
        raise HTTPException(status_code=404, detail="No matching region/neuropil.")
    return TablePayload(**payload)
