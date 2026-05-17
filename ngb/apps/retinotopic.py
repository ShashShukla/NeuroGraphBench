"""Retinotopic-mapping Dash app.

Implements the workflow described in Appendix 1 ("Retinotopic mapping"):

1. Topographic-map L1 neurons in the lamina to obtain projected centroids.
2. For each L1, identify 6 nearest neighbors in projected space.
3. Stitch local hexagonal neighborhoods into a global column index.
4. Propagate the column index to L2 (one-to-one), and to downstream columnar
   celltypes via their L1/L2 partners.

Public surface: `make_app(client) -> dash.Dash`. Persists the resulting column
index back to NeuroArch via FBA cache endpoints (to be designed alongside the
example notebook).
"""
