# Changelog

All notable changes to NeuroGraphBench. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows [SemVer](https://semver.org).

## [0.1.0-dev] — 2026-05

First cut of the release repo. Regional-analysis capability is implemented end-to-end; remaining capabilities are stubbed.

### Added

**Architecture & layout**
- Monorepo skeleton at `claude/neurographbench/` with `fba` (server + client) and `ngb` (utilities) subpackages.
- `ARCHITECTURE.md` mirroring Appendix 1 of the manuscript: REST resource map, server/client decomposition, dependency rules, object-relational diagram, naming conventions.
- `pyproject.toml` with single `neurographbench` distribution exposing both subpackages, dev extras, and pytest config.

**`fba` — FlyBrainAtlas (FastAPI server + Python client)**
- Server entry point at `fba.server.app` with lifespan-managed neo4j driver (`fba.server.neo4j_driver`) exposed as a FastAPI dependency.
- Implemented REST endpoints:
  - `GET  /neuropils` — list neuropil names.
  - `GET  /neuropils/{name}` — neuropil mesh.
  - `GET  /neuropils/{name}/subregions` — subregion meshes.
  - `GET  /neuropils/{name}/neurons` — neurons arborizing in neuropil.
  - `GET  /neuropils/{name}/celltypes` — celltypes arborizing in neuropil.
  - `GET  /neuropils/{name}/synapses` — cached neuropil synapse table.
  - `POST /regions/synapses` — synapse table for an arbitrary region (neuropil and/or volume).
  - `POST /connectivity` — connectivity by names and/or region.
  - `POST /arborization` — per-name pre/post arborization counts.
  - `POST /innervation` — per-region neurite counts for a circuit.
  - `GET  /health` — liveness check.
- Cypher queries lifted from `FlyBrainAtlas/query.py` and reorganized by resource under `fba/server/cypher/`. Naming normalized to camelCase per project convention; mesh node decoding centralized in `_meshFromRecord`.
- `navis.in_volume` permitted server-side for arbitrary-region filtering; responses remain primitive JSON.
- Pydantic wire schemas (`MeshPayload`, `SynapseCloudPayload`, `RegionSpec`, `TablePayload`, and request bodies).
- Server-side derived-data cache scaffolding for retinotopic columns (`fba/server/cache/`).

**`fba.client` — Python client**
- `Client` class with `_get` / `_post` transport over `requests.Session`.
- Raw method API mirroring every implemented endpoint (`listNeuropils`, `getNeuropilMesh`, `listSubregions`, `getNeuropilSynapseTable`, `getRegionSynapseTable`, `getConnectivity`, `getArborization`, `getInnervation`, …).
- Response hydration: `meshFromPayload` → `navis.Volume`, `meshListFromPayload`, `tableFromPayload` → `pandas.DataFrame` (column-order preserving).
- Request serialization: `meshToPayload`, `regionToSpec` (lazy — doesn't trigger mesh fetch when serializing a neuropil-only Region).
- Object model in `fba.client.models`: `Region` class with `name`, lazy `mesh`, `subregions`, `neurons`, `celltypes` properties and `synapseTable()`, `connectivity()`, `arborization()` methods. Dispatches between neuropil, volume, and LPU spec automatically.
- Object factories on the client: `client.neuropil(name)`, `client.region(neuropil=..., volume=...)`.

**`ngb` — utilities library**
- Module stubs for `geometry`, `skeleton`, `canvas`, `circuit`, and the `apps.topographic` / `apps.retinotopic` Dash applications.
- Function signatures and docstrings describe the verbatim lift from `FlyBrainAtlas/utils.py` and the algorithmic procedures in Appendix 1 of the manuscript.

**Examples**
- `examples/01-regional-analysis.ipynb` — 27-cell reference notebook walking through the LPLC2 → LOP example: list neuropils, load LOP, visualize layers, filter to LPLC2, regional synapse table, connectivity heatmap, per-layer arborization, innervation matrix. Ties findings back to the manuscript.

**Tests**
- 57 pytest tests across `tests/test_neuropils.py`, `tests/test_regions.py`, `tests/test_regional_analysis.py`, `tests/test_client.py`.
- Mocked `neo4j.Driver` via `app.dependency_overrides[getDriver]`; FastAPI `TestClient` fixtures in `tests/conftest.py`.

**Documentation**
- `README.md` with quickstart, install (incl. the `h5py`-via-conda workaround), repo layout, roadmap, citation.
- `docs/README.md` — single-page user guide.
- `examples/README.md` — capability-to-notebook map plus drafting principles.
- `LICENSE` (MIT) and `.gitignore`.

### Known limitations (TODOs preserved in code)

- `fba.server.cypher.connectivity._getGlobalConnectivity` runs N+1 / O(N·M) `execute_query` calls; needs batching with `UNWIND`.
- `fba.server.cypher.innervation` iterates `navis.in_volume` per (neuron, region); O(N·M).
- `_getRegionArborization` column naming (`inputs` aggregated from `pre_name`, `outputs` from `post_name`) is reversed from the usual neuroscience convention. Preserved as-lifted; flagged in the cypher docstring.
- Database connection settings hardcoded in `fba.server.neo4j_driver`; factor out into config.
- Retinotopic-column cache loaders/producers not yet wired (server stubs in `fba/server/cache/retinotopic.py`).

### Environment

- Tested on Python 3.10.20 in a dedicated conda env (`ngb`) with `fastapi 0.136`, `pydantic 2.13`, `neo4j 6.2`, `navis 1.11`, `pytest 9.0`.
- Existing FBA / notebook work continues to run in the legacy `ffbo` env (Python 3.9, `pydantic 1.7`); the two envs are kept isolated by design.
