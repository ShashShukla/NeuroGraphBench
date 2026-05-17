"""Retinotopic column cache.

Persists and serves the derived data produced by the retinotopic-mapping
algorithm (Appendix 1, "Retinotopic mapping"):

1. `column_index` — global hexagonal grid: for each column id, its hex (q, r)
   coordinate and a representative 3D centroid. Stored as parquet.
2. `neuron_columns` — per-celltype map from neuron name to column id. One
   parquet per columnar celltype (L1, L2, Mi1, T4a/b/c/d, ...).

Loaded on FastAPI server startup (see `fba.server.app` lifespan) and served
from in-memory DataFrames by the `/columns` router.

Public surface to implement:
    loadColumnIndex()              -> pandas.DataFrame
    loadNeuronColumns(celltype)    -> pandas.DataFrame
    columnsFor(neuron_name)        -> int | None
    neuronsAt(column_id, celltype) -> list[str]

The *computation* of the column index from raw L1/L2 topography lives in
`ngb.apps.retinotopic` (client-side Dash app); the server persists and serves
the resulting tables. This split keeps the heavy interactive UI client-side
while making the resulting maps queryable by everyone.
"""
