"""Innervation queries — neurite counts in regions for specified neurons/celltypes.

Lifted from `FlyBrainAtlas/query.py` (`getInnervationInRegions`,
`getInnervationInNeuropils`).

For each (entity, region) pair, count neurites of the entity that fall inside
the region's mesh. Thresholding filters out regions with very few neurites.

TODO: the original implementation iterates per-neuron via `navis.in_volume`,
which is O(N*M) for N neurons and M regions. Acceptable for small circuits;
needs batching for large queries.
"""

import navis
import numpy as np
import pandas as pd
from neo4j import Driver

from ..neo4j_driver import database
from . import neuropils as neuropilCypher
from ._tables import dataFrameToPayload


def getInnervation(driver: Driver, request) -> dict | None:
    """Dispatch from an `InnervationRequest`.

    If `regions` is omitted, default to *all* neuropils in the dataset (mirrors
    `query.getInnervationInNeuropils`).
    """
    if request.regions is None:
        regions = {
            name: payload for name, payload in neuropilCypher.getAllNeuropilMeshes(driver).items()
        }
    else:
        regions = {name: payload.model_dump() for name, payload in request.regions.items()}

    if not regions:
        return None

    # build navis.Volume map for in_volume tests
    region_volumes = {
        name: navis.Volume(
            vertices=np.asarray(payload["vertices"], dtype=float),
            faces=np.asarray(payload["faces"], dtype=int),
            name=name,
        )
        for name, payload in regions.items()
    }

    entity = request.entity
    rows = []
    total_neurite_count = 0

    if entity == "neuron":
        for neuron_name in request.names:
            neuron = _fetchNeuronSkeleton(driver, neuron_name)
            total_neurite_count += len(neuron.nodes)
            for region_name, volume in region_volumes.items():
                in_volume_mask = navis.in_volume(neuron.nodes, volume, inplace=False)
                count = int(np.sum(in_volume_mask))
                rows.append([neuron_name, region_name, count])
        columns = ["name", "region", "neurite_count"]

    elif entity == "celltype":
        for celltype_name in request.names:
            neuron_names = _fetchCelltypeNeuronNames(driver, celltype_name)
            for neuron_name in neuron_names:
                neuron = _fetchNeuronSkeleton(driver, neuron_name)
                total_neurite_count += len(neuron.nodes)
                for region_name, volume in region_volumes.items():
                    in_volume_mask = navis.in_volume(neuron.nodes, volume, inplace=False)
                    count = int(np.sum(in_volume_mask))
                    rows.append([celltype_name, region_name, count])
        columns = ["celltype", "region", "neurite_count"]
        # aggregate within celltype
        df = pd.DataFrame(rows, columns=columns)
        df = df.groupby(["celltype", "region"], as_index=False).sum()
        rows = df.values.tolist()
        columns = list(df.columns)
    else:
        raise ValueError(f"Invalid entity {entity!r}")

    df = pd.DataFrame(rows, columns=columns)

    # threshold by fraction of total neurites
    if request.threshold > 0 and total_neurite_count > 0:
        region_totals = df.groupby("region")["neurite_count"].sum()
        kept_regions = region_totals[region_totals / total_neurite_count > request.threshold].index
        df = df[df["region"].isin(kept_regions)].reset_index(drop=True)

    if request.layout == "table":
        return dataFrameToPayload(df.reset_index(drop=True))
    if request.layout == "matrix":
        name_col = columns[0]  # "name" or "celltype"
        matrix = pd.pivot_table(
            df, index=name_col, columns="region",
            values="neurite_count", fill_value=0,
        )
        return dataFrameToPayload(matrix, include_index=True)
    raise ValueError(f"Invalid layout {request.layout!r}")


def _fetchNeuronSkeleton(driver: Driver, name: str) -> navis.TreeNeuron:
    """Internal: pull a TreeNeuron for in_volume tests."""
    records, _, _ = driver.execute_query(
        """
        MATCH (:Neuron {name:$name})-[:HasData]-(st:SkeletonTree)
        RETURN st AS skeleton
        """,
        name=name, database_=database(),
    )
    if len(records) == 0:
        raise LookupError(f"No skeleton for neuron {name!r}")
    skeleton = records[0]["skeleton"]
    swc = pd.DataFrame({
        "x": skeleton["x"], "y": skeleton["y"], "z": skeleton["z"],
        "radius": skeleton["r"], "parent_id": skeleton["parent"],
    })
    swc["node_id"] = swc.index + 1
    tree = navis.heal_skeleton(navis.TreeNeuron(swc))
    tree.name = name
    tree.soma = [1]
    return tree


def _fetchCelltypeNeuronNames(driver: Driver, celltype: str) -> list[str]:
    records, _, _ = driver.execute_query(
        "MATCH (n:Neuron {celltype:$celltype}) RETURN n.name AS name",
        celltype=celltype, database_=database(),
    )
    return [record["name"] for record in records]
