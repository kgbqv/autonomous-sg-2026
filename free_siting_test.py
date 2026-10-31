#!/usr/bin/env python3
"""Benchmark facility siting on a regular inland Kalimantan grid."""

import json
from collections import defaultdict

import numpy as np
import pandas as pd

import optimize as opt
from config import OUT, RECOVERY_SCENARIOS, FREE_SITING_GRID_DEG


def make_grid(biomass, spacing_deg=FREE_SITING_GRID_DEG):
    # A finite grid is the practical MILP approximation to "anywhere on land".
    lats = np.arange(-4.5, 4.51, spacing_deg)
    lons = np.arange(109.0, 119.01, spacing_deg)
    rows = [{"location_id": f"GRID_{i:04d}", "latitude": float(lat), "longitude": float(lon), "production_kilotons": 0.0}
            for i, (lat, lon) in enumerate(( (lat, lon) for lat in lats for lon in lons ))]
    grid = pd.DataFrame(rows)
    grid["on_land"] = opt.kalimantan_land_flags(grid)
    grid = grid[grid.on_land].copy()
    # Include the valid source coordinates as extra candidate points so the
    # benchmark cannot be worse merely because of grid quantization.
    extras = biomass[biomass.on_land][["location_id", "latitude", "longitude", "production_kilotons", "on_land"]]
    grid = pd.concat([grid, extras], ignore_index=True).drop_duplicates(subset=["latitude", "longitude"])
    return grid.reset_index(drop=True)


def utilization(solution, facilities):
    depot_in = defaultdict(float)
    ref_in = defaultdict(float)
    for r in solution["routes"]["biomass_to_depot"]: depot_in[r["to"]] += r["flow_kt"]
    for r in solution["routes"]["depot_to_refinery"]: ref_in[r["to"]] += r["flow_kt"]
    out = []
    for ftype, selected, flows in [("depot", solution["depots"], depot_in), ("refinery", solution["refineries"], ref_in)]:
        for f in selected:
            cap = facilities[(ftype, f["size"])] ["capacity_kt"]
            out.append({"facility_type": ftype, "location_id": f["location_id"], "size": f["size"],
                        "latitude": f["lat"], "longitude": f["lon"], "throughput_kt": flows[f["location_id"]],
                        "capacity_kt": cap, "utilization": flows[f["location_id"]] / cap})
    return out


def main():
    biomass, airports, facilities, transport = opt.load_inputs()
    candidates = make_grid(biomass)
    baseline = json.loads((OUT / "updated_results.json").read_text())
    results = {"grid_spacing_deg": FREE_SITING_GRID_DEG, "candidate_count": len(candidates), "scenarios": {}}
    for recovery in RECOVERY_SCENARIOS:
        model = opt.build_model(biomass, airports, facilities, transport, recovery, candidate_locations=candidates)
        result = opt.solve(model)
        sol = opt.extract(result, model, airports, recovery)
        if sol is None:
            results["scenarios"][str(recovery)] = None
            print(f"recovery={recovery:.0%}: infeasible/no incumbent")
            continue
        sol["candidate_mode"] = f"{FREE_SITING_GRID_DEG}-degree inland grid plus valid biomass coordinates"
        sol["candidate_count"] = len(candidates)
        sol["facility_utilization"] = utilization(sol, facilities)
        base = baseline.get(str(recovery))
        sol["baseline_objective_usd"] = None if base is None else base["objective_usd"]
        sol["savings_usd"] = None if base is None else base["objective_usd"] - sol["objective_usd"]
        results["scenarios"][str(recovery)] = sol
        print(f"recovery={recovery:.0%}: grid=${sol['objective_usd']/1e6:.2f}M, savings=${sol['savings_usd']/1e6:.2f}M")
    (OUT / "free_siting_results.json").write_text(json.dumps(results, indent=2))
    rows = []
    for sol in results["scenarios"].values():
        if sol: rows.extend([{**r, "recovery": sol["recovery"]} for r in sol["facility_utilization"]])
    pd.DataFrame(rows).to_csv(OUT / "free_siting_facility_utilization.csv", index=False)
    candidates.to_csv(OUT / "free_siting_candidates.csv", index=False)
    print(f"candidates={len(candidates)}; wrote free_siting_results.json and utilization CSV")


if __name__ == "__main__":
    main()
