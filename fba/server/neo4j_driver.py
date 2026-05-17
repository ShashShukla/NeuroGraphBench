"""neo4j driver singleton.

Exposes `getDriver` as both a regular accessor and a FastAPI dependency
(consumed via `Depends(getDriver)` in routers). Tests override the dependency
through `app.dependency_overrides[getDriver]` to inject a mock driver.

TODO: factor out hardcoded URI/credentials into config (yaml/toml + env-var
override) before public release. Currently hardcoded to localhost so that the
first-slice port can boot without a config-loading dependency.
"""

from neo4j import Driver, GraphDatabase

_DRIVER: Driver | None = None

# TODO: replace with config-loaded values.
_NEO4J_URI = "bolt://localhost:7687"
_NEO4J_USER = "neo4j"
_NEO4J_PASSWORD = "neo4j"
_NEO4J_DATABASE = "neo4j"


def getDriver() -> Driver:
    """Return the neo4j driver singleton; used as a FastAPI dependency."""
    global _DRIVER
    if _DRIVER is None:
        _DRIVER = GraphDatabase.driver(_NEO4J_URI, auth=(_NEO4J_USER, _NEO4J_PASSWORD))
    return _DRIVER


def closeDriver() -> None:
    global _DRIVER
    if _DRIVER is not None:
        _DRIVER.close()
        _DRIVER = None


def database() -> str:
    return _NEO4J_DATABASE
