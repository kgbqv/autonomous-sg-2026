"""Create a qualitative protected-area reference overlay for the updated model."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parent
data = ROOT / "data"
out = ROOT / "outputs"
out.mkdir(exist_ok=True)

biomass = pd.read_csv(data / "biomass.csv")
airports = pd.read_csv(data / "challenge3_airports_4.csv")
reference = Image.open(data / "kalimantan_protected_areas_reference.png")

fig, ax = plt.subplots(figsize=(14, 9))
ax.scatter(biomass.longitude, biomass.latitude, s=22, color="#607D8B", alpha=0.65, label="Biomass source sites", zorder=3)
ax.scatter(airports.longitude, airports.latitude, s=150, color="#6A1B9A", edgecolor="white", linewidth=1.5, label="SAF demand airports", zorder=4)
for row in airports.itertuples():
    ax.annotate(row.iata, (row.longitude, row.latitude), xytext=(6, 5), textcoords="offset points", fontweight="bold")

ax.set_title("Kalimantan facility-candidate context\nProtected-area/concession figure shown as qualitative reference only", fontsize=15, fontweight="bold")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.grid(alpha=0.25)
ax.legend(loc="lower left")

# Inset rather than a geospatial blend: the supplied paper figure is a raster
# image with historical map layers, not a georeferenced GIS mask.
inset = fig.add_axes([0.55, 0.54, 0.39, 0.30])
inset.imshow(reference)
inset.axis("off")
inset.patch.set_edgecolor("black")
inset.patch.set_linewidth(1.5)
fig.text(0.55, 0.515, "Historical land-use reference — Gaveau et al. (2013)", fontsize=9, fontweight="bold")

fig.text(0.02, 0.02, "No protected-area exclusion is applied. Facilities remain free to locate anywhere in the candidate space for this version.", fontsize=10, color="#8E0000")
fig.tight_layout(rect=[0, 0.04, 1, 1])
fig.savefig(out / "protected_area_reference_overlay.png", dpi=180, bbox_inches="tight")
plt.close(fig)
