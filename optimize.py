#!/usr/bin/env python3
"""Updated Challenge 3 MILP using the authoritative parameter workbook."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

from config import DATA, OUT, YIELD, ROAD_FACTOR, RECOVERY_SCENARIOS, TIME_LIMIT_SECONDS, MIN_FACILITY_UTILIZATION, FACILITY_CANDIDATE_MODE


def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return r * 2 * np.arcsin(np.sqrt(a))


def kalimantan_land_flags(df):
    """Classify points against the downloaded GADM Kalimantan province polygons."""
    from matplotlib.path import Path as MplPath
    boundary_path = DATA / "indonesia_provinces.geojson"
    if not boundary_path.exists():
        return np.ones(len(df), dtype=bool)
    with boundary_path.open() as f: geo = json.load(f)
    paths = []
    for feature in geo["features"]:
        if "kalimantan" not in str(feature.get("properties", {}).get("NAME_1", "")).lower():
            continue
        geom = feature["geometry"]
        polygons = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        paths.extend(MplPath(rings[0]) for rings in polygons)
    return np.array([any(p.contains_point((lon, lat)) for p in paths) for lat, lon in zip(df.latitude, df.longitude)])


def load_inputs():
    biomass = pd.read_csv(DATA / "biomass.csv")
    biomass["on_land"] = kalimantan_land_flags(biomass)
    airports = pd.read_csv(DATA / "challenge3_airports_4.csv")
    import openpyxl
    wb = openpyxl.load_workbook(DATA / "challenge3_parameters.xlsx", data_only=True, read_only=True)
    facilities = {}
    for row in list(wb["facilities"].iter_rows(values_only=True))[3:]:
        if row[0]:
            facilities[(str(row[0]).lower(), str(row[1]).lower())] = {
                "capex": float(row[2]), "capacity_kt": float(row[3]), "fixed_opex": float(row[4]),
                "variable_opex": float(row[5]), "annualized_capex": float(row[6]),
            }
    transport = {}
    for row in list(wb["transport"].iter_rows(values_only=True))[3:]:
        if row[0]: transport[str(row[0]).lower()] = {"cost": float(row[2]), "small_t": float(row[3]), "large_t": float(row[4])}
    return biomass, airports, facilities, transport


def add_row(rows, lbs, ubs, terms, lb, ub):
    rows.append(terms); lbs.append(lb); ubs.append(ub)


def build_model(biomass, airports, facilities, transport, recovery, candidate_locations=None):
    sources = biomass.reset_index(drop=True)
    # Retain all feedstock records for supply accounting, but only allow
    # facilities at coordinates classified as Kalimantan land.
    depots = (sources[sources.on_land].reset_index(drop=True).copy()
              if candidate_locations is None else candidate_locations.reset_index(drop=True).copy())
    refineries = depots.copy()
    ns = len(sources); nd = len(depots); nr = len(refineries); na = len(airports)
    cursor = 0; idx = {}
    for name, count in [("ds", nd), ("dl", nd), ("rs", nr), ("rl", nr), ("b2d", ns * nd), ("b2dl", ns * nd), ("d2r", nd * nr), ("d2rl", nd * nr), ("r2a", nr * na)]:
        idx[name] = np.arange(cursor, cursor + count); cursor += count
    nvars = cursor
    b2d = lambda i, j: idx["b2d"][i * nd + j]
    d2r = lambda j, k: idx["d2r"][j * nr + k]
    b2dl = lambda i, j: idx["b2dl"][i * nd + j]
    d2rl = lambda j, k: idx["d2rl"][j * nr + k]
    r2a = lambda k, a: idx["r2a"][k * na + a]

    depot_small = facilities[("depot", "small")]; depot_large = facilities[("depot", "large")]
    refinery_small = facilities[("refinery", "small")]; refinery_large = facilities[("refinery", "large")]
    farm_cost = transport["farm to depot"]["cost"]
    depot_cost = transport["depot to refinery"]["cost"]
    airport_cost = transport["refinery to airport"]["cost"]

    src_xy = sources[["latitude", "longitude"]].to_numpy()
    dep_xy = depots[["latitude", "longitude"]].to_numpy()
    ref_xy = refineries[["latitude", "longitude"]].to_numpy()
    ap_xy = airports[["latitude", "longitude"]].to_numpy()
    d_sd = ROAD_FACTOR * haversine(src_xy[:, 0, None], src_xy[:, 1, None], dep_xy[None, :, 0], dep_xy[None, :, 1])
    d_dr = ROAD_FACTOR * haversine(dep_xy[:, 0, None], dep_xy[:, 1, None], ref_xy[None, :, 0], ref_xy[None, :, 1])
    d_ra = ROAD_FACTOR * haversine(ref_xy[:, 0, None], ref_xy[:, 1, None], ap_xy[None, :, 0], ap_xy[None, :, 1])

    c = np.zeros(nvars)
    c[idx["ds"]] = depot_small["annualized_capex"] + depot_small["fixed_opex"]
    c[idx["dl"]] = depot_large["annualized_capex"] + depot_large["fixed_opex"]
    c[idx["rs"]] = refinery_small["annualized_capex"] + refinery_small["fixed_opex"]
    c[idx["rl"]] = refinery_large["annualized_capex"] + refinery_large["fixed_opex"]
    for i in range(ns):
        for j in range(nd):
            c[b2d(i, j)] = farm_cost * d_sd[i, j] * 1000 + depot_small["variable_opex"] * 1000
            c[b2dl(i, j)] = (depot_large["variable_opex"] - depot_small["variable_opex"]) * 1000
    for j in range(nd):
        for k in range(nr):
            c[d2r(j, k)] = depot_cost * d_dr[j, k] * 1000 + refinery_small["variable_opex"] * 1000
            c[d2rl(j, k)] = (refinery_large["variable_opex"] - refinery_small["variable_opex"]) * 1000
    for k in range(nr):
        for a in range(na): c[r2a(k, a)] = airport_cost * d_ra[k, a] * 1000

    rows, lbs, ubs = [], [], []
    for i in range(ns):
        add_row(rows, lbs, ubs, {b2d(i, j): 1 for j in range(nd)}, 0, float(sources.iloc[i].production_kilotons) * recovery)
    for j in range(nd):
        add_row(rows, lbs, ubs, {**{b2d(i, j): 1 for i in range(ns)}, **{d2r(j, k): -1 for k in range(nr)}}, 0, 0)
        add_row(rows, lbs, ubs, {**{b2d(i, j): 1 for i in range(ns)}, idx["ds"][j]: -depot_small["capacity_kt"], idx["dl"][j]: -depot_large["capacity_kt"]}, -np.inf, 0)
        add_row(rows, lbs, ubs, {idx["ds"][j]: 1, idx["dl"][j]: 1}, 0, 1)
        add_row(rows, lbs, ubs, {**{b2d(i, j): 1 for i in range(ns)}, idx["ds"][j]: -MIN_FACILITY_UTILIZATION * depot_small["capacity_kt"], idx["dl"][j]: -MIN_FACILITY_UTILIZATION * depot_large["capacity_kt"]}, 0, np.inf)
        for i in range(ns):
            # b2dl is exactly b2d when the depot is large, and zero otherwise.
            M = float(sources.iloc[i].production_kilotons) * recovery
            add_row(rows, lbs, ubs, {b2dl(i, j): 1, b2d(i, j): -1}, -np.inf, 0)
            add_row(rows, lbs, ubs, {b2dl(i, j): 1, idx["dl"][j]: -depot_large["capacity_kt"]}, -np.inf, 0)
            add_row(rows, lbs, ubs, {b2d(i, j): 1, b2dl(i, j): -1, idx["dl"][j]: M}, -np.inf, M)
    for k in range(nr):
        # Refinery capacity is biomass intake; yield converts intake into SAF output.
        add_row(rows, lbs, ubs, {**{d2r(j, k): -YIELD for j in range(nd)}, **{r2a(k, a): 1 for a in range(na)}}, 0, 0)
        add_row(rows, lbs, ubs, {**{d2r(j, k): 1 for j in range(nd)}, idx["rs"][k]: -refinery_small["capacity_kt"], idx["rl"][k]: -refinery_large["capacity_kt"]}, -np.inf, 0)
        add_row(rows, lbs, ubs, {idx["rs"][k]: 1, idx["rl"][k]: 1}, 0, 1)
        add_row(rows, lbs, ubs, {**{d2r(j, k): 1 for j in range(nd)}, idx["rs"][k]: -MIN_FACILITY_UTILIZATION * refinery_small["capacity_kt"], idx["rl"][k]: -MIN_FACILITY_UTILIZATION * refinery_large["capacity_kt"]}, 0, np.inf)
        for j in range(nd):
            M = float(depot_large["capacity_kt"])
            add_row(rows, lbs, ubs, {d2rl(j, k): 1, d2r(j, k): -1}, -np.inf, 0)
            add_row(rows, lbs, ubs, {d2rl(j, k): 1, idx["rl"][k]: -refinery_large["capacity_kt"]}, -np.inf, 0)
            add_row(rows, lbs, ubs, {d2r(j, k): 1, d2rl(j, k): -1, idx["rl"][k]: M}, -np.inf, M)
    for a, airport in airports.iterrows():
        # Airport demand is an upper bound. A separate system-wide requirement
        # prevents the positive-cost objective from choosing the trivial zero-flow solution.
        add_row(rows, lbs, ubs, {r2a(k, a): 1 for k in range(nr)}, 0, float(airport.saf_demand_kt_per_year))
    add_row(rows, lbs, ubs, {r2a(k, a): 1 for k in range(nr) for a in range(na)},
            float(airports.saf_demand_kt_per_year.sum()), np.inf)

    A = lil_matrix((len(rows), nvars), dtype=float)
    for r, terms in enumerate(rows):
        for col, value in terms.items(): A[r, col] = value
    integrality = np.zeros(nvars); binary = np.concatenate([idx["ds"], idx["dl"], idx["rs"], idx["rl"]]); integrality[binary] = 1
    lower = np.zeros(nvars); upper = np.full(nvars, np.inf); upper[binary] = 1
    return {"c": c, "A": A.tocsr(), "lb": np.array(lbs), "ub": np.array(ubs), "integrality": integrality, "lower": lower, "upper": upper, "idx": idx, "d_sd": d_sd, "d_dr": d_dr, "d_ra": d_ra, "sources": sources, "depots": depots, "refineries": refineries}


def solve(model):
    return milp(c=model["c"], integrality=model["integrality"], bounds=Bounds(model["lower"], model["upper"]), constraints=LinearConstraint(model["A"], model["lb"], model["ub"]), options={"time_limit": TIME_LIMIT_SECONDS})


def extract(result, model, airports, recovery):
    if result.x is None: return None
    x = result.x; idx = model["idx"]; sources = model["sources"]; depots = model["depots"]; refs = model["refineries"]; nr = len(refs); na = len(airports)
    def b2d(i, j): return idx["b2d"][i * len(depots) + j]
    def d2r(j, k): return idx["d2r"][j * nr + k]
    def r2a(k, a): return idx["r2a"][k * na + a]
    depots_out=[]; refs_out=[]
    for j,r in depots.iterrows():
        if x[idx["ds"][j]]>.5 or x[idx["dl"][j]]>.5: depots_out.append({"location_id":r.location_id,"size":"large" if x[idx["dl"][j]]>.5 else "small","lat":r.latitude,"lon":r.longitude})
    for k,r in refs.iterrows():
        if x[idx["rs"][k]]>.5 or x[idx["rl"][k]]>.5: refs_out.append({"location_id":r.location_id,"size":"large" if x[idx["rl"][k]]>.5 else "small","lat":r.latitude,"lon":r.longitude})
    routes={"biomass_to_depot":[],"depot_to_refinery":[],"refinery_to_airport":[]}
    for i,s in sources.iterrows():
        for j,d in depots.iterrows():
            f=x[b2d(i,j)]
            if f>1e-3: routes["biomass_to_depot"].append({"from":s.location_id,"to":d.location_id,"flow_kt":f,"distance_km":model["d_sd"][i,j]})
    for j,d in depots.iterrows():
        for k,r in refs.iterrows():
            f=x[d2r(j,k)]
            if f>1e-3: routes["depot_to_refinery"].append({"from":d.location_id,"to":r.location_id,"flow_kt":f,"distance_km":model["d_dr"][j,k]})
    delivered={}
    for a,ap in airports.iterrows():
        delivered[ap.iata]=0
        for k,r in refs.iterrows():
            f=x[r2a(k,a)]; delivered[ap.iata]+=f
            if f>1e-3: routes["refinery_to_airport"].append({"from":r.location_id,"to":ap.iata,"flow_kt":f,"distance_km":model["d_ra"][k,a],"mode":"barge" if ap.iata=="TRK" else "truck"})
    return {"recovery":recovery,"yield":YIELD,"road_factor":ROAD_FACTOR,"objective_usd":float(result.fun),"status":int(result.status),"message":str(result.message),"depots":depots_out,"refineries":refs_out,"routes":routes,"saf_delivered":delivered,"biomass_processed_kt":sum(r["flow_kt"] for r in routes["biomass_to_depot"]),"candidate_mode":FACILITY_CANDIDATE_MODE}


def make_map(solution, biomass, airports, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    def great_circle_points(lat1, lon1, lat2, lon2, n=40):
        # Spherical interpolation for a visually honest route arc; optimization still
        # uses the corresponding great-circle distance multiplied by ROAD_FACTOR.
        p1 = np.radians([lat1, lon1]); p2 = np.radians([lat2, lon2])
        v1 = np.array([np.cos(p1[0])*np.cos(p1[1]), np.cos(p1[0])*np.sin(p1[1]), np.sin(p1[0])])
        v2 = np.array([np.cos(p2[0])*np.cos(p2[1]), np.cos(p2[0])*np.sin(p2[1]), np.sin(p2[0])])
        omega = np.arccos(np.clip(np.dot(v1, v2), -1, 1))
        t = np.linspace(0, 1, n)
        if omega < 1e-10: v = np.repeat(v1[None, :], n, axis=0)
        else: v = (np.sin((1-t)*omega)[:,None]*v1 + np.sin(t*omega)[:,None]*v2) / np.sin(omega)
        return np.degrees(np.arcsin(v[:,2])), np.degrees(np.arctan2(v[:,1], v[:,0]))
    fig, ax = plt.subplots(figsize=(14,9)); ax.set_facecolor("#B8D5EA")
    # Real province boundaries from GADM, filtered to the five Kalimantan provinces.
    # This is a visual overlay only; it is not used as an optimization land mask.
    boundary_path = DATA / "indonesia_provinces.geojson"
    if boundary_path.exists():
        with boundary_path.open() as f: geo = json.load(f)
        kal = [f for f in geo["features"] if "kalimantan" in str(f.get("properties", {}).get("NAME_1", "")).lower()]
        for feature in kal:
            geom = feature["geometry"]
            polygons = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
            for rings in polygons:
                ax.add_patch(Polygon(rings[0], closed=True, facecolor="#E8E0C8", edgecolor="#7D6B4F", linewidth=0.8, zorder=0))
    else:
        # Fallback only if the downloaded public boundary is unavailable.
        land=[(108.4,-1.2),(109.0,1.4),(110.0,3.0),(112.0,4.0),(114.8,4.2),(117.8,4.0),(119.2,2.0),(119.0,-1.0),(117.5,-3.0),(116.0,-4.5),(113.0,-4.4),(111.0,-3.5),(109.5,-2.5)]
        ax.add_patch(Polygon(land,closed=True,facecolor="#E8E0C8",edgecolor="#7D6B4F",linewidth=1.5,zorder=0))
    land_bio = biomass[biomass.on_land]
    sea_bio = biomass[~biomass.on_land]
    ax.scatter(land_bio.longitude,land_bio.latitude,s=18,c="#607D8B",alpha=.55,label="Biomass sites (land)",zorder=2)
    if not sea_bio.empty:
        ax.scatter(sea_bio.longitude,sea_bio.latitude,s=42,c="#D32F2F",marker="x",label="Offshore source coordinate — excluded as facility site",zorder=3)
    for route in solution["routes"]["biomass_to_depot"]+solution["routes"]["depot_to_refinery"]: 
        a=biomass[biomass.location_id==route["from"]].iloc[0]; b=biomass[biomass.location_id==route["to"]].iloc[0]; y,x=great_circle_points(a.latitude,a.longitude,b.latitude,b.longitude); ax.plot(x,y,c="#EF6C00",alpha=.35,lw=.6,zorder=1)
    for route in solution["routes"]["refinery_to_airport"]:
        r=biomass[biomass.location_id==route["from"]].iloc[0]; a=airports[airports.iata==route["to"]].iloc[0]; y,x=great_circle_points(r.latitude,r.longitude,a.latitude,a.longitude); ax.plot(x,y,c="#1565C0",alpha=.65,lw=1.5,zorder=1)
    d=pd.DataFrame(solution["depots"]); rr=pd.DataFrame(solution["refineries"])
    if not d.empty: ax.scatter(d.lon,d.lat,marker="s",s=120,c="#2E7D32",edgecolor="white",label="Depot",zorder=4)
    if not rr.empty: ax.scatter(rr.lon,rr.lat,marker="^",s=170,c="#C62828",edgecolor="white",label="Refinery",zorder=5)
    ax.scatter(airports.longitude,airports.latitude,marker="o",s=150,c="#6A1B9A",edgecolor="white",label="Airport",zorder=6)
    for a in airports.itertuples(): ax.annotate(a.iata,(a.longitude,a.latitude),xytext=(5,5),textcoords="offset points",fontweight="bold")
    ax.set_xlim(108,120); ax.set_ylim(-5,5); ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude"); ax.grid(alpha=.2)
    ax.set_title(f"Updated Challenge 3 network | recovery {solution['recovery']:.0%} | 20% yield | {ROAD_FACTOR:.1f}× distance\nKalimantan province boundaries aligned from GADM — no protected-area or land-use exclusion applied",fontweight="bold")
    ax.legend(loc="lower left"); fig.tight_layout(); fig.savefig(path,dpi=180,bbox_inches="tight"); plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True); biomass, airports, facilities, transport = load_inputs(); results={}
    for recovery in RECOVERY_SCENARIOS:
        start=time.time(); model=build_model(biomass,airports,facilities,transport,recovery); result=solve(model); sol=extract(result,model,airports,recovery)
        if sol: sol["solve_time_s"]=time.time()-start
        results[str(recovery)]=sol; print(f"recovery={recovery:.0%}: {'feasible' if sol else 'infeasible'}" + (f" cost=${sol['objective_usd']/1e6:.2f}M" if sol else ""))
    (OUT/"updated_results.json").write_text(json.dumps(results,indent=2)); biomass.to_csv(OUT/"biomass_used.csv",index=False)
    for key,sol in results.items():
        if sol: make_map(sol,biomass,airports,OUT/f"network_recovery_{key.replace('.', '')}.png")
    print(f"Wrote {len([x for x in results.values() if x])} maps to {OUT}")


if __name__ == "__main__": main()
