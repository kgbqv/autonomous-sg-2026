#!/usr/bin/env python3
"""Export report-ready facility utilization tables from saved solver outputs."""

import json
from collections import defaultdict

import pandas as pd

import optimize as opt
from free_siting_test import utilization
from config import OUT


def main():
    biomass, airports, facilities, transport = opt.load_inputs()
    baseline = json.loads((OUT / "updated_results.json").read_text())
    rows = []
    for recovery, solution in baseline.items():
        if solution:
            rows.extend([{**row, "recovery": float(recovery), "model": "biomass-site baseline"}
                         for row in utilization(solution, facilities)])
    pd.DataFrame(rows).to_csv(OUT / "baseline_facility_utilization.csv", index=False)
    free = OUT / "free_siting_90_long.json"
    if free.exists():
        solution = json.loads(free.read_text())
        pd.DataFrame([{**row, "recovery": solution["recovery"], "model": "1-degree free-siting grid"}
                      for row in solution["facility_utilization"]]).to_csv(
                          OUT / "free_siting_90_facility_utilization.csv", index=False)
    print("wrote baseline_facility_utilization.csv")


if __name__ == "__main__": main()
