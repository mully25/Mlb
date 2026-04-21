import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
import matplotlib.patheffects as pe
import io
import warnings
warnings.filterwarnings("ignore")

# ── fetch data ────────────────────────────────────────────────────────────────
url = "https://baseballsavant.mlb.com/leaderboard/custom"
params = {
    "year": "2026",
    "type": "batter",
    "filter": "",
    "min": "q",
    "selections": "xwoba",
    "chart": "false",
    "x": "xwoba",
    "y": "xwoba",
    "r": "no",
    "chartType": "bbs",
    "csv": "true",
}
headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}

resp = requests.get(url, params=params, headers=headers, timeout=30)
resp.raise_for_status()

df = pd.read_csv(io.StringIO(resp.text))
df.columns = df.columns.str.strip()

name_col = df.columns[0]
df[["last_name", "first_name"]] = df[name_col].str.split(", ", n=1, expand=True)
df["name"] = df["first_name"].str.strip() + " " + df["last_name"].str.strip()
df["xwoba"] = df["xwoba"].astype(str).str.strip().astype(float)

top10 = df.nlargest(10, "xwoba").reset_index(drop=True)
top10["rank"] = range(1, 11)

print("Top 10 xwOBA leaders (2026 season):")
for _, row in top10.iterrows():
    print(f"  {row['rank']:2d}. {row['name']:<25s}  {row['xwoba']:.3f}")

# ── palette ───────────────────────────────────────────────────────────────────
BG     = "#0d1117"
PANEL  = "#161b22"
ACCENT = "#c41e3a"
GOLD   = "#f5c518"
TEXT   = "#e6edf3"
SUBTEXT = "#8b949e"

# rank 1 = deepest blue, rank 10 = lighter
bar_colors = [
    "#1565C0",  # rank 1
    "#1976D2",
    "#1E88E5",
    "#2196F3",
    "#42A5F5",
    "#64B5F6",
    "#90CAF9",
    "#BBDEFB",
    "#DDEEFF",
    "#EEF6FF",  # rank 10
]

# text colour: dark text on light bars, white on dark bars
def text_color(hex_color):
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#0d1117" if luminance > 0.55 else "#ffffff"

# ── figure layout ─────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(14, 9), facecolor=BG)

# axes: leave generous left margin for rank + name labels
ax = fig.add_axes([0.03, 0.09, 0.94, 0.72])
ax.set_facecolor(PANEL)

players = top10["name"].tolist()
values  = top10["xwoba"].tolist()
ranks   = top10["rank"].tolist()

# rank 1 at top → highest y_pos value
y_pos = list(range(10, 0, -1))

x_min = 0.27
x_max = max(values) + 0.03

for i, (y, val, color, name, rank) in enumerate(
        zip(y_pos, values, bar_colors, players, ranks)):

    tc = text_color(color)

    # draw bar
    ax.barh(y, val - x_min, left=x_min, color=color,
            height=0.68, zorder=3, linewidth=0)

    # rank badge (always left-anchored just inside bar start)
    rank_clr = GOLD if rank == 1 else ACCENT if rank <= 3 else SUBTEXT
    ax.text(x_min + 0.006, y, f"#{rank}",
            va="center", ha="left", fontsize=10.5, fontweight="bold",
            color=rank_clr, zorder=5)

    # player name
    ax.text(x_min + 0.042, y, name,
            va="center", ha="left", fontsize=11, fontweight="bold",
            color=tc, zorder=5)

    # xwOBA value at right end of bar
    ax.text(val + 0.004, y, f"{val:.3f}",
            va="center", ha="left", fontsize=11, fontweight="bold",
            color=TEXT, zorder=5)

# ── axes cosmetics ─────────────────────────────────────────────────────────
ax.set_xlim(x_min, x_max)
ax.set_ylim(0.4, 10.6)
ax.set_yticks(y_pos)
ax.set_yticklabels([])
ax.tick_params(axis="x", colors=SUBTEXT, labelsize=9, pad=6)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_visible(False)
ax.spines["bottom"].set_color("#30363d")
ax.set_xlabel("Expected Weighted On-Base Average (xwOBA)",
               color=SUBTEXT, fontsize=10, labelpad=8)
ax.xaxis.grid(True, color="#21262d", linewidth=0.8, zorder=0)
ax.set_axisbelow(True)

# faint separator lines
for y in y_pos[:-1]:
    ax.axhline(y - 0.5, color="#21262d", linewidth=0.5, zorder=1)

# ── header ─────────────────────────────────────────────────────────────────
fig.text(0.03, 0.95, "TOP 10 xwOBA LEADERS",
         fontsize=24, fontweight="black", color=TEXT, va="top")
fig.text(0.03, 0.895,
         "2026 MLB Season  •  Qualified Batters  •  Via Baseball Savant",
         fontsize=11, color=SUBTEXT, va="top")

# red accent line under subtitle
line = mpatches.FancyArrowPatch(
    (0.03, 0.878), (0.60, 0.878),
    transform=fig.transFigure,
    arrowstyle="-", color=ACCENT, linewidth=2.5, zorder=10)
fig.add_artist(line)

# MLB badge top-right
fig.text(0.97, 0.955, "MLB", fontsize=28, fontweight="black",
         color=ACCENT, va="top", ha="right")
fig.text(0.97, 0.900, "STATCAST", fontsize=10, fontweight="bold",
         color=SUBTEXT, va="top", ha="right")

# footer
fig.text(0.5, 0.018,
         "Minimum plate appearances to qualify  •  Data: baseballsavant.mlb.com",
         fontsize=8.5, color=SUBTEXT, ha="center", va="bottom")

out = "/home/user/Mlb/xwoba_top10.png"
plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=BG, edgecolor="none")
print(f"\nSaved: {out}")
