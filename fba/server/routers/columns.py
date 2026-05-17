"""/columns resources — retinotopic hexagonal coordinate index.

Endpoints (stubs):
    GET  /columns                         — global hexagonal column index
    GET  /columns/{id}/neurons            — neurons assigned to a column
                                            (filter by celltype via query param)
    GET  /columns/celltypes/{name}        — full neuron→column map for a celltype
    GET  /neurons/{name}/columnarPartners — columnar inputs to a non-columnar neuron

Backing storage: server-side derived-data cache, not NeuroArch. See
`fba.server.cache.retinotopic`. The cache is hydrated on FastAPI startup and
served from in-memory DataFrames. The user explicitly chose this over storing
columns in neo4j to keep the database focused on raw connectome data.

The cache is *produced* by the Dash retinotopic-mapping app (`ngb.apps.retinotopic`)
and uploaded via a separate admin path (to be designed). Users *query* via the
endpoints above.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/columns", tags=["columns"])
