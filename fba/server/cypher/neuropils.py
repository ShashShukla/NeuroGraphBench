"""Cypher queries backing the /neuropils endpoints.

Queries lifted from `FlyBrainAtlas/query.py` (`getAllNeuropilMeshes`,
`getMorphology(entity='neuropil')`, `getNeuropilSubregions`,
`getNeuronsInNeuropil`, `getCelltypesInNeuropil`); names normalized to
camelCase. Return shapes are JSON-friendly dicts/lists (no navis on the
server side).
"""

from neo4j import Driver

from ..neo4j_driver import database


def _meshFromRecord(name: str, mesh: dict) -> dict:
    """Convert a neo4j VolumeMesh node (parallel x/y/z + i/j/k) to a MeshPayload dict."""
    xs, ys, zs = mesh["x"], mesh["y"], mesh["z"]
    iis, jjs, kks = mesh["i"], mesh["j"], mesh["k"]
    return {
        "name": name,
        "vertices": [[xs[idx], ys[idx], zs[idx]] for idx in range(len(xs))],
        "faces": [[iis[idx], jjs[idx], kks[idx]] for idx in range(len(iis))],
    }


def getAllNeuropilMeshes(driver: Driver) -> dict[str, dict]:
    """Return a `{name: MeshPayload-dict}` map of every neuropil's mesh.

    Lifted from `query.getAllNeuropilMeshes`. Used internally by region-level
    endpoints to find which neuropils overlap an arbitrary volume.
    """
    records, _, _ = driver.execute_query(
        """
        MATCH (r:Neuropil)-[:HasData]->(m:VolumeMesh)
        RETURN r.name AS name, m AS mesh
        """,
        database_=database(),
    )
    return {
        record["name"]: _meshFromRecord(record["name"], record["mesh"])
        for record in records
    }


def listNeuropilNames(driver: Driver) -> list[str]:
    """Return the names of all neuropils in the database, alphabetically.

    Lighter than `getAllNeuropilMeshes` — no `:HasData->VolumeMesh` hop — so it
    can serve a frequent `GET /neuropils` listing endpoint cheaply. Callers
    that need meshes should hit `GET /neuropils/{name}` per neuropil.
    """
    records, _, _ = driver.execute_query(
        """
        MATCH (r:Neuropil)
        RETURN r.name AS name
        ORDER BY name
        """,
        database_=database(),
    )
    return [record["name"] for record in records]


def getNeuropilMesh(driver: Driver, name: str) -> dict | None:
    """Return a single neuropil's mesh as a MeshPayload-shaped dict, or None.

    Cypher pattern preserved verbatim from `query.getMorphology(entity='neuropil')`.
    """
    records, _, _ = driver.execute_query(
        """
        MATCH (:Neuropil {name: $name})-
        [:HasData]->
        (m:VolumeMesh)
        RETURN m AS mesh
        """,
        name=name,
        database_=database(),
    )
    if len(records) == 0:
        return None
    return _meshFromRecord(name, records[0]["mesh"])


def listSubregions(driver: Driver, neuropilName: str) -> list[dict] | None:
    """Return the subregion meshes of a neuropil, or None if the neuropil is missing.

    Lifted from `query.getNeuropilSubregions(return_data=True)`. Empty list
    (`[]`) means the neuropil exists but has no subregions; None means the
    neuropil itself is not in the database.
    """
    if not _neuropilExists(driver, neuropilName):
        return None
    records, _, _ = driver.execute_query(
        """
        MATCH (n:Neuropil {name:$name})-[:Owns]->(sr:Subregion)-[:HasData]->(mesh:VolumeMesh)
        RETURN sr.name AS name, mesh
        """,
        name=neuropilName,
        database_=database(),
    )
    return [_meshFromRecord(record["name"], record["mesh"]) for record in records]


def listNeuronsInNeuropil(driver: Driver, neuropilName: str) -> list[str] | None:
    """Return neuron names arborizing in a neuropil, or None if the neuropil is missing.

    Lifted from `query.getNeuronsInNeuropil`.
    """
    if not _neuropilExists(driver, neuropilName):
        return None
    records, _, _ = driver.execute_query(
        """
        MATCH (n:Neuron)-[:ArborizesIn]->(r:Neuropil {name:$name})
        RETURN n.name AS name
        ORDER BY name
        """,
        name=neuropilName,
        database_=database(),
    )
    return [record["name"] for record in records]


def listCelltypesInNeuropil(driver: Driver, neuropilName: str) -> list[str] | None:
    """Return distinct celltypes arborizing in a neuropil, or None if missing.

    Lifted from `query.getCelltypesInNeuropil`.
    """
    if not _neuropilExists(driver, neuropilName):
        return None
    records, _, _ = driver.execute_query(
        """
        MATCH (n:Neuron)-[:ArborizesIn]->(r:Neuropil {name:$name})
        RETURN DISTINCT n.celltype AS celltype
        ORDER BY celltype
        """,
        name=neuropilName,
        database_=database(),
    )
    return [record["celltype"] for record in records]


def _neuropilExists(driver: Driver, name: str) -> bool:
    records, _, _ = driver.execute_query(
        "MATCH (r:Neuropil {name:$name}) RETURN r LIMIT 1",
        name=name,
        database_=database(),
    )
    return len(records) > 0
