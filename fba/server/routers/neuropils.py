"""/neuropils resources."""

from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver

from ..cypher import neuropils as cypher
from ..cypher import synapses as synapseCypher
from ..neo4j_driver import getDriver
from ..schemas import MeshPayload, TablePayload

router = APIRouter(prefix="/neuropils", tags=["neuropils"])


def _requireNeuropil(value, name: str):
    if value is None:
        raise HTTPException(status_code=404, detail=f"Neuropil {name!r} not found.")
    return value


@router.get("", response_model=list[str], summary="List all neuropil names")
def listNeuropils(driver: Driver = Depends(getDriver)) -> list[str]:
    return cypher.listNeuropilNames(driver)


@router.get("/{name}", response_model=MeshPayload, summary="Get a neuropil mesh by name")
def getNeuropil(name: str, driver: Driver = Depends(getDriver)) -> MeshPayload:
    return MeshPayload(**_requireNeuropil(cypher.getNeuropilMesh(driver, name), name))


@router.get(
    "/{name}/subregions",
    response_model=list[MeshPayload],
    summary="List subregion meshes of a neuropil",
)
def listSubregions(name: str, driver: Driver = Depends(getDriver)) -> list[MeshPayload]:
    payloads = _requireNeuropil(cypher.listSubregions(driver, name), name)
    return [MeshPayload(**payload) for payload in payloads]


@router.get(
    "/{name}/neurons",
    response_model=list[str],
    summary="List neurons arborizing in a neuropil",
)
def listNeuronsInNeuropil(name: str, driver: Driver = Depends(getDriver)) -> list[str]:
    return _requireNeuropil(cypher.listNeuronsInNeuropil(driver, name), name)


@router.get(
    "/{name}/celltypes",
    response_model=list[str],
    summary="List celltypes arborizing in a neuropil",
)
def listCelltypesInNeuropil(name: str, driver: Driver = Depends(getDriver)) -> list[str]:
    return _requireNeuropil(cypher.listCelltypesInNeuropil(driver, name), name)


@router.get(
    "/{name}/synapses",
    response_model=TablePayload,
    summary="Get the (cached) synapse table for a neuropil",
)
def getNeuropilSynapses(name: str, driver: Driver = Depends(getDriver)) -> TablePayload:
    payload = _requireNeuropil(synapseCypher.getNeuropilSynapseTable(driver, name), name)
    return TablePayload(**payload)
