"""Cypher queries backing synapse-table endpoints.

Lifted from `FlyBrainAtlas/query.py` (`getNeuropilSynapseTable` and the
underlying `fetchNeuropilSynapseTable`). Returns `TablePayload`-shaped dicts:

    {"columns": [...], "data": {col: [values]}}

The cached path tries `Neuropil -[:HasData]-> SynapseTable`; on miss it falls
back to a heavier traversal that joins synapse clouds with pre/post neurons
and pages through the per-neuropil `RegionSynapseSet`.
"""

import numpy as np
from neo4j import Driver

from ..neo4j_driver import database


def getNeuropilSynapseTable(driver: Driver, neuropilName: str) -> dict | None:
    """Return the synapse table for a neuropil, hitting cache when available.

    Returns a TablePayload-shaped dict, or None if the neuropil does not exist.
    Lifted from `query.getNeuropilSynapseTable`.
    """
    # check neuropil exists
    records, _, _ = driver.execute_query(
        "MATCH (r:Neuropil {name:$name}) RETURN r AS neuropil LIMIT 1",
        name=neuropilName,
        database_=database(),
    )
    if len(records) == 0:
        return None

    # try cached SynapseTable
    records, _, _ = driver.execute_query(
        """
        MATCH (n:Neuropil {name:$name})-[:HasData]->(st:SynapseTable)
        RETURN st AS synapse_table
        """,
        name=neuropilName,
        database_=database(),
    )
    if len(records) > 0:
        return _tableNodeToPayload(records[0]["synapse_table"])

    # cache miss: fall back to live fetch
    return _fetchNeuropilSynapseTable(driver, neuropilName)


def _tableNodeToPayload(tableNode: dict) -> dict:
    """Convert a SynapseTable neo4j node (column → array properties) to TablePayload."""
    raw = dict(tableNode)
    data = {col: list(values) for col, values in raw.items()}
    return {"columns": list(data.keys()), "data": data}


# Lifted verbatim from FlyBrainAtlas/query.fetchNeuropilSynapseTable, with
# error-dict returns replaced by None and the final pd.DataFrame replaced by
# a TablePayload dict (so the server never imports pandas).
def _fetchNeuropilSynapseTable(driver: Driver, neuropilName: str) -> dict:
    """Live fetch of per-neuropil synapse table when no cache exists."""
    records, _, _ = driver.execute_query(
        """
        MATCH (rss:RegionSynapseSet {region:$name})-
        [:References]->
        (ss:SynapseSet)-
        [:HasData]->
        (sc:SynapseCloud),
        (pre_neuron:Neuron)-
        [:SendsTo]->
        (rss)-
        [:SendsTo]->
        (post_neuron:Neuron)
        RETURN rss, sc, pre_neuron, post_neuron
        """,
        name=neuropilName,
        database_=database(),
    )

    columns = [
        "x", "y", "z",
        "pre_name", "pre_celltype",
        "post_name", "post_celltype",
        "neurotransmitters",
    ]
    data: dict[str, list] = {col: [] for col in columns}

    if len(records) == 0:
        return {"columns": columns, "data": data}

    # detect whether the database has neurotransmitter data on any neuron
    test_records, _, _ = driver.execute_query(
        "MATCH (n:Neuron) RETURN n AS neuron LIMIT 1",
        database_=database(),
    )
    has_nts = bool(test_records) and "neurotransmitters" in test_records[0]["neuron"]

    for record in records:
        ids = record["rss"]["ids"]
        sc = record["sc"]
        # indexed gather over parallel-array storage in the SynapseCloud node
        xs = np.asarray(sc["x"])[ids]
        ys = np.asarray(sc["y"])[ids]
        zs = np.asarray(sc["z"])[ids]
        pre_neuron = record["pre_neuron"]
        post_neuron = record["post_neuron"]
        count = len(xs)

        nts = ",".join(pre_neuron["neurotransmitters"]) if has_nts else ""

        data["x"].extend(xs.tolist())
        data["y"].extend(ys.tolist())
        data["z"].extend(zs.tolist())
        data["pre_name"].extend([pre_neuron["name"]] * count)
        data["pre_celltype"].extend([pre_neuron["celltype"]] * count)
        data["post_name"].extend([post_neuron["name"]] * count)
        data["post_celltype"].extend([post_neuron["celltype"]] * count)
        data["neurotransmitters"].extend([nts] * count)

    return {"columns": columns, "data": data}
