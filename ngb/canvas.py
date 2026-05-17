"""plotly 3D scene wrapper for neurons / regions / synapses.

To be lifted from FlyBrainAtlas/visualize.py::Canvas. Changes from the original:
- Takes a `fba.client.Client` instead of a raw neo4j driver.
- `add_trace(trace_name, trace_type, data=None, ...)` keeps the same surface;
  when `data is None`, fetches via the client instead of `query.getMorphology`.

Also keeps the small `show_matrix` helper (was `showMatrix`).
"""
