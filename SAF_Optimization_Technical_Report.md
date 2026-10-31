---
header-includes:
  - \usepackage{graphicx}
---

# SAF Supply-Chain Optimization in Kalimantan

## Technical modeling report

**Scope.** This report develops a mixed-integer linear programming model for a one-year sustainable aviation fuel (SAF) supply chain in Kalimantan. It is written as a mathematical-modeling study: the formulation, feasibility logic, computational method, and validation are the primary results.

## 1. Problem statement

The system collects biomass at source locations, moves it through biomass depots, converts it at SAF refineries, and supplies four airports:

```text
Biomass sources → depots → refineries → airports
```

The challenge statement specifies four airports—PNK, PKN, BPN, and TRK—with 300 kt SAF/year demand at each airport, for total demand of 1,200 kt/year [1,2].

The optimization problem is:

> Choose facility locations, facility sizes, biomass flows, and SAF flows to produce at least 1,200 kt SAF/year without exceeding any airport's demand cap, at minimum annualized cost.

The technical questions are:

1. At what feedstock recovery rate is the system feasible?
2. Which facility sizes and locations minimize annual cost?
3. How should biomass and SAF flow through the network?
4. Does the cost-minimizing network behave as a hub system or a distributed collection system?
5. How sensitive are feasibility and cost to uncertain assumptions?

## 2. Data and assumptions

### 2.1 Input data

The source file contains 80 biomass locations totaling 6,800 kt/year [3]. Airport coordinates and airport-specific demand are taken from the supplied airport CSV [2]. Facility, transport, and planning assumptions are taken from the updated Challenge 3 workbook [4].

The authoritative facility parameters are:

| Facility | Size | Biomass capacity (kt/year) | Annualized CapEx | Fixed OpEx | Variable OpEx |
|---|---:|---:|---:|---:|---:|
| Depot | Small | 150 | $112,500 | $112,500 | $5/t |
| Depot | Large | 300 | $225,000 | $225,000 | $4/t |
| Refinery | Small | 500 | $24,000,000 | $24,000,000 | $60/t |
| Refinery | Large | 1,087 | $38,250,000 | $38,250,000 | $55/t |

The workbook defines annualized CapEx as CapEx/20, fixed OpEx as 5% of CapEx, and facility capacity as biomass intake rather than SAF output [4].

Transport costs are $0.10/t-km from farm to depot, $0.12/t-km from depot to refinery, and $0.08/t-km from refinery to airport. Truck size changes reported trip counts but does not change the transport rate [4].

### 2.2 Baseline assumptions

The baseline uses the following challenge-provided assumptions:

- planning horizon: one year;
- biomass-to-SAF yield: \(\eta=0.20\);
- distance: great-circle distance multiplied by 1.3;
- TRK final leg: barge at the same stated transport rate;
- total SAF requirement: 1,200 kt/year, with each airport demand treated as an upper bound;
- facilities: located on Kalimantan land;
- unused biomass: allowed, because only 6,000 kt is required at 20% yield [1,4].

The 1.3 road factor is a proxy because no road network is supplied [4]. It is a modeling assumption, not an observed average road detour.

### 2.3 Facility candidate locations

The challenge permits facilities anywhere on land in Kalimantan but does not provide a continuous facility-location geometry model [1]. The baseline therefore uses inland biomass coordinates as discrete facility candidates. This is an author modeling choice documented in the optimizer configuration [5]. It is also a defensible screening proxy: arbitrary points selected without a land-use, protected-area, access-road, port, or development-feasibility layer could produce mathematically cheap but physically unbuildable facilities. The historical protected-area/concession source shows why land-use status matters, but it is not a current exclusion mask [9]. Restricting candidates to supplied biomass locations avoids claiming feasibility for unaccounted land parcels while keeping the optimization finite [1,5,9].

The actual Kalimantan province boundaries are taken from the GADM boundary dataset and are used for inland screening and map alignment [6]. They are not a protected-area mask.

The biomass table contains 12 coordinates that fall offshore under this geographic screen. These records remain available as feedstock sources in the baseline, but are excluded as depot/refinery candidates. This preserves the supplied biomass total while preventing facilities from being placed in the sea. Removing those source records entirely would leave 5,741.27 kt, below the 6,000 kt required at the baseline yield [3,5].

### 2.4 Arbitrary or analyst-selected choices

The following values are not independently measured in the supplied data and are explicitly treated as modeling choices:

