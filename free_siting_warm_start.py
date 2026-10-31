#!/usr/bin/env python3
"""Local 0.05-degree free-siting test seeded by the saved 90% baseline solution."""

import json
from pathlib import Path

import highspy
import numpy as np
import pandas as pd

import optimize as opt
from config import OUT, TIME_LIMIT_SECONDS


def local_candidates(biomass, baseline, step=0.05, radius=0.05):
    rows = []
    for facility in baseline["depots"] + baseline["refineries"]:
        for dlat in np.arange(-radius, radius + 1e-9, step):
            for dlon in np.arange(-radius, radius + 1e-9, step):
                rows.append({"location_id": f"WARM_{len(rows):05d}",
                             "latitude": round(facility["lat"] + float(dlat), 5),
                             "longitude": round(facility["lon"] + float(dlon), 5),
                             "production_kilotons": 0.0})
    grid = pd.DataFrame(rows).drop_duplicates(["latitude", "longitude"]).reset_index(drop=True)
    grid["on_land"] = opt.kalimantan_land_flags(grid)
    grid = grid[grid.on_land].copy()
    extras = biomass[biomass.on_land][["location_id", "latitude", "longitude", "production_kilotons", "on_land"]]
    # Keep the original biomass IDs when a local grid point coincides with a
    # baseline candidate; this is what lets the saved solution seed the model.
    return pd.concat([extras, grid], ignore_index=True).drop_duplicates(["latitude", "longitude"]).reset_index(drop=True)


def highs_model(model):
    from scipy.sparse import csc_matrix
    lp = highspy.HighsLp()
    A = csc_matrix(model["A"])
    lp.num_col_ = len(model["c"]); lp.num_row_ = len(model["lb"])
    lp.col_cost_ = np.asarray(model["c"], dtype=np.float64)
    lp.col_lower_ = np.asarray(model["lower"], dtype=np.float64)
    lp.col_upper_ = np.asarray(model["upper"], dtype=np.float64)
    lp.row_lower_ = np.asarray(model["lb"], dtype=np.float64)
    lp.row_upper_ = np.asarray(model["ub"], dtype=np.float64)
    lp.integrality_ = np.asarray([highspy.HighsVarType.kInteger if x else highspy.HighsVarType.kContinuous for x in model["integrality"]])
    mat = highspy.HighsSparseMatrix()
    mat.format_ = highspy.MatrixFormat.kColwise
    mat.num_col_ = A.shape[1]; mat.num_row_ = A.shape[0]
    mat.start_ = np.asarray(A.indptr, dtype=np.int32)
    mat.p_end_ = np.asarray(A.indptr[1:], dtype=np.int32)
    mat.index_ = np.asarray(A.indices, dtype=np.int32)
    mat.value_ = np.asarray(A.data, dtype=np.float64)
    lp.a_matrix_ = mat
    return lp


def seed_from_baseline(model, biomass, baseline):
    x = np.zeros(len(model["c"]), dtype=float); idx = model["idx"]
    dep = model["depots"]; refs = model["refineries"]; sources = model["sources"]
    dep_pos = {v: i for i, v in enumerate(dep.location_id)}
    ref_pos = {v: i for i, v in enumerate(refs.location_id)}
    src_pos = {v: i for i, v in enumerate(sources.location_id)}
    dep_size = {v["location_id"]: v["size"] for v in baseline["depots"]}
    ref_size = {v["location_id"]: v["size"] for v in baseline["refineries"]}
    for v in baseline["depots"]:
        j = dep_pos[v["location_id"]]; x[idx["ds" if v["size"] == "small" else "dl"][j]] = 1
    for v in baseline["refineries"]:
        k = ref_pos[v["location_id"]]; x[idx["rs" if v["size"] == "small" else "rl"][k]] = 1
    for v in baseline["routes"]["biomass_to_depot"]:
        i, j = src_pos[v["from"]], dep_pos[v["to"]]; flow = v["flow_kt"]
        x[idx["b2d"][i * len(dep) + j]] = flow
        if dep_size[v["to"]] == "large": x[idx["b2dl"][i * len(dep) + j]] = flow
    for v in baseline["routes"]["depot_to_refinery"]:
        j, k = dep_pos[v["from"]], ref_pos[v["to"]]; flow = v["flow_kt"]
        x[idx["d2r"][j * len(refs) + k]] = flow
        if ref_size[v["to"]] == "large": x[idx["d2rl"][j * len(refs) + k]] = flow
    for v in baseline["routes"]["refinery_to_airport"]:
        k = ref_pos[v["from"]]; a = list(model["airports"].iata).index(v["to"]) if "airports" in model else None
        if a is not None: x[idx["r2a"][k * len(model["airports"]) + a]] = v["flow_kt"]
    return x


def main():
    biomass, airports, facilities, transport = opt.load_inputs()
    baseline = json.loads((OUT / "updated_results.json").read_text())["0.9"]
    candidates = local_candidates(biomass, baseline)
    model = opt.build_model(biomass, airports, facilities, transport, 0.90, candidate_locations=candidates)
    model["airports"] = airports
    seed = seed_from_baseline(model, biomass, baseline)
    h = highspy.Highs(); h.setOptionValue("time_limit", float(TIME_LIMIT_SECONDS)); h.setOptionValue("output_flag", False)
    h.passModel(highs_model(model))
    solution = highspy.HighsSolution(); solution.col_value = seed; solution.value_valid = True
    status = h.setSolution(solution); print("MIP start status:", status)
    h.run()
    info = h.getInfo(); sol = h.getSolution()
    result = type("Result", (), {"x": np.asarray(sol.col_value), "fun": info.objective_function_value,
                                 "status": 1, "message": h.modelStatusToString(h.getModelStatus())})()
    extracted = opt.extract(result, model, airports, 0.90)
    extracted["candidate_mode"] = "0.05-degree local inland grid around 90% baseline facilities"
    extracted["candidate_count"] = len(candidates)
    extracted["mip_gap"] = info.mip_gap
    extracted["mip_dual_bound"] = info.mip_dual_bound
    extracted["baseline_objective_usd"] = baseline["objective_usd"]
    extracted["savings_usd"] = baseline["objective_usd"] - extracted["objective_usd"]
    (OUT / "free_siting_warm_start_90.json").write_text(json.dumps(extracted, indent=2))
    print(f"candidates={len(candidates)} cost=${extracted['objective_usd']/1e6:.2f}M savings=${extracted['savings_usd']/1e6:.2f}M gap={info.mip_gap}")


if __name__ == "__main__": main()
