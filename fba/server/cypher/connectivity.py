"""Connectivity queries.

Lifted from `FlyBrainAtlas/query.py` (`getConnectivity`,
`getGlobalConnectivity`, `getRegionConnectivity`, `getConnectivityInRegion`).
The dispatch matches the original behavior:

    names only       → global connectivity
    region only      → region-aggregated connectivity
    both             → region connectivity filtered to names

Known issues preserved with TODOs (not fixed in this lift):
- `_getGlobalConnectivity` runs O(N*M) `execute_query` calls when N pre and
  M post partners are supplied. Should batch with `UNWIND $names AS name ...`.
- When the celltype-pair aggregation returns NULL (no synapses), upstream
  code referenced `records[0]['synapse_count']` without coalescing. Coerce
  None → 0 here so the response is well-typed.
"""

import pandas as pd
from neo4j import Driver

from ..neo4j_driver import database
from . import regions as regionsCypher
from ._tables import dataFrameToPayload, payloadToDataFrame


def getConnectivity(driver: Driver, request) -> dict | None:
    """Dispatch from a `ConnectivityRequest` to the appropriate sub-query."""
    if request.region is None and request.names is not None:
        return _getGlobalConnectivity(driver, request)
    if request.region is not None and request.names is None:
        return _getRegionConnectivity(driver, request)
    if request.region is not None and request.names is not None:
        return _getConnectivityInRegion(driver, request)
    return None


# --- helpers ---


def _parsePrePost(names):
    """Mirror `query.getGlobalConnectivity`'s name parsing — flat or [[pre],[post]]."""
    if isinstance(names, list) and len(names) == 2 and all(isinstance(n, list) for n in names):
        return list(names[0]), list(names[1])
    if isinstance(names, list) and all(isinstance(n, str) for n in names):
        return list(names), list(names)
    raise ValueError("Invalid format for neuron/celltype names.")


def _hasNeurotransmitterData(driver: Driver) -> bool:
    records, _, _ = driver.execute_query(
        "MATCH (n:Neuron) RETURN n AS neuron LIMIT 1",
        database_=database(),
    )
    return bool(records) and "neurotransmitters" in records[0]["neuron"]


def _pivotAsMatrix(df: pd.DataFrame, pre_column: str, post_column: str) -> pd.DataFrame:
    return pd.pivot_table(
        df,
        index=pre_column,
        columns=post_column,
        values="synapse_count",
        fill_value=0,
    )


# --- (1) global connectivity ---


def _getGlobalConnectivity(driver: Driver, request) -> dict:
    """Lifted from `query.getGlobalConnectivity`. See module docstring for TODOs."""
    pre_names, post_names = _parsePrePost(request.names)
    entity = request.entity
    has_nts = _hasNeurotransmitterData(driver)

    if entity == "neuron":
        columns = ["pre_name", "post_name", "pre_celltype", "post_celltype", "synapse_count"]
        if has_nts:
            columns.append("neurotransmitters")
        rows = []
        for pre_name in pre_names:
            records, _, _ = driver.execute_query(
                "MATCH (n:Neuron {name:$name}) RETURN n AS neuron",
                name=pre_name, database_=database(),
            )
            if len(records) == 0:
                raise LookupError(f"No neuron {pre_name!r} in database")
            pre_neuron = records[0]["neuron"]
            pre_celltype = pre_neuron["celltype"]
            nts = ",".join(pre_neuron["neurotransmitters"]) if has_nts else None

            for post_name in post_names:
                if pre_name == post_name:  # skip autapses
                    continue
                records, _, _ = driver.execute_query(
                    "MATCH (n:Neuron {name:$name}) RETURN n AS neuron",
                    name=post_name, database_=database(),
                )
                if len(records) == 0:
                    raise LookupError(f"No neuron {post_name!r} in database")
                post_celltype = records[0]["neuron"]["celltype"]

                # TODO: batch with UNWIND — current O(N*M) is wasteful for large circuits.
                records, _, _ = driver.execute_query(
                    """
                    MATCH (:Neuron {name:$pre_name})-
                    [:SendsTo]->
                    (ss:SynapseSet)-
                    [:SendsTo]->
                    (:Neuron {name:$post_name})
                    RETURN ss.N AS synapse_count
                    """,
                    pre_name=pre_name, post_name=post_name, database_=database(),
                )
                synapse_count = records[0]["synapse_count"] if records else 0

                row = [pre_name, post_name, pre_celltype, post_celltype, synapse_count]
                if has_nts:
                    row.append(nts)
                rows.append(row)

    elif entity == "celltype":
        columns = ["pre_celltype", "post_celltype", "synapse_count"]
        if has_nts:
            columns.append("neurotransmitters")
        rows = []
        for pre_celltype in pre_names:
            nts = None
            if has_nts:
                records, _, _ = driver.execute_query(
                    "MATCH (n:Neuron {celltype:$name}) RETURN n.neurotransmitters AS nts LIMIT 1",
                    name=pre_celltype, database_=database(),
                )
                if len(records) == 0:
                    raise LookupError(f"No neuron of celltype {pre_celltype!r} in database")
                nts = ",".join(records[0]["nts"] or [])

            for post_celltype in post_names:
                records, _, _ = driver.execute_query(
                    """
                    MATCH (:Neuron {celltype:$pre_name})-
                    [:SendsTo]->
                    (ss:SynapseSet)-
                    [:SendsTo]->
                    (:Neuron {celltype:$post_name})
                    RETURN sum(ss.N) AS synapse_count
                    """,
                    pre_name=pre_celltype, post_name=post_celltype, database_=database(),
                )
                # `sum(...)` returns a single row with NULL when no match — coerce to 0.
                synapse_count = (records[0]["synapse_count"] if records else 0) or 0
                row = [pre_celltype, post_celltype, synapse_count]
                if has_nts:
                    row.append(nts)
                rows.append(row)

    else:
        raise ValueError(f"Invalid entity {entity!r}")

    df = pd.DataFrame(rows, columns=columns)
    return _formatConnectivityResponse(df, entity, request.layout)


