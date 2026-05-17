"""/connectivity resource.

Endpoints:
    POST /connectivity                    — by names and/or region; entity=neuron|celltype

Known issues preserved from the lift (see cypher/connectivity.py):
- N+1 / O(N*M) execute_query pattern in `_getGlobalConnectivity`.
- celltype-pair sum aggregation can return NULL; coerced to 0 in the lift.
"""

from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver

from ..cypher import connectivity as cypher
from ..neo4j_driver import getDriver
from ..schemas import ConnectivityRequest, TablePayload

router = APIRouter(prefix="/connectivity", tags=["connectivity"])


@router.post(
    "",
    response_model=TablePayload,
    summary="Connectivity by neurons/celltypes and/or region",
)
def postConnectivity(
    request: ConnectivityRequest, driver: Driver = Depends(getDriver)
) -> TablePayload:
    if request.region is None and request.names is None:
        raise HTTPException(
            status_code=400, detail="`region` and `names` cannot both be None."
        )
    try:
        payload = cypher.getConnectivity(driver, request)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if payload is None:
        raise HTTPException(status_code=404, detail="No matching region/neuropil.")
    return TablePayload(**payload)
