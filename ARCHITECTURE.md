# Architecture

This document mirrors Appendix 1 of the NGB manuscript and describes how the code is laid out to match.

## Server-side

```
NeuroArch (neo4j)  ───► FBA (FastAPI) ───► REST /
```

- **NeuroArch** is a neo4j graph database storing 3D morphology (neuropil/subneuropil meshes, neuron skeletons/meshes, synapse locations), cached per-region synaptic connectivity, retinotopic hexagonal coordinates for columnar neurons, and per-dataset attributes (neurotransmitter predictions, etc.). It is consumed, not produced, by this repo.
- **FBA** (this repo, `fba/server/`) is a FastAPI server exposing curated REST resources on top of NeuroArch. It is the canonical *data-retrieval* surface for NGB and abstracts away Cypher.

## Client-side

```
fba.client (Python)     ngb (utilities library)
       │                      │
       └─── used by ──► examples/ notebooks
```

- **`fba/client/`** — Python client that calls the FBA REST API and de-serializes responses into native Python types: `navis.Volume` / `navis.TreeNeuron` for morphology, `pandas.DataFrame` for connectivity/synapse tables, `networkx.Graph` for graph data, `numpy.ndarray` for geometric maps. The client exposes **two co-existing surfaces**: (a) **raw methods** like `client.getNeuronSynapseTable(name)` that return DataFrames / navis objects directly, and (b) an **object-relational layer** (`fba/client/models.py`) that exposes connectomic entities — `Region`, `Celltype`, `Neuron`, `Segment`, `Synapse`, `Column` — with relationships between them. Object instances hold a client reference internally and fetch lazily with attribute-level caching. Users pick whichever surface fits the task.
- **`ngb/`** — Utilities library bundling viz and analysis primitives because they are tightly coupled (e.g., the manifold-fitting Dash app *is* how topographic mapping is performed):
  - `ngb.geometry` — point-cloud volume filtering, region overlap counts, bounding-hull construction.
  - `ngb.skeleton` — geodesic neighborhoods along neuron skeletons.
  - `ngb.canvas` — plotly 3D scene wrapper for neurons / regions / synapses.
  - `ngb.circuit` — stateful circuit-builder bundling canvas + queries.
  - `ngb.apps` — Dash applications: `topographic`, `retinotopic`, and additional analyses authored as interactive surfaces.

## REST resource map

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/neuropils` | List neuropil names (optionally with meshes) |
| GET | `/neuropils/{name}` | Single neuropil mesh |
| GET | `/neuropils/{name}/subregions` | Subregion meshes |
| GET | `/neuropils/{name}/neurons` | Neurons arborizing in neuropil |
| GET | `/neuropils/{name}/celltypes` | Celltypes arborizing in neuropil |
| GET | `/neuropils/{name}/synapses` | Synapse table for neuropil (cached) |
| GET | `/neurons/{name}` | Neuron metadata |
| GET | `/neurons/{name}/skeleton` | TreeNeuron skeleton |
| GET | `/neurons/{name}/synapses` | Per-neuron synapse table (cached) |
| GET | `/neurons/{name}/partners` | Synaptic partners |
| GET | `/celltypes/{name}/neurons` | Neurons of a celltype |
| POST | `/regions/synapses` | Synapse table for an arbitrary region (mesh in body) |
| POST | `/connectivity` | Connectivity by names and/or region |
| POST | `/arborization` | Arborization counts by names and/or region |
| POST | `/innervation` | Per-region neurite counts for a circuit |
| POST | `/tracts` | Tract between source/target regions |
| GET | `/columns` | Retinotopic hexagonal column index |
| GET | `/columns/{id}/neurons` | Neurons assigned to a column |

POST is used wherever a request body carries an arbitrary `navis.Volume` mesh; named-resource queries are GET.

## Object model

The relational view exposed by `fba/client/models.py`:

```
        ┌────────────┐                         ┌────────────┐
        │  Region    │◄──── arborizesIn ─────  │  Neuron    │
        │  (volume)  │ ───── neurons    ────►  │ (skeleton) │
        └──────┬─────┘                         └──┬─────┬───┘
               │                                  │     │
       subregions│                       segmentIn│     │partners
               │                                  │     │
               ▼                                  ▼     ▼
        ┌────────────┐                         ┌────────────┐
        │  Region    │                         │  Segment   │
        └────────────┘                         └─────┬──────┘
                                                     │
                                              synapses│
                                                     ▼
        ┌────────────┐ ◄── neurons ─── ┌────────────┐ │
        │  Celltype  │                 │   Column   │ │
        └────────────┘ ─── columns ──► └────────────┘ │
                                                     ▼
                                              ┌──────────────┐
                                              │   Synapse    │
                                              │ (tables 1st) │
                                              └──────────────┘
