# SAF Optimizer — Updated Challenge 3

## Repository contents

- `SAF_Optimization_Technical_Report.md` — technical mathematical-modeling report
- `SAF_Optimization_Technical_Report.pdf` — exported report
- `optimize.py` and `config.py` — baseline MILP and configuration
- `free_siting_warm_start.py` — HiGHS MIP-start free-siting experiment
- `data/` — challenge inputs and inland boundary data
- `outputs/` — validated results, utilization table, network maps, and free-siting output

## Reproduce the baseline

```bash
python3 -m pip install -r requirements.txt
cd github_submission
python3 optimize.py
python3 report_metrics.py
```

The baseline uses a 120-second HiGHS time limit per recovery scenario. The free-siting warm-start experiment requires `highspy` and is intentionally a local 0.05-degree neighborhood around the 90% baseline facilities.

This folder is the separate workspace for the updated Problem 3 specification.

Inputs copied here:

- `data/challenge3_parameters.xlsx` — authoritative facilities, transport, airport demand, and assumptions
- `data/challenge3_airports_4.csv` — the four airports and 300 kt/year demand each
- `data/biomass.csv` — 80 biomass sites totaling 6,800 kt/year
- `data/kalimantan_protected_areas_reference.png` — user-provided reference figure from Gaveau et al. (2013)
- `data/indonesia_provinces.geojson` — GADM province boundary layer used only to align the Kalimantan reference map
- `Autonomous SG 2026 - Airbus Problem Statements (Updated).pdf` — updated statement and clarifications

The new solution must model:

- 1,200 kt/year total SAF requirement, with a 300 kt/year cap at each airport;
- 0.20 t SAF per tonne biomass;
- facility capacity as biomass intake, including refineries;
- annualized CapEx = CapEx / 20;
- fixed OpEx = 5% of CapEx per year;
- variable OpEx per tonne of biomass intake;
- distance = great-circle distance × 1.3;
- the TRK final leg as a barge with the same transport rate;
- airport demand as an upper bound plus a system-wide 1,200 kt/year requirement;
- facilities reportable by coordinates on Kalimantan land.

The previous `saf_optimizer/` folder is preserved as the earlier exploratory model and should not be overwritten.

## Protected-area risk treatment

The protected-area figure is useful as qualitative evidence that land-use constraints and accessibility matter. It is not a georeferenced vector mask, so it must not be used to mark individual candidate points as protected or available. The updated MVP should either:

1. use it as a presentation/context figure and keep facility candidates at inland biomass coordinates; or
2. obtain a real GIS protected-area layer and add explicit site-exclusion constraints.

The cited study found protected areas covered about 110,232 km² in its 2010 map and analyzed forest/concession change from 2000–2010. Those historical categories are not a current land-availability dataset.

## Recommended risk sensitivities

- biomass recovery: 90%, 95%, 100%, selected to bracket the feasible threshold;
- fixed 20% yield baseline, with optional 15% and 25% stress tests;
- biomass-source outage: remove the largest source or randomly remove 5–10% of sites;
- facility outage: disable one selected refinery;
- CapEx contingency: +10%, +20%, +30%;
- transport disruption: 1.3x, 1.5x, and 2.0x route-distance/cost factors;
- TRK barge disruption: reduce or disable the final-leg capacity if capacity data is later obtained.

The 5% biomass-loss case is reasonable as a sensitivity, but it should not be called a measured fact. A better presentation is to show the full 80–100% recovery curve and let the optimizer identify the feasibility threshold.

The GADM overlay identifies 12 of the 80 supplied biomass coordinates as offshore, including the suspected site near 110°E, 2°S. These points remain in the feedstock-supply accounting for now, but are excluded from depot/refinery candidate locations and shown as red crosses. If they are also removed from feedstock supply, only 5,741.27 kt remains—below the 6,000 kt biomass requirement for 1,200 kt SAF at 20% yield—so the problem becomes infeasible even at 100% recovery. That is a data-quality issue to disclose, not hide.

The facility-dimension indexing was corrected after the land-only filter: the model now has 80 source nodes but 68 inland depot/refinery candidate nodes. Flow-balance validation now confirms 6,000 kt source-to-depot, 6,000 kt depot-to-refinery, and 1,200 kt refinery-to-airport flow in the 90% case, with no flow through an unselected depot.

The current run also imposes a 5% minimum utilization on an opened facility, removing zero-throughput “stray” depots. The latest 90% incumbent uses 36 depots and 6 large refineries. This is still a decentralized capacitated-facility-location model, not an explicit hub-location model.

## Latest run

`optimize.py` now uses exact size-dependent variable OpEx through linear auxiliary flow variables, uses airport demand caps plus a system-wide production requirement, and writes route figures with great-circle arcs. The run uses a 1.3× distance factor and a 120-second HiGHS time limit per recovery case. The configured 90%, 95%, and 100% cases return feasible incumbents, but their solver status is time-limit rather than proven optimality. The network maps use GADM province boundaries for land/water QA, not a protected-area or legal land-availability GIS layer.