| Choice | Value | Justification / citation |
|---|---:|---|
| Minimum utilization of opened facilities | 5% | Analyst choice to prevent zero-throughput facilities; configured in [5] |
| Facility candidates | Inland biomass coordinates | Discrete approximation to “anywhere on land”; [1,5] |
| Road-distance adjustment | 1.3× great-circle distance | Challenge assumption; [4] |
| Solver time limit | 120 seconds per scenario | Computational bound selected for a solo-run sensitivity sweep; [5] |
| Free-siting benchmark grid | 0.05° inland grid plus valid biomass sites | Higher-resolution benchmark approximation; computationally much larger than the baseline; [5,7] |

These choices should be reported as assumptions, not presented as empirical facts.

## 3. Mathematical formulation

### 3.1 Sets

Let:

- \(i\in I\): biomass sources;
- \(j\in J\): depot candidate locations;
- \(k\in K\): refinery candidate locations;
- \(a\in A\): airports;
- \(s\in\{S,L\}\): small or large facility size.

### 3.2 Parameters

Let:

- \(B_i\): annual biomass availability at source \(i\), kt/year;
- \(r\): recoverable fraction of biomass;
- \(D_a\): SAF demand at airport \(a\), kt/year;
- \(\eta=0.20\): SAF yield;
- \(C^D_s,C^R_s\): depot and refinery biomass-intake capacities;
- \(F^D_s,F^R_s\): annual fixed facility costs;
- \(V^D_s,V^R_s\): variable facility costs per tonne of biomass intake;
- \(c^{SD},c^{DR},c^{RA}\): transport costs per tonne-km;
- \(d^{SD}_{ij},d^{DR}_{jk},d^{RA}_{ka}\): adjusted distances.

The distance calculation is:

$$
d_{uv}=1.3\,d^{GC}_{uv},
$$

where the great-circle distance is calculated from latitude and longitude using the haversine formula [4,5].

### 3.3 Decision variables

\(x_{ij}\) is biomass shipped from source \(i\) to depot \(j\), in kt/year.

\(z_{jk}\) is biomass shipped from depot \(j\) to refinery \(k\), in kt/year.

\(q_{ka}\) is SAF shipped from refinery \(k\) to airport \(a\), in kt/year.

\(y^D_{js}\) is a binary variable equal to 1 if depot \(j\) is opened at size \(s\).

\(y^R_{ks}\) is a binary variable equal to 1 if refinery \(k\) is opened at size \(s\).

Because variable OpEx depends on selected facility size, auxiliary flow variables are used to keep the formulation linear. They represent the portion of flow passing through a large facility and activate the difference between small and large variable costs.

### 3.4 Objective function

The model minimizes annual system cost:

$$
\min Z = Z_{\text{fixed}}+Z_{\text{variable}}+Z_{\text{transport}}.
$$

The fixed-cost component is:

$$
Z_{\text{fixed}}=
\sum_{j,s}F^D_s y^D_{js}
+\sum_{k,s}F^R_s y^R_{ks}.
$$

The transport component is:

$$
Z_{\text{transport}}=
1000\left(
\sum_{i,j}c^{SD}d^{SD}_{ij}x_{ij}
+\sum_{j,k}c^{DR}d^{DR}_{jk}z_{jk}
+\sum_{k,a}c^{RA}d^{RA}_{ka}q_{ka}
\right),
$$

where the factor 1000 converts kt to tonnes.

The variable-cost component applies the selected size-specific cost to biomass intake. The auxiliary variables linearize the size-dependent term rather than multiplying a continuous flow by a binary variable [5].

### 3.5 Constraints

**Source availability.**

$$
\sum_{j}x_{ij}\le rB_i
\qquad \forall i\in I.
$$

**Depot flow conservation.**

$$
\sum_i x_{ij}=\sum_k z_{jk}
\qquad \forall j\in J.
$$

**Depot capacity and size selection.**

$$
\sum_i x_{ij}\le\sum_s C^D_s y^D_{js}
\qquad \forall j\in J,
$$

$$
\sum_s y^D_{js}\le1
\qquad \forall j\in J.
$$

The baseline also imposes:

$$
\sum_i x_{ij}
\ge 0.05\sum_s C^D_s y^D_{js}
\qquad \forall j\in J.
$$

The 5% value is an analyst-selected anti-degeneracy constraint, not a challenge-provided operating requirement [5].

**Refinery conversion.**

$$
\sum_aq_{ka}=\eta\sum_jz_{jk}
\qquad \forall k\in K.
$$