```

- A **Segment** is the central abstraction for sub-neuronal analysis. It is constructed two ways: (1) intersecting a Neuron with a Region (regional analysis), (2) taking a geodesic neighborhood on a Neuron's skeleton (skeletal analysis).
- A **Column** is a retinotopic hex coordinate with associated neurons per columnar celltype; backed by the server-side cache (`fba/server/cache/retinotopic.py`), not neo4j.
- Most synapse-level work is done on **DataFrames** (`segment.synapses`, `region.synapseTable()`); the `Synapse` class exists for completeness but is rarely instantiated directly.

## Backend caches

Some derived data is computed once per dataset and served from a server-side cache rather than recomputed per request:

- **Retinotopic column index** (`/columns/*`) — produced by `ngb.apps.retinotopic`; persisted as parquet under a dataset-specific cache directory; loaded into memory on FastAPI startup; served by `fba.server.routers.columns`.

Stored separately from NeuroArch by design: keeps the graph database focused on raw connectome data and lets derived caches evolve without schema migrations.

## Dependency rules

- `fba/server/` may import: `neo4j`, `fastapi`, `pydantic`, `numpy`, `pandas`, **and `navis` for internal volumetric ops** (e.g., `in_volume` filtering when a request carries an arbitrary mesh). Originally we tried to exclude `navis` server-side, but every arbitrary-volume endpoint needs point-in-mesh tests, and reimplementing that is busywork. Server response *payloads* still must be primitive JSON (lists / dicts / scalars) — no `navis.Volume` or `pandas.DataFrame` instances cross the wire.
- `fba/server/` must **not** import `plotly`, `dash`, `alphashape` — those are visualization / hull-construction concerns that belong to the client / `ngb/`.
- `fba/client/` may import: `requests`, `numpy`, `pandas`, `navis`, `networkx`.
- `ngb/` may import: `fba.client`, `navis`, `numpy`, `pandas`, `plotly`, `dash`, `alphashape`, `networkx`, `scipy`.
- `ngb/` must **not** import `fba.server` — clients talk to FBA over HTTP, not in-process.

## Naming conventions

- **Function and method names:** camelCase (`getNeuronSynapseTable`, `arborizesIn`, `filterLocationsTableByVolume`). Matches the existing FBA codebase and all repo-root notebooks; rename-on-lift was explicitly rejected.
- **Class names:** PascalCase (`Region`, `Neuron`, `Segment`).
- **Local variables and parameter names:** snake_case (`neuron_name`, `region_table`, `return_data`).
- **Pydantic wire schema fields and JSON keys:** snake_case (standard JSON convention; the client de-serializer bridges to camelCase Python identifiers where appropriate).
- **pandas DataFrame column names:** snake_case (`pre_name`, `post_celltype`, `synapse_count`) — matches existing tables; not renamed.

## Algorithmic capabilities

The four morphology-analysis capabilities (regional / skeletal / topographic / retinotopic) live behind REST endpoints that cache derived data in NeuroArch; the client + `ngb` utilities expose them to users. Algorithmic detail for each follows Appendix 1 of the manuscript.
