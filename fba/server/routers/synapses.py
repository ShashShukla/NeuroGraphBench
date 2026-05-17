"""Synapse point-cloud resources.

Endpoints (stubs):
    GET  /synapses?pre=<name>&post=<name>          — neuron-to-neuron synapse cloud
    GET  /synapses?pre_celltype=...&post_celltype=...  — celltype-to-celltype synapse cloud

Per-neuron and per-neuropil annotated synapse *tables* live on /neurons/{name}/synapses
and /neuropils/{name}/synapses respectively. This router is for raw point clouds.

TODO: lift Cypher from FlyBrainAtlas/query.py:
    getMorphology(entity='synapse_NeuronToNeuron'),
    getMorphology(entity='synapse_CelltypeToCelltype'),
    getMorphology(entity='synapse_Neuron' / 'synapse_Celltype').
"""

from fastapi import APIRouter

router = APIRouter(prefix="/synapses", tags=["synapses"])
