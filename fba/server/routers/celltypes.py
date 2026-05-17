"""/celltypes resources.

Endpoints (stubs):
    GET  /celltypes/{name}/neurons        — neuron names of a celltype

TODO: lift Cypher from FlyBrainAtlas/query.py:
    getCelltypeNeuronNames, getSynapticPartners(entity='celltype').
"""

from fastapi import APIRouter

router = APIRouter(prefix="/celltypes", tags=["celltypes"])
