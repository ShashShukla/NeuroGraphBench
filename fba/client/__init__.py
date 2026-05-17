"""FBA Python client.

Two co-existing surfaces:

**Raw methods** — DataFrames / navis objects, one method per REST endpoint::

    from fba.client import Client

    fba = Client("http://localhost:8000")
    neuropils = fba.listNeuropils()
    mesh      = fba.getNeuropilMesh("LOP")
    synTable  = fba.getNeuronSynapseTable("LPLC2_R_1")
    conn      = fba.getConnectivity(names=["LPLC2_R_1", "PVLP011_R"],
                                    region={"neuropil": "PVLP"})

**Object model** — entities with relationships (see `fba.client.models`)::

    neuron = fba.neuron("LPLC2_R_1")
    lop    = fba.neuropil("LOP")
    seg    = neuron.segmentIn(lop)
    syns   = seg.synapses                # pandas.DataFrame
    parts  = neuron.partners(region=lop) # list[Neuron]

The client wraps HTTP calls (see `fba.client.http`) and de-serializes responses
into `navis` / `pandas` / `numpy` types (see `fba.client.deserialize`).

Naming: camelCase functions/methods, snake_case variables and pandas columns.
"""

from .http import Client
from .models import Region
from .serialize import meshToPayload, regionToSpec

__all__ = ["Client", "Region", "meshToPayload", "regionToSpec"]
