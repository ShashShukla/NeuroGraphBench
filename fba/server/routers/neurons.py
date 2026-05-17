"""/neurons resources.

Endpoints (stubs):
    GET  /neurons/{name}                  — neuron metadata
    GET  /neurons/{name}/skeleton         — TreeNeuron skeleton (swc-like payload)
    GET  /neurons/{name}/synapses         — cached synapse table
    GET  /neurons/{name}/partners         — synaptic partners (optionally region-filtered)

TODO: lift Cypher from FlyBrainAtlas/query.py:
    getMorphology(entity='neuron'), getNeuronSynapseTable / fetchNeuronSynapseTable,
    getSynapticPartners(entity='neuron').
"""

from fastapi import APIRouter

router = APIRouter(prefix="/neurons", tags=["neurons"])
