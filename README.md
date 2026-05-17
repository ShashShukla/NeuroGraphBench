# NeuroGraphBench

> An open-source Python toolset for constructing geometrically grounded, segment-level representations of neural circuits from connectomic datasets.

**Status:** pre-1.0 / alpha (`0.1.0-dev`). Regional-analysis capability is implemented end-to-end with test coverage; skeletal, topographic, and retinotopic capabilities are partially stubbed. APIs are expected to change.

NeuroGraphBench (NGB) accompanies the manuscript *"NeuroGraphBench: From connectomic structure to an executable model of collision detection in Drosophila"* (Lazar, Shukla, Zhou). It provides the geometry- and connectivity-aware primitives used in the paper's LPLC2 → PVLP011 → Giant Fiber circuit analysis, packaged as a reusable toolset.

NGB has two installable subpackages:

- **`fba`** — *FlyBrainAtlas*. A FastAPI server exposing a NeuroArch (neo4j) connectome database as curated REST resources, plus a Python client that wraps the API and de-serializes responses into `navis` / `pandas` / `numpy` objects.
- **`ngb`** — utilities library. Geometric primitives (point-cloud filtering, geodesic neighborhoods, bounding-hull construction) and interactive `plotly` / `Dash` apps for 3D visualization, segment specification, and manifold-fitting analyses.

## Capabilities

The four core morphology-analysis capabilities mirror those described in Section 2.2 of the manuscript:

| Capability | What it does | Status (`0.1.0-dev`) |
| --- | --- | --- |
| **Regional analysis** | Segment neuronal arbors by neuropil or layer; query region-restricted connectivity, arborization, and innervation. | ✅ Implemented end-to-end + reference notebook |
| **Skeletal analysis** | Define local geodesic neighborhoods along neuron skeletons. | 🚧 Stubs in place (`ngb/skeleton.py`); algorithm + cache TBD |
| **Topographic mapping** | Project 3D morphology onto 2D manifolds via an interactive Dash UI. | 🚧 App skeleton in `ngb/apps/topographic.py` |
| **Retinotopic mapping** | Propagate hexagonal columnar coordinates from the retina to downstream visual pathways. | 🚧 Server cache stubs + app skeleton |

## Architecture

```
              ┌──────────────────────┐
              │  NeuroArch (neo4j)   │
              └──────────┬───────────┘
                         │ Cypher
              ┌──────────▼───────────┐
              │  fba.server (FastAPI)│   curated REST resources
              └──────────┬───────────┘   ← navis allowed for in-volume ops
                         │ HTTP / JSON
              ┌──────────▼───────────┐
              │  fba.client (Python) │   raw methods + Region/Neuron/... objects
              └──┬───────────────┬───┘
                 │               │
        ┌────────▼────┐    ┌─────▼──────┐
        │  ngb        │    │  examples/ │   reference notebooks
        │  (viz +     │    └────────────┘
        │   geometry) │
        └─────────────┘
```

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full server/client decomposition, the REST resource map, dependency rules, and the relational diagram of the object model.

## Installation

Requires Python 3.10+. Tested with Python 3.10 in a dedicated `ngb` conda env.

```bash
# 1. Create env
conda create -n ngb -y python=3.10

# 2. Install binary-heavy deps from conda-forge (avoids h5py source build)
conda install -n ngb -y -c conda-forge \
    h5py numpy pandas scipy networkx pytest httpx requests plotly seaborn

# 3. Install everything else, including the editable repo
conda run -n ngb pip install -e .
```

**Why the conda step?** `navis` pulls in `h5py`, which on hosts with HDF5 < 1.10.7 fails the wheel build. Installing `h5py` from conda-forge first ships a bundled HDF5 and avoids the source build. If your system has a recent HDF5, `pip install -e .` alone works.