Refinery capacity is applied to biomass intake:

$$
\sum_jz_{jk}\le\sum_s C^R_s y^R_{ks}
\qquad \forall k\in K.
$$

The refinery size-selection constraint is:

$$
\sum_s y^R_{ks}\le1
\qquad \forall k\in K.
$$

**Airport demand.**

$$
\sum_kq_{ka}=D_a
\qquad \forall a\in A.
$$

The airport constraints are upper bounds:

\[
\sum_kq_{ka}\le D_a\qquad\forall a\in A.
\]

To prevent the positive-cost objective from choosing zero production, the model also imposes a system-wide SAF requirement:

\[
\sum_{k,a}q_{ka}\ge\sum_aD_a=1{,}200.
\]

Because the four airport upper bounds sum to exactly 1,200 kt, the combination still delivers 300 kt to each airport in the current baseline, but the constraint semantics are demand caps rather than four strict equalities [1,5].

**Integrality and nonnegativity.**

$$
y^D_{js},y^R_{ks}\in\{0,1\},
\qquad x_{ij},z_{jk},q_{ka}\ge0.
$$

## 4. Feasibility analysis

At 20% yield, the network requires:

$$
\frac{1{,}200}{0.20}=6{,}000\text{ kt biomass/year}.
$$

The necessary recovery threshold is:

$$
r\ge\frac{6{,}000}{6{,}800}=0.88235.
$$

Therefore:

| Recovery | Recovered biomass | Result |
|---:|---:|---|
| 90% | 6,120 kt | Feasible with only 120 kt slack |
| 95% | 6,460 kt | Feasible |
| 100% | 6,800 kt | Feasible |

This calculation is independent of facility locations and is the strongest initial feasibility result in the study. The computational sensitivity starts at 90% because it is the nearest selected rate above the analytical threshold, while 95% represents moderate recovery loss and 100% is the no-loss upper benchmark. These are analyst-selected scenario points intended to bracket the feasible region, not measured recovery probabilities [5].

## 5. Computational method and validation

The model is implemented in Python using SciPy's HiGHS-backed `milp` solver [5]. The workflow is:

1. Load the challenge CSV and workbook.
2. Classify biomass coordinates against Kalimantan polygons.
3. Build source, depot, refinery, and airport node sets.
4. Calculate adjusted distance matrices.
5. Construct sparse MILP variables and constraints.
6. Solve each recovery scenario.
7. Extract facilities, flows, utilization, and airport deliveries.
8. Generate network maps and validation tables.

The following checks were applied to the latest baseline outputs:

- no airport receives more than 300 kt SAF;
- total airport delivery is at least 1,200 kt SAF;
- source-to-depot flow equals depot-to-refinery flow at 6,000 kt;
- refinery intake converts to exactly 1,200 kt SAF;
- no flow uses an unselected depot or refinery;
- selected facilities are inland under the GADM screen;
- stored route distances equal 1.3 times the haversine distance;
- all reported facility binaries are integral in the returned incumbent.

### 5.1 Relevant implementation snippets

The following excerpts show how the technical assumptions are translated into code [5].

**Configuration and scenario selection:**

```python
YIELD = 0.20
ROAD_FACTOR = 1.30
RECOVERY_SCENARIOS = [0.90, 0.95, 1.00]
TIME_LIMIT_SECONDS = 120
MIN_FACILITY_UTILIZATION = 0.05
FREE_SITING_GRID_DEG = 0.05
```

**Inland facility screening:**

```python
biomass["on_land"] = kalimantan_land_flags(biomass)
sources = biomass.reset_index(drop=True)
depots = sources[sources.on_land].reset_index(drop=True)
refineries = depots.copy()
```

This keeps source supply separate from facility feasibility: offshore source records are retained for the stated baseline assumption, but cannot become facilities.

**Distance matrices:**

```python
d_sd = ROAD_FACTOR * haversine(source_xy, depot_xy)
d_dr = ROAD_FACTOR * haversine(depot_xy, refinery_xy)
d_ra = ROAD_FACTOR * haversine(refinery_xy, airport_xy)
```

The complete implementation expands these arrays for the sparse MILP matrix [5].

**Facility costs and flow conservation:**

```python
c[depot_open] = annualized_capex + fixed_opex
c[biomass_to_depot] = distance_cost + variable_opex_per_tonne * 1000

add_row(
    biomass_to_depot_into_depot,
    depot_to_refinery_out_of_depot,
    lower=0,
    upper=0,
)
```

