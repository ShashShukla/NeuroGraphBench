"""/innervation resource.

Endpoints:
    POST /innervation                     — neurite counts per region for a circuit.
                                            `regions` omitted → defaults to all neuropils.
"""

from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver

from ..cypher import innervation as cypher
from ..neo4j_driver import getDriver
from ..schemas import InnervationRequest, TablePayload

router = APIRouter(prefix="/innervation", tags=["innervation"])


@router.post(
    "",
    response_model=TablePayload,
    summary="Neurite counts per region for a circuit of neurons/celltypes",
)
def postInnervation(
    request: InnervationRequest, driver: Driver = Depends(getDriver)
) -> TablePayload:
    try:
        payload = cypher.getInnervation(driver, request)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if payload is None:
        raise HTTPException(status_code=404, detail="No regions to query.")
    return TablePayload(**payload)
