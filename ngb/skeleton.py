"""Geodesic-neighborhood operations on neuron skeletons.

Functions (to be implemented per Appendix 1, "Skeletal analysis"):

    geodesic_distance_matrix(neuron)                 # cached per neuron in NeuroArch
    geodesic_neighborhood(neuron, center, radius)    # neurite IDs within geodesic radius
    synapses_in_neighborhood(neuron, synapses, nbhd) # filter synapses by node_id ∈ nbhd

These should be thin wrappers around `navis` traversal utilities; the heavy
caching path (per-neuron geodesic matrix and synapse→neurite map) is computed
once and stored back in NeuroArch by the dataset-load pipeline (out of scope
for this package).
"""