The first lines add fixed and variable terms to the objective. The flow-balance row forces every selected depot to pass on exactly the biomass it receives [5].

**Capacity and size linking:**

```python
sum(inbound_flow) <= small_capacity * open_small \
                  + large_capacity * open_large
open_small + open_large <= 1
```

This is the binary-continuous linking structure that turns the network design into a MILP [5].

**Airport demand caps and total requirement:**

```python
for airport in airports:
    sum(q[k, airport] for k in refineries) <= airport.demand

sum(q[k, a] for k in refineries for a in airports) >= total_demand
```

The first constraint prevents over-delivery at any airport. The second prevents the trivial zero-flow solution caused by positive operating and transport costs. Since the four caps sum to the required total, the current solution delivers 300 kt to each airport.

**HiGHS MILP solve:**

```python
result = milp(
    c=objective,
    integrality=integrality,
    bounds=Bounds(lower, upper),
    constraints=LinearConstraint(A, lower_constraints, upper_constraints),
    options={"time_limit": TIME_LIMIT_SECONDS},
)
```

**Facility utilization validation:**

```python
utilization = throughput_kt / capacity_kt
assert throughput_kt >= MIN_FACILITY_UTILIZATION * capacity_kt
```

### Warm-started free siting

```python
seed = seed_from_baseline(free_model, baseline_90_solution)
highs.passModel(free_model)
solution = HighsSolution()
solution.col_value = seed
highs.setSolution(solution)
highs.run()
```

SciPy's `milp` wrapper does not expose MIP starts, so the native HiGHS Python interface is used for this experiment [7].

These snippets are abbreviated for readability; the complete implementation is cited in [5].

\newpage

## 6. Baseline results

The solver was limited to 120 seconds per scenario, so feasible cases are reported as incumbents rather than proven global optima [5].

| Recovery | Annual cost | Depots | Refineries | Delivered SAF | Solver status |
|---:|---:|---:|---:|---:|---|
| 90% | $918.44M | 35 | 6 | 1,200 kt | Time limit; feasible incumbent |
| 95% | $902.34M | 27 | 6 | 1,200 kt | Time limit; feasible incumbent |
| 100% | $896.47M | 23 | 6 | 1,200 kt | Time limit; feasible incumbent |

The 90% case uses 35 depots and six large refineries. The number of depots decreases as recovery improves because additional recovered biomass reduces the need to activate marginal collection locations.

### 6.1 Utilization

The full facility-level table is in [baseline_facility_utilization.csv](./outputs/baseline_facility_utilization.csv) [8]. Summary statistics are:

| Recovery | Facility | Count | Min | Mean | Max |
|---:|---|---:|---:|---:|---:|
| 90% | Depots | 35 | 5.0% | 64.5% | 100.0% |
| 90% | Refineries | 6 | 68.8% | 92.0% | 100.0% |
| 95% | Depots | 27 | 5.0% | 85.7% | 100.0% |
| 95% | Refineries | 6 | 71.8% | 92.0% | 100.0% |
| 100% | Depots | 23 | 35.8% | 89.1% | 100.0% |
| 100% | Refineries | 6 | 69.0% | 92.0% | 100.0% |

The repeated 5% depot values are a direct consequence of the analyst-selected minimum-utilization constraint. They should be treated as a warning that the baseline permits marginal depots, not as evidence that 5%-utilized facilities are operationally desirable.

The network is more concentrated at the refinery layer than at the depot layer. This follows from the much larger refinery fixed costs and the need to process 6,000 kt of biomass, while depots are relatively inexpensive and limited to 150 or 300 kt intake [4].

### 6.2 Network flow maps

The following maps show the selected facilities and great-circle route arcs for every feasible recovery scenario. Green squares are depots, red triangles are refineries, purple circles are airports, grey points are inland biomass sites, and red crosses are offshore source coordinates retained only as feedstock records. The Kalimantan boundary is used for geographic alignment, not as a protected-area exclusion layer [5,6].

\begin{center}
\includegraphics[width=6.2in]{outputs/network_recovery_09.png}

\textbf{Figure 1.} Network flow at 90\% recovery.
\end{center}

\newpage

\begin{center}
\includegraphics[width=6.2in]{outputs/network_recovery_095.png}

\textbf{Figure 2.} Network flow at 95\% recovery.
\end{center}

\newpage

\begin{center}
\includegraphics[width=6.2in]{outputs/network_recovery_10.png}

\textbf{Figure 3.} Network flow at 100\% recovery.
\end{center}