# --- (2) region connectivity ---


def _getRegionConnectivity(driver: Driver, request) -> dict | None:
    """Region-aggregated connectivity from the region's synapse table."""
    region_payload = regionsCypher.getRegionSynapseTable(driver, request.region)
    if region_payload is None:
        return None
    region_df = payloadToDataFrame(region_payload)

    # group + aggregate by neuron partners (table form)
    grouping = ["pre_name", "post_name", "pre_celltype", "post_celltype"]
    if "neurotransmitters" in region_df.columns:
        grouping.append("neurotransmitters")
    # `query.getRegionConnectivity` uses `.count()` after assigning synapse_count=1;
    # equivalent and faster: groupby + size.
    table = (
        region_df.drop(columns=["x", "y", "z"])
        .groupby(grouping, as_index=False)
        .size()
        .rename(columns={"size": "synapse_count"})
    )

    if request.entity == "neuron":
        return _formatConnectivityResponse(table, "neuron", request.layout)

    if request.entity == "celltype":
        celltype_grouping = ["pre_celltype", "post_celltype"]
        if "neurotransmitters" in table.columns:
            celltype_grouping.append("neurotransmitters")
        table = (
            table.drop(columns=["pre_name", "post_name"])
            .groupby(celltype_grouping, as_index=False)
            .sum(numeric_only=True)
        )
        return _formatConnectivityResponse(table, "celltype", request.layout)

    raise ValueError(f"Invalid entity {request.entity!r}")


# --- (3) connectivity within a region, restricted to specified names ---


def _getConnectivityInRegion(driver: Driver, request) -> dict | None:
    pre_names, post_names = _parsePrePost(request.names)
    entity = request.entity
    pre_col = "pre_name" if entity == "neuron" else "pre_celltype"
    post_col = "post_name" if entity == "neuron" else "post_celltype"

    region_response = _getRegionConnectivity(driver, request)
    if region_response is None:
        return None
    df = payloadToDataFrame(region_response)
    df = df[df[pre_col].isin(pre_names) & df[post_col].isin(post_names)].reset_index(drop=True)
    return _formatConnectivityResponse(df, entity, request.layout)


# --- response formatting ---


def _formatConnectivityResponse(df: pd.DataFrame, entity: str, layout: str) -> dict:
    if layout == "table":
        return dataFrameToPayload(df.reset_index(drop=True))
    if layout == "matrix":
        pre_col = "pre_name" if entity == "neuron" else "pre_celltype"
        post_col = "post_name" if entity == "neuron" else "post_celltype"
        matrix = _pivotAsMatrix(df, pre_col, post_col)
        return dataFrameToPayload(matrix, include_index=True)
    raise ValueError(f"Invalid layout {layout!r}")
