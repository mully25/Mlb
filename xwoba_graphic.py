"""
MLB Top 10 stat graphic – Instagram-ready (1080x1350)
Usage: python3 xwoba_graphic.py [photo.jpg] [stat]

  stat options:
    xwoba  (default) – Expected Weighted On-Base Average
    ba               – Batting Average
    xba              – Expected Batting Average
    slg              – Slugging Percentage
    xslg             – Expected Slugging Percentage
    woba             – Weighted On-Base Average
"""
import sys, io, requests, pandas as pd, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from datetime import date

# ── Stat config ──────────────────────────────────────────────────────────────
STAT_CONFIG = {
    "xwoba": {"col": "est_woba", "title": "xwOBA LEADERS",       "footer": "Statcast xwOBA",          "fmt": lambda v: f".{int(round(v*1000)):03d}"},
    "ba":    {"col": "ba",       "title": "BATTING AVG LEADERS",  "footer": "Batting Average",          "fmt": lambda v: f".{int(round(v*1000)):03d}"},
    "xba":   {"col": "est_ba",   "title": "xBA LEADERS",          "footer": "Statcast xBA",             "fmt": lambda v: f".{int(round(v*1000)):03d}"},
    "slg":   {"col": "slg",      "title": "SLUGGING LEADERS",     "footer": "Slugging Percentage",      "fmt": lambda v: f".{int(round(v*1000)):03d}"},
    "xslg":  {"col": "est_slg",  "title": "xSLG LEADERS",         "footer": "Statcast xSLG",            "fmt": lambda v: f".{int(round(v*1000)):03d}"},
    "woba":  {"col": "woba",     "title": "wOBA LEADERS",         "footer": "Weighted On-Base Average", "fmt": lambda v: f".{int(round(v*1000)):03d}"},
}

# ── Layout ──────────────────────────────────────────────────────────────────
W, H       = 1080, 1350
IMAGE_PATH = sys.argv[1] if len(sys.argv) > 1 else None
STAT_KEY   = sys.argv[2].lower() if len(sys.argv) > 2 else "xwoba"
if STAT_KEY not in STAT_CONFIG:
    print(f"Unknown stat '{STAT_KEY}'. Options: {', '.join(STAT_CONFIG)}")
    sys.exit(1)
STAT = STAT_CONFIG[STAT_KEY]

# ── Fonts ───────────────────────────────────────────────────────────────────
F = "/usr/share/fonts/truetype/open-sans/"
def font(name, size):
    return ImageFont.truetype(F + name, size)

# ── Colors ──────────────────────────────────────────────────────────────────
BG         = (6,  9, 14)
PANEL      = (12, 16, 24)
WHITE      = (255, 255, 255)
LIGHT      = (200, 210, 225)
DIM        = (95, 108, 125)
ACCENT_RED = (196, 30, 58)

TEAM_COLORS = {
    "Houston Astros":       (235, 110,  31),
    "Detroit Tigers":       (245,  70,  22),
    "Los Angeles Angels":   (186,   0,  33),
    "Los Angeles Dodgers":  ( 28, 108, 220),
    "New York Yankees":     ( 62, 116, 196),
    "Seattle Mariners":     (  0, 145, 135),
    "Washington Nationals": (171,   0,   3),
    "Milwaukee Brewers":    (198, 162,  48),
}

# ── Helpers ──────────────────────────────────────────────────────────────────
def tw(draw, text, fnt):
    bb = draw.textbbox((0, 0), text, font=fnt, anchor="lt")
    return bb[2] - bb[0]

def th(draw, text, fnt):
    bb = draw.textbbox((0, 0), text, font=fnt, anchor="lt")
    return bb[3] - bb[1]

def put(draw, text, x, y, fnt, color):
    draw.text((x, y), text, font=fnt, fill=color, anchor="lt")

