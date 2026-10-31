# Free-siting benchmark

The test replaces biomass-only facility candidates with a finite inland grid plus the valid biomass coordinates.

- Grid resolution configured: 0.05 degree latitude/longitude, plus the 68 valid biomass coordinates
- Candidate count: not run to completion; the 0.05-degree grid creates thousands of inland candidates
- Feedstock sources: unchanged 80 records, including the 12 offshore source coordinates
- Demand, yield, costs, and distance factor: unchanged from the baseline

Earlier 0.5-degree and 1.0-degree tests produced larger MILPs and time-limit incumbents. The coarse 1.0-degree 90% incumbent was more expensive than baseline, but this negative “saving” is not a real result: because the grid contains all baseline candidate sites, the exact free-siting optimum cannot be worse than baseline. The difference shows that the larger model had not converged enough.

Conclusion: a 0.05-degree grid is geographically more defensible than 1 degree, but it is too large for the current dense arc formulation without decomposition, warm starts, candidate reduction, or a continuous location-allocation method. Do not claim a free-siting saving yet.

## Warm-started local test

The native `highspy` interface was used to pass the saved 90% baseline solution as a genuine HiGHS MIP start. To keep the model computationally bounded, the candidate set was a 0.05-degree local neighborhood around the baseline facilities, plus all valid biomass coordinates. This produced 339 inland candidates.

After 120 seconds, HiGHS retained the baseline incumbent at $918.44M, with no observed saving and a 9.07% MIP gap. This is a valid warm-start result: it proves that the seeded baseline is feasible in the enlarged candidate set, but it does not prove that no nearby siting improvement exists.
