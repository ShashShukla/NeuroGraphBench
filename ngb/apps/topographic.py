"""Topographic-mapping Dash app.

Implements the interactive workflow described in Appendix 1 ("Topographic
mapping"):

1. Visualize N neuron skeletons alongside a parameterized projection manifold.
2. UI controls translate / rotate / resize / curve the manifold.
3. On manifold change, recompute per-neuron intersection locations (centroids
   when multiple intersections exist) and project into manifold-intrinsic 2D
   coordinates.
4. Return the (neuron_name -> (u, v)) mapping.

Public surface: `make_app(client, neuron_names: list[str]) -> dash.Dash`.
"""