A separate NeuroArch (neo4j) instance loaded with a fly-brain dataset is required to use the data-retrieval surface. See the manuscript and the [NeuroArch](https://github.com/fruitflybrain/neuroarch) project for setup. For now, FBA's connection settings are hardcoded in `fba/server/neo4j_driver.py` and will be moved to config before public release.

## Quickstart

Start the FBA server:

```bash
uvicorn fba.server.app:app --reload
# server now listening at http://localhost:8000
```

Smallest end-to-end check from Python:

```python
from fba.client import Client

fba = Client("http://localhost:8000")
print(fba.listNeuropils()[:5])               # ['AL', 'AL-DA1', 'AL-DC1', ...]

lop = fba.neuropil("LOP")
print(lop.mesh)                              # navis.Volume(n=…)
print(len(lop.neurons), "neurons in LOP")
```

For the complete walkthrough — regional connectivity, per-layer arborization, innervation matrices, and the LPLC2-in-LOP example from the manuscript — open [`examples/01-regional-analysis.ipynb`](./examples/01-regional-analysis.ipynb).

## Repository layout

```
neurographbench/
├── README.md                   # you are here
├── ARCHITECTURE.md             # canonical architecture spec (mirrors manuscript Appendix 1)
├── CHANGELOG.md                # release notes
├── LICENSE                     # MIT
├── pyproject.toml              # build + deps + pytest config
├── fba/
│   ├── server/                 # FastAPI app exposing NeuroArch
│   │   ├── app.py              # FastAPI entry point
│   │   ├── neo4j_driver.py     # driver singleton (config TODO)
│   │   ├── schemas.py          # Pydantic wire types
│   │   ├── cache/              # server-side derived-data cache (retinotopic columns, etc.)
│   │   ├── cypher/             # Cypher queries by resource
│   │   └── routers/            # FastAPI routers, one module per resource
│   └── client/
│       ├── http.py             # Client (sync requests-based)
│       ├── deserialize.py      # wire → navis / pandas
│       ├── serialize.py        # navis / pandas → wire
│       └── models.py           # Region (and forthcoming Neuron/Segment/...)
├── ngb/
│   ├── geometry.py             # point-in-volume, hull construction, overlap counts
│   ├── skeleton.py             # geodesic neighborhoods (stub)
│   ├── canvas.py               # plotly 3D scene wrapper (stub)
│   ├── circuit.py              # stateful circuit builder (stub)
│   └── apps/                   # Dash applications (topographic, retinotopic) (stubs)
├── examples/                   # one notebook per capability
│   └── 01-regional-analysis.ipynb
├── docs/                       # user guide (entry point: docs/README.md)
└── tests/                      # pytest suite (run with `pytest` from repo root)
```

## Development

```bash
# run the test suite
conda run -n ngb pytest

# launch the server with auto-reload
conda run -n ngb uvicorn fba.server.app:app --reload

# build the API reference (interactive)
# http://localhost:8000/docs   ← Swagger UI (generated by FastAPI)
# http://localhost:8000/redoc  ← ReDoc
```

The test suite mocks the neo4j driver via `app.dependency_overrides`, so no live database is required to run `pytest`.

## Status & roadmap

`0.1.0-dev` (this release):
- Regional analysis end-to-end (server + client + object model + notebook + tests).

Next planned slices, in order:
1. `Neuron` and `Segment` object classes (currently `region.neurons` returns strings).
2. Skeletal-analysis capability + `02-skeletal-analysis.ipynb`.
3. `ngb.canvas.Canvas` and `ngb.circuit.Circuit` implementations.
4. Topographic-mapping Dash app + `03-topographic-mapping.ipynb`.
5. Retinotopic-mapping cache pipeline + `04-retinotopic-mapping.ipynb`.

See [`CHANGELOG.md`](./CHANGELOG.md) for what landed in each release.

## Citation

If you use NGB in academic work, please cite the manuscript:

> Lazar, A. A., Shukla, S., & Zhou, Y. (2026). *NeuroGraphBench: From connectomic structure to an executable model of collision detection in Drosophila.*

## License

MIT. See [`LICENSE`](./LICENSE). © 2026 the NeuroGraphBench authors.
