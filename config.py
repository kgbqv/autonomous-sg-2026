from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "outputs"

YIELD = 0.20
ROAD_FACTOR = 1.30
RECOVERY_SCENARIOS = [0.90, 0.95, 1.00]
# Keep the sensitivity sweep bounded for a solo-demo workflow.
TIME_LIMIT_SECONDS = 120
MIN_FACILITY_UTILIZATION = 0.05
FREE_SITING_GRID_DEG = 0.05

# For now, facilities may be selected at any biomass coordinate. This is a
# discrete approximation to the updated instruction that facilities may sit
# anywhere on land in Kalimantan.
FACILITY_CANDIDATE_MODE = "land_only_biomass_coordinates"
