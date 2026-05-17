"""Geometric primitives for volumetric operations on point clouds and meshes.

Functions (to be ported verbatim from FlyBrainAtlas/utils.py):

    filterLocationsTableByVolume(table, volume)
    cloudRegionCounts(point_cloud, regions)
    volumeOverlaps(volume, regions)
    constructSynapsesHull(locations, name, alpha)
    neuronConnectorsTable(neuron_table)

Naming convention: camelCase for function names (matches existing FBA code and
all repo-root notebooks), snake_case for local variables and parameters.
"""