## 7. Free-siting benchmark

A separate test is configured for a 0.05° inland grid plus valid biomass coordinates [5,7]. This is approximately 5.5 km in latitude and is much more geographically reasonable than a 1° grid, but a full Kalimantan grid creates thousands of potential locations and a dramatically larger MILP. The implemented warm-start experiment therefore uses a 0.05° local neighborhood around the 90% baseline facilities, plus all valid biomass coordinates [7].

HiGHS accepted the saved 90% baseline solution as a genuine MIP start for the local 0.05° model. The resulting 339-candidate model retained the baseline incumbent at $918.44M after 120 seconds, with a 9.07% MIP gap. No saving was observed, but the result does not prove that no nearby siting improvement exists. Since the free-siting candidate set contains all baseline candidate sites, its exact optimum cannot be more expensive; a non-improving incumbent is therefore a convergence result, not a structural conclusion.

The free-siting outputs are retained in the [benchmark notes](./FREE_SITING_NOTES.md), the [warm-start result](./outputs/free_siting_warm_start_90.json), and the [earlier long-run result](./outputs/free_siting_90_long.json) [7]. No free-siting saving is claimed.

## 8. Limitations and risk interpretation

### 8.1 Geographic data

The biomass records include offshore coordinates. They are preserved as source supply for the baseline but excluded as facility candidates. This is a data-quality limitation, not a validated physical interpretation [3,5].

### 8.2 Facility siting

The baseline is a discrete facility-location model over inland biomass coordinates. It is not a continuous optimization over every possible parcel of land. The free-siting test is also discrete because the grid is an approximation [1,5,7].

### 8.3 Transport

The 1.3 distance multiplier is a proxy for road distance. Actual road-network routing, bridges, river crossings, port access, vehicle availability, and seasonal disruption are not represented [4].

### 8.4 Trucks and trips

Truck sizes affect reported trip counts but do not constrain annual flow in the current MILP because the workbook specifies that truck size only changes the number of trips [4]. One truck is therefore not modeled as a one-time capacity limit.

### 8.5 Protected areas

The supplied protected-area figure is historical land-use context from Gaveau et al. and is not a current georeferenced protected-area exclusion mask [9]. The model therefore does not claim legal or environmental site clearance.

### 8.6 Solver optimality

The latest feasible cases reach the 120-second time limit. They satisfy the constraints, but the objective values are not proven globally optimal. This distinction is essential when interpreting small cost differences between scenarios [5].

## 9. Conclusions

The necessary feedstock recovery threshold is 88.24%. The selected 90% recovery case is therefore a near-threshold stress case with only 120 kt of biomass slack; 95% is a moderate-recovery case and 100% is the no-loss upper benchmark.

The MILP produces a distributed depot layer and a more concentrated refinery layer. This is mathematically consistent with the supplied capacity and cost structure: depots have much lower fixed costs and limited capacities, while refineries have large fixed costs and act as regional processing hubs.

The current model is suitable as a transparent mathematical planning benchmark. It is not yet a final siting or investment recommendation because candidate locations, road distances, offshore source coordinates, protected-area status, and solver optimality require further validation.

## References

[1] Airbus / Autonomous SG 2026, *Challenge 3: SAF Supply Chain*. [Local PDF](./Autonomous%20SG%202026%20-%20Airbus%20Problem%20Statements%20%28Updated%29.pdf).

[2] Supplied airport input, `challenge3_airports_4.csv`.

[3] Supplied biomass input, `biomass.csv`, copied from the Challenge 3 dataset.

[4] Supplied Challenge 3 parameter workbook, `challenge3_parameters.xlsx`.

[5] This project's [optimizer implementation](./optimize.py) and [configuration](./config.py). These are the sources for implementation choices, solver time limit, candidate filtering, distance calculation, and minimum utilization.

[6] GADM, [administrative boundary data](https://www.gadm.org/download), used for Kalimantan inland screening and map alignment.

[7] This project's [free-siting benchmark](./free_siting_test.py), [configuration](./config.py), and [benchmark notes](./FREE_SITING_NOTES.md). The 0.05° grid is an explicitly stated analyst approximation and is not yet run to convergence.

[8] This project's [facility utilization output](./outputs/baseline_facility_utilization.csv).

[9] Gaveau et al. (2013), [Reconciling Forest Conservation and Logging in Indonesian Borneo](https://doi.org/10.1371/journal.pone.0069887). Used only for historical protected-area/concession context, not as a current exclusion layer.