def put_center_x(draw, text, cx, y, fnt, color):
    put(draw, text, cx - tw(draw, text, fnt) // 2, y, fnt, color)

# ── Gradient overlay: solid on left, fade to transparent on right ────────────
def side_gradient(width, height, color_rgb, solid_until=0.52, fade_end=0.90):
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    arr[:, :, :3] = color_rgb
    xs = np.arange(width, dtype=float)
    alpha = np.where(
        xs / width <= solid_until, 255,
        np.where(
            xs / width >= fade_end, 0,
            255 * (1 - (xs / width - solid_until) / (fade_end - solid_until))
        )
    ).astype(np.uint8)
    arr[:, :, 3] = alpha[np.newaxis, :]
    return Image.fromarray(arr, "RGBA")

# ── Fetch data ───────────────────────────────────────────────────────────────
def fetch_top10():
    import time
    url = "https://baseballsavant.mlb.com/expected_statistics"
    params = {"type":"batter","year":"2026","position":"","team":"","min":"q","csv":"true"}
    headers = {"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    for attempt in range(5):
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 200 and "last_name" in resp.text:
            break
        wait = 2 ** attempt
        print(f"  Baseball Savant returned {resp.status_code}, retrying in {wait}s…")
        time.sleep(wait)
    resp.raise_for_status()
    text = resp.text.lstrip('﻿')
    df = pd.read_csv(io.StringIO(text))
    df.columns = df.columns.str.strip()
    nc = df.columns[0]
    df[["last","first"]] = df[nc].str.split(", ", n=1, expand=True)
    df["name"]  = df["first"].str.strip() + " " + df["last"].str.strip()
    df["val"]   = pd.to_numeric(df[STAT["col"]].astype(str).str.strip(), errors="coerce")
    top10 = df.nlargest(10, "val").reset_index(drop=True)
    top10["rank"] = range(1, 11)
    return top10

def fetch_team(pid):
    import time
    for attempt in range(3):
        try:
            r = requests.get(
                f"https://statsapi.mlb.com/api/v1/people/{pid}/stats"
                f"?stats=gameLog&season=2026&group=hitting",
                headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
            splits = r.json().get("stats", [{}])
            if splits and splits[0].get("splits"):
                return splits[0]["splits"][-1].get("team", {}).get("name", "Unknown")
            return "Unknown"
        except Exception:
            if attempt < 2:
                time.sleep(1.5)
    return "Unknown"

# ── Build ────────────────────────────────────────────────────────────────────
def build(top10, output=None):
    if output is None:
        output = f"/home/user/Mlb/{STAT_KEY}_top10.png"
    canvas = Image.new("RGBA", (W, H), (*BG, 255))

    # ── right side: player photo ─────────────────────────────────────────
    if IMAGE_PATH:
        import math
        photo = Image.open(IMAGE_PATH).convert("RGB")
        pw, ph = photo.size
        new_w = math.ceil(pw * H / ph)
        photo = photo.resize((new_w, H), Image.LANCZOS)
        photo = ImageEnhance.Brightness(photo).enhance(0.80)
        if new_w > W:
            cx = (new_w - W) // 2
            photo = photo.crop((cx, 0, cx + W, H))
            paste_x = 0
        else:
            paste_x = W - new_w
        canvas.paste(photo.convert("RGBA"), (paste_x, 0))

    # ── dark gradient overlay (left panel) ───────────────────────────────
    grad = side_gradient(W, H, BG, solid_until=0.50, fade_end=0.88)
    canvas.paste(grad, (0, 0), grad)

    d = ImageDraw.Draw(canvas)

    # ── top accent stripe ─────────────────────────────────────────────────
    d.rectangle([0, 0, W, 7], fill=(*ACCENT_RED, 255))

    # ── header ───────────────────────────────────────────────────────────
    ML = 54          # margin left
    y  = 36

    # "TOP 10" on one line using two colors
    f_big = font("OpenSans-ExtraBold.ttf", 100)
    top_w = tw(d, "TOP ", f_big)
    put(d, "TOP ", ML, y, f_big, WHITE)
    put(d, "10",  ML + top_w, y, f_big, ACCENT_RED)
    y += th(d, "TOP 10", f_big) + 4

    # subtitle
    f_sub = font("OpenSans-Bold.ttf", 38)
    put(d, STAT["title"], ML, y, f_sub, LIGHT)
    y += th(d, "x", f_sub) + 14

    # red rule
    d.rectangle([ML, y, ML + 520, y + 3], fill=(*ACCENT_RED, 255))
    y += 16

    # season label
    f_lbl = font("OpenSans-Semibold.ttf", 24)
    today = date.today().strftime("%-m/%-d/%y")
    put(d, f"2026 MLB Season  ·  Qualified Batters  ·  As of {today}", ML, y, f_lbl, DIM)
    y += th(d, "x", f_lbl) + 36

    # ── player rows ───────────────────────────────────────────────────────
    # distribute remaining space evenly across 10 rows
    FOOTER_H = 52
    available = H - y - FOOTER_H - 10
    ROW_H    = available // 10          # ~93px per row
    PILL_R   = 14                       # pill corner radius
    PAD_X    = 16                       # horizontal text padding inside pill
    PAD_Y    = 9                        # vertical text padding inside pill

    f_rank  = font("OpenSans-ExtraBold.ttf", 36)
    f_name  = font("OpenSans-Bold.ttf", 31)
    f_stat  = font("OpenSans-ExtraBold.ttf", 38)

    RANK_COL_W = 64
    STAT_COL_W = 96
    MAX_NAME_W = 380

    for i, row in top10.iterrows():
        rank  = int(row["rank"])
        name  = row["name"]
        xwoba = row["val"]
        team  = row.get("team", "Unknown")
        color = TEAM_COLORS.get(team, (70, 80, 95))

        row_top = y + i * ROW_H
        row_bot = row_top + ROW_H
        mid_y   = (row_top + row_bot) // 2

        # thin divider between rows
        if i > 0:
            d.line([(ML, row_top), (int(W * 0.60), row_top)],
                   fill=(28, 34, 46, 200), width=1)

        # rank number
        rank_str   = f"#{rank}"
        rank_color = (245, 200, 24) if rank == 1 else ACCENT_RED if rank <= 3 else DIM
        rw = tw(d, rank_str, f_rank)
        rh = th(d, rank_str, f_rank)
        put(d, rank_str, ML + (RANK_COL_W - rw) // 2, mid_y - rh // 2, f_rank, rank_color)

        # pill: truncate name to fit
        pill_x = ML + RANK_COL_W + 10
        name_fnt = f_name
        for size in range(31, 17, -1):
            name_fnt = font("OpenSans-Bold.ttf", size)
            if tw(d, name, name_fnt) <= MAX_NAME_W - PAD_X * 2:
                break
        display = name

        name_w_px = tw(d, display, name_fnt)
        name_h_px = th(d, display, name_fnt)
        pill_w = name_w_px + PAD_X * 2
        pill_h = name_h_px + PAD_Y * 2
        pill_y = mid_y - pill_h // 2

        # drop shadow
        sh = 4
        d.rounded_rectangle(
            [pill_x + sh, pill_y + sh, pill_x + pill_w + sh, pill_y + pill_h + sh],
            radius=PILL_R, fill=(*tuple(max(0, c - 70) for c in color), 120))
        # pill body
        d.rounded_rectangle(
            [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
            radius=PILL_R, fill=(*color, 255))
        # name text centered inside pill
        put(d, display, pill_x + PAD_X, pill_y + PAD_Y, name_fnt, WHITE)

        # stat value
        stat_str = STAT["fmt"](xwoba)
        sx = pill_x + pill_w + 16
        sh2 = th(d, stat_str, f_stat)
        put(d, stat_str, sx, mid_y - sh2 // 2, f_stat, WHITE)

    # ── footer ───────────────────────────────────────────────────────────
    fy = H - FOOTER_H
    d.rectangle([0, fy, W, H], fill=(*PANEL, 255))
    d.rectangle([0, fy, W, fy + 2], fill=(*ACCENT_RED, 255))
    f_foot = font("OpenSans-Regular.ttf", 21)
    foot_text = f"Data: baseballsavant.mlb.com  ·  {STAT['footer']}  ·  Qualified PA"
    put(d, foot_text, ML, fy + (FOOTER_H - th(d, "x", f_foot)) // 2, f_foot, DIM)

    # ── save ──────────────────────────────────────────────────────────────
    out = canvas.convert("RGB")
    out.save(output, "PNG")
    print(f"Saved → {output}")

# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Fetching {STAT['title']}…")
    top10 = fetch_top10()

    print("Fetching team data…")
    teams = []
    for _, row in top10.iterrows():
        team = fetch_team(int(row["player_id"]))
        teams.append(team)
        print(f"  {row['name']:<25} → {team}")
    top10["team"] = teams

    print("\nBuilding graphic…")
    build(top10)
