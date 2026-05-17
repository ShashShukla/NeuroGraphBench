"""FastAPI application entry point.

Wires neo4j driver lifespan and includes resource routers. Run with::

    uvicorn fba.server.app:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .neo4j_driver import closeDriver, getDriver
from .routers import (
    arborization,
    celltypes,
    columns,
    connectivity,
    innervation,
    neurons,
    neuropils,
    regions,
    synapses,
    tracts,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    getDriver()
    try:
        yield
    finally:
        closeDriver()


app = FastAPI(
    title="FlyBrainAtlas",
    version="0.1.0.dev0",
    description="REST API for segment-level connectomic queries over NeuroArch (neo4j).",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(neuropils.router)
app.include_router(neurons.router)
app.include_router(celltypes.router)
app.include_router(synapses.router)
app.include_router(regions.router)
app.include_router(connectivity.router)
app.include_router(arborization.router)
app.include_router(innervation.router)
app.include_router(tracts.router)
app.include_router(columns.router)
