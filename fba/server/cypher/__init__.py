"""Cypher queries used by FBA routers.

TODO: As routers are implemented, move the literal Cypher strings out of
`FlyBrainAtlas/query.py` into modules here (one module per resource) so that
schema-coupled queries are co-located. Lift verbatim during the first pass;
flag known issues with TODO comments (e.g., N+1 patterns in
`getGlobalConnectivity`, neurotransmitter aggregation in `fetchNeuronSynapseTable`).
"""
