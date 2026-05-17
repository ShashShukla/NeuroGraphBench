"""Arborization queries — synapse counts on neurons/celltypes per region.

Lifted from `FlyBrainAtlas/query.py` (`getArborization`,
`getGlobalArborization`, `getRegionArborization`, `getArborizationInRegion`).

Dispatch:
    names only       → global arborization (sum inputs/outputs over all neuropils)
    region only      → arborization aggregated within the region
    both             → region arborization filtered to specified names
"""

import pandas as pd
from neo4j import Driver

from ..neo4j_driver import database
from . import regions as regionsCypher
from ._tables import dataFrameToPayload, payloadToDataFrame


def getArborization(driver: Driver, request) -> dict | None:
    """Dispatch from an `ArborizationRequest`."""
    if request.region is None and request.names is not None:
        return _getGlobalArborization(driver, request)
    if request.region is not None and request.names is None:
        return _getRegionArborization(driver, request)
    if request.region is not None and request.names is not None:
        return _getArborizationInRegion(driver, request)
    return None


def _getGlobalArborization(driver: Driver, request) -> dict:
    """Lifted from `query.getGlobalArborization`. O(N) execute_query calls — TODO batch."""
    entity = request.entity
    name_col = "name" if entity == "neuron" else "celltype"
    columns = [name_col, "inputs", "outputs"]
    rows = []
    for name in request.names:
        if entity == "neuron":
            records, _, _ = driver.execute_query(
                """
                MATCH (si:SynapseSet)-[:SendsTo]->(:Neuron {name:$name}),
                      (:Neuron {name:$name})-[:SendsTo]->(so:SynapseSet)
                RETURN sum(si.N) AS inputs, sum(so.N) AS outputs
                """,
                name=name, database_=database(),
            )
        else:  # celltype
            records, _, _ = driver.execute_query(
                """
                MATCH (si:SynapseSet)-[:SendsTo]->(:Neuron {celltype:$name}),
                      (:Neuron {celltype:$name})-[:SendsTo]->(so:SynapseSet)
                RETURN sum(si.N) AS inputs, sum(so.N) AS outputs
                """,
                name=name, database_=database(),
            )
        inputs = (records[0]["inputs"] if records else 0) or 0
        outputs = (records[0]["outputs"] if records else 0) or 0
        if inputs + outputs > 0:
            rows.append([name, inputs, outputs])

    df = pd.DataFrame(rows, columns=columns)
    return dataFrameToPayload(df.reset_index(drop=True))


def _getRegionArborization(driver: Driver, request) -> dict | None:
    """Lifted from `query.getRegionArborization`. Aggregates region connectivity table.

    TODO (preserved-as-lifted naming oddity): the result columns are `inputs`
    (aggregated from `pre_name`) and `outputs` (aggregated from `post_name`).
    By neuroscience convention this is reversed — synapses where a neuron is
    *presynaptic* are its outputs, not its inputs. The lift keeps the
    original column names so existing notebooks aren't broken; flag for a
    semantics-corrected v2.
    """
    from . import connectivity as connectivityCypher

    region_response = connectivityCypher._getRegionConnectivity(driver, _connectivityRequestForRegion(request))
    if region_response is None:
        return None
    table = payloadToDataFrame(region_response)
    entity = request.entity

    if entity == "neuron":
        inputs = (
            table.groupby(["pre_name", "pre_celltype"], as_index=False)
            .agg(inputs=pd.NamedAgg(column="synapse_count", aggfunc="sum"))
            .rename(columns={"pre_name": "name", "pre_celltype": "celltype"})
        )
        outputs = (
            table.groupby(["post_name", "post_celltype"], as_index=False)
            .agg(outputs=pd.NamedAgg(column="synapse_count", aggfunc="sum"))
            .rename(columns={"post_name": "name", "post_celltype": "celltype"})
        )
        merged = inputs.merge(outputs, how="outer").fillna(0)
    elif entity == "celltype":
        inputs = (
            table.groupby(["pre_celltype"], as_index=False)
            .agg(inputs=pd.NamedAgg(column="synapse_count", aggfunc="sum"))
            .rename(columns={"pre_celltype": "celltype"})
        )
        outputs = (
            table.groupby(["post_celltype"], as_index=False)
            .agg(outputs=pd.NamedAgg(column="synapse_count", aggfunc="sum"))
            .rename(columns={"post_celltype": "celltype"})
        )
        merged = inputs.merge(outputs, how="outer").fillna(0)
    else:
        raise ValueError(f"Invalid entity {entity!r}")

    # coerce float counts (from fillna(0)) back to int for clean wire output
    for col in ("inputs", "outputs"):
        if col in merged.columns:
            merged[col] = merged[col].astype("int64")

    return dataFrameToPayload(merged.reset_index(drop=True))


def _getArborizationInRegion(driver: Driver, request) -> dict | None:
    region_response = _getRegionArborization(driver, request)
    if region_response is None:
        return None
    df = payloadToDataFrame(region_response)
    name_col = "name" if request.entity == "neuron" else "celltype"
    df = df[df[name_col].isin(request.names)].reset_index(drop=True)
    return dataFrameToPayload(df)


def _connectivityRequestForRegion(arborizationRequest):
    """Build a minimal ConnectivityRequest for the region-connectivity sub-query."""
    from ..schemas import ConnectivityRequest

    return ConnectivityRequest(
        names=None,
        entity="neuron",  # region table is always neuron-level; we aggregate after
        region=arborizationRequest.region,
        layout="table",
    )
