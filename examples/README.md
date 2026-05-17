# Examples

One notebook per NGB capability. Each notebook is the canonical reference for
*how to use* the corresponding capability end-to-end, and is the place to look
when learning the toolset.

| Notebook | Capability | Status | Source material at repo root |
| --- | --- | --- | --- |
| `01-regional-analysis.ipynb` | Regional analysis | First slice — to be authored | `LobulaPlate.ipynb`, `LPi.ipynb`, `Lobula.ipynb`, `LPLC2_PopulationGeometry.ipynb` |
| `02-skeletal-analysis.ipynb` | Skeletal analysis | TBD | `DendriticBall.ipynb`, `Morphometrics.ipynb`, `Neuron3DFlow.ipynb` |
| `03-topographic-mapping.ipynb` | Topographic mapping | TBD | `IsometricNeuronProjection`, `L1_Topography.ipynb` |
| `04-retinotopic-mapping.ipynb` | Retinotopic mapping | TBD | `NewRetinotopy.ipynb`, `LPLC2_Morphology_Retinotopy.ipynb` |

## Drafting principles

- Each notebook should run top-to-bottom against a single FBA server instance.
- Imports come from `fba.client` and `ngb.*` only. No direct `neo4j` driver use
  in user-facing code.
- Demonstrate one or two non-trivial findings from the manuscript rather than
  exhaustive feature listing.
- Where the same intermediate computation appears in multiple notebooks, factor
  it into `ngb/` rather than duplicating notebook cells.
