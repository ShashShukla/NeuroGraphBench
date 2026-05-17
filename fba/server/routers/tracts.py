"""/tracts resource.

Endpoints (stubs):
    POST /tracts                          — neurons/celltypes with inputs in
                                            source_region and outputs in target_region

TODO: lift from FlyBrainAtlas/query.py:
    getTract (source/target via getRegionArborization, then merge on names).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/tracts", tags=["tracts"])
