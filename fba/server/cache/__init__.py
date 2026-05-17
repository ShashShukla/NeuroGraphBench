"""Server-side derived-data cache.

Some FBA endpoints serve data that is precomputed once per dataset and held
server-side rather than recomputed on every request — most notably the
retinotopic hexagonal column index and the per-celltype neuron→column maps
(see `fba.server.cache.retinotopic` and the `/columns` router).

This package owns:
- Cache file formats (parquet / json) and on-disk layout.
- Startup loaders that hydrate the cache into memory.
- Update procedures (server-side computation that produces the cache from a
  fresh dataset).

The cache is **dataset-specific** and is not checked into the release repo;
cache files are produced by a dataset-load pipeline and pointed at via config.

TODO: factor the cache root path into the config refactor (deferred). For now
the loader uses a hardcoded relative path.
"""
