"""
MLB Top 10 pitching stat graphic – Instagram-ready (1080x1350)
Ranks by lowest ERA or xERA; shows the other + diff as secondary.

Usage: python3 pitching_graphic.py [photo.jpg] [stat]

  stat options:
    era    (default) – ERA leaders  (shows xERA + diff)
    xera             – xERA leaders (shows ERA + diff)
"""
import sys, io, os, time, requests, pandas as pd, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from datetime import date

# ── Stat config ───────────────────────────────────────────────────────────────
def _era(v):
    return f"{v:.2f}"

STAT_CONFIG = {
    "era": {
        "col": "era",   "secondary": "xera",  "sec_label": "xERA",
        "diff_col": "era_minus_xera_diff",
        "title": "ERA LEADERS",    "footer": "ERA  ·  xERA  ·  Diff",
    },
    "xera": {
        "col": "xera",  "secondary": "era",   "sec_label": "ERA",
        "diff_col": "era_minus_xera_diff",
        "title": "xERA LEADERS",   "footer": "xERA  ·  ERA  ·  Diff",
    },
}

# ── CLI args ──────────────────────────────────────────────────────────────────
IMAGE_PATH = sys.argv[1] if len(sys.argv) > 1 else None
STAT_KEY   = sys.argv[2].lower() if len(sys.argv) > 2 else "era"
if STAT_KEY not in STAT_CONFIG:
    print(f"Unknown stat '{STAT_KEY}'. Options: {', '.join(STAT_CONFIG)}")
    sys.exit(1)
STAT = STAT_CONFIG[STAT_KEY]

# ── Dimensions ────────────────────────────────────────────────────────────────
W, H = 1080, 1350

# ── Fonts ─────────────────────────────────────────────────────────────────────
FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts") + "/"
def font(name, size):
    return ImageFont.truetype(FD + name, size)

# ── Colors ────────────────────────────────────────────────────────────────────
BG         = (6,  9, 14)
PANEL      = (12, 16, 24)
WHITE      = (255, 255, 255)
LIGHT      = (200, 210, 225)
DIM        = (95, 108, 125)
DIM2       = (130, 145, 165)
ACCENT_RED = (196, 30, 58)

TEAM_COLORS = {
    "Houston Astros":         (235, 110,  31),
    "Detroit Tigers":         (245,  70,  22),
    "Los Angeles Angels":     (186,   0,  33),
    "Los Angeles Dodgers":    ( 28, 108, 220),
    "New York Yankees":       ( 12,  35,  64),
    "Seattle Mariners":       (  0, 145, 135),
    "Washington Nationals":   (171,   0,   3),
    "Milwaukee Brewers":      (198, 162,  48),
    "Minnesota Twins":        (  0,  43,  92),
    "Atlanta Braves":         (206,  17,  65),
    "Chicago Cubs":           ( 14,  51, 134),
    "Arizona Diamondbacks":   (167,  25,  48),
    "New York Mets":          (  0,  45, 114),
    "Toronto Blue Jays":      ( 19,  74, 142),
    "Miami Marlins":          (  0, 163, 224),
    "Athletics":              (  0,  56,  49),
    "Boston Red Sox":         (189,  48,  57),
    "San Francisco Giants":   (253,  90,  30),
    "Chicago White Sox":      ( 39,  37,  31),
    "Cincinnati Reds":        (198,   1,  31),
    "Cleveland Guardians":    ( 12,  35,  64),
    "Colorado Rockies":       ( 51,   0, 111),
    "Kansas City Royals":     (  0,  70, 135),
    "Pittsburgh Pirates":     (253, 184,  39),
    "San Diego Padres":       ( 47,  36,  29),
    "St. Louis Cardinals":    (196,  30,  58),
    "Tampa Bay Rays":         (  9,  44,  92),
    "Texas Rangers":          (  0,  50, 120),
    "Philadelphia Phillies":  (232,  24,  40),
    "Baltimore Orioles":      (223,  70,   1),
}

# ── Drawing helpers ───────────────────────────────────────────────────────────
def tw(d, text, fnt):
    bb = d.textbbox((0, 0), text, font=fnt, anchor="lt")
    return bb[2] - bb[0]

def th(d, text, fnt):
    bb = d.textbbox((0, 0), text, font=fnt, anchor="lt")
    return bb[3] - bb[1]

def put(d, text, x, y, fnt, color):
    d.text((x, y), text, font=fnt, fill=color, anchor="lt")

# ── Gradient ──────────────────────────────────────────────────────────────────
def side_gradient(width, height, color_rgb, solid_until=0.52, fade_end=0.90):
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    arr[:, :, :3] = color_rgb
    xs = np.arange(width, dtype=float)
    alpha = np.where(
        xs / width <= solid_until, 255,
        np.where(xs / width >= fade_end, 0,
                 255 * (1 - (xs / width - solid_until) / (fade_end - solid_until)))
    ).astype(np.uint8)
    arr[:, :, 3] = alpha[np.newaxis, :]
    return Image.fromarray(arr, "RGBA")

# ── Data fetching ─────────────────────────────────────────────────────────────
def _get(url, params):
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    for attempt in range(8):
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 200 and "last_name" in resp.text:
            return resp.text
        wait = min(2 ** attempt, 120)
        print(f"  Savant returned {resp.status_code}, retrying in {wait}s…")
        time.sleep(wait)
    resp.raise_for_status()

def fetch_top10():
    text = _get("https://baseballsavant.mlb.com/expected_statistics",
                {"type":"pitcher","year":"2026","position":"","team":"","min":"q","csv":"true"})
    df = pd.read_csv(io.StringIO(text.lstrip('﻿')))
    df.columns = df.columns.str.strip()
    nc = df.columns[0]
    df[["last","first"]] = df[nc].str.split(", ", n=1, expand=True)
    df["name"]    = df["first"].str.strip() + " " + df["last"].str.strip()
    df["val"]     = pd.to_numeric(df[STAT["col"]].astype(str).str.strip(), errors="coerce")
    df["sec_val"] = pd.to_numeric(df[STAT["secondary"]].astype(str).str.strip(), errors="coerce")
    # era_minus_xera_diff = ERA - xERA; negate so positive = outperforming (ERA < xERA)
    df["diff_val"] = pd.to_numeric(df[STAT["diff_col"]].astype(str).str.strip(), errors="coerce") * -1
    # for xera ranking, diff should be xERA - ERA = already negated correctly
    if STAT_KEY == "xera":
        df["diff_val"] = df["diff_val"] * -1  # flip back: positive = ERA < xERA still outperforming
    # require meaningful sample: 50+ BIP and ERA > 0
    df["bip"] = pd.to_numeric(df["bip"], errors="coerce")
    df = df[(df["bip"] >= 50) & (df["val"] > 0)]
    top10 = df.nsmallest(10, "val").reset_index(drop=True)
    top10["rank"] = range(1, 11)
    return top10

def fetch_team(pid):
    headers = {"User-Agent": "Mozilla/5.0"}
    for attempt in range(3):
        try:
            r = requests.get(f"https://statsapi.mlb.com/api/v1/people/{pid}?hydrate=currentTeam",
                             headers=headers, timeout=10)
            team = r.json().get("people", [{}])[0].get("currentTeam", {}).get("name", "")
            if team:
                return team
            r2 = requests.get(f"https://statsapi.mlb.com/api/v1/people/{pid}/stats"
                              f"?stats=gameLog&season=2026&group=pitching",
                              headers=headers, timeout=10)
            splits = r2.json().get("stats", [{}])
            if splits and splits[0].get("splits"):
                return splits[0]["splits"][-1].get("team", {}).get("name", "Unknown")
            return "Unknown"
        except Exception:
            if attempt < 2:
                time.sleep(1.5)
    return "Unknown"

# ── Graphic builder ───────────────────────────────────────────────────────────
def build(top10, output=None):
    if output is None:
        output = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{STAT_KEY}_top10.png")

    canvas = Image.new("RGBA", (W, H), (*BG, 255))

    if IMAGE_PATH:
        photo = Image.open(IMAGE_PATH).convert("RGB")
        pw, ph = photo.size
        new_w  = int(pw * H / ph)
        photo  = photo.resize((new_w, H), Image.LANCZOS)
        photo  = ImageEnhance.Brightness(photo).enhance(0.95)
        canvas.paste(photo.convert("RGBA"), (W - new_w + 50, 0))

    grad = side_gradient(W, H, BG, solid_until=0.42, fade_end=0.72)
    canvas.paste(grad, (0, 0), grad)

    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, W, 7], fill=(*ACCENT_RED, 255))

    # ── header ────────────────────────────────────────────────────────────
    ML = 54
    y  = 36
    f_big = font("OpenSans-ExtraBold.ttf", 100)
    top_w = tw(d, "TOP ", f_big)
    put(d, "TOP ", ML, y, f_big, WHITE)
    put(d, "10",  ML + top_w, y, f_big, ACCENT_RED)
    y += th(d, "TOP 10", f_big) + 4

    f_sub = font("OpenSans-Bold.ttf", 38)
    put(d, STAT["title"], ML, y, f_sub, LIGHT)
    y += th(d, "x", f_sub) + 14

    d.rectangle([ML, y, ML + 520, y + 3], fill=(*ACCENT_RED, 255))
    y += 16

    f_lbl = font("OpenSans-Semibold.ttf", 24)
    today = date.today().strftime("%-m/%-d/%y")
    put(d, f"Baseball Savant  ·  Qualified SP  ·  As of {today}", ML, y, f_lbl, DIM)
    y += th(d, "x", f_lbl) + 36

    # ── player rows ───────────────────────────────────────────────────────
    FOOTER_H = 52
    ROW_H    = (H - y - FOOTER_H - 10) // 10
    PILL_R   = 14
    PAD_X    = 16
    PAD_Y    = 9

    f_rank   = font("OpenSans-ExtraBold.ttf", 36)
    f_name   = font("OpenSans-Bold.ttf", 31)
    f_stat   = font("OpenSans-ExtraBold.ttf", 38)
    f_sec    = font("OpenSans-Bold.ttf", 24)
    f_seclbl = font("OpenSans-Semibold.ttf", 19)
    f_diff   = font("OpenSans-Bold.ttf", 22)

    GREEN = (80, 220, 120)
    RED   = (230, 80,  80)

    RANK_COL_W = 64
    MAX_NAME_W = 310

    for i, row in top10.iterrows():
        rank  = int(row["rank"])
        name  = row["name"]
        val   = row["val"]
        team  = row.get("team", "Unknown")
        color = TEAM_COLORS.get(team, (70, 80, 95))

        row_top = y + i * ROW_H
        row_bot = row_top + ROW_H
        mid_y   = (row_top + row_bot) // 2

        if i > 0:
            d.line([(ML, row_top), (int(W * 0.60), row_top)],
                   fill=(28, 34, 46, 200), width=1)

        rank_str   = f"#{rank}"
        rank_color = (245, 200, 24) if rank == 1 else ACCENT_RED if rank <= 3 else DIM
        rw = tw(d, rank_str, f_rank)
        rh = th(d, rank_str, f_rank)
        put(d, rank_str, ML + (RANK_COL_W - rw) // 2, mid_y - rh // 2, f_rank, rank_color)

        pill_x   = ML + RANK_COL_W + 10
        name_fnt = f_name
        for size in range(31, 17, -1):
            name_fnt = font("OpenSans-Bold.ttf", size)
            if tw(d, name, name_fnt) <= MAX_NAME_W - PAD_X * 2:
                break

        nw  = tw(d, name, name_fnt)
        nh  = th(d, name, name_fnt)
        pw2 = nw + PAD_X * 2
        ph2 = nh + PAD_Y * 2
        py  = mid_y - ph2 // 2

        sh = 4
        d.rounded_rectangle(
            [pill_x + sh, py + sh, pill_x + pw2 + sh, py + ph2 + sh],
            radius=PILL_R, fill=(*tuple(max(0, c - 70) for c in color), 120))
        d.rounded_rectangle(
            [pill_x, py, pill_x + pw2, py + ph2],
            radius=PILL_R, fill=(*color, 255))
        put(d, name, pill_x + PAD_X, py + PAD_Y, name_fnt, WHITE)

        sx       = pill_x + pw2 + 16
        sec_val  = row.get("sec_val", float("nan"))
        diff_val = row.get("diff_val", float("nan"))
        lbl_str  = STAT["sec_label"]
        sec_str  = _era(sec_val) if pd.notna(sec_val) else "—"

        if pd.notna(diff_val):
            diff_str  = ("+" if diff_val >= 0 else "-") + f"{abs(diff_val):.2f}"
            diff_color = GREEN if diff_val >= 0 else RED
        else:
            diff_str, diff_color = "", DIM2

        gap     = 3
        line1_h = th(d, _era(val), f_stat)
        line2_h = th(d, lbl_str, f_seclbl)
        total_h = line1_h + gap + line2_h
        top_y   = mid_y - total_h // 2

        put(d, _era(val), sx, top_y, f_stat, WHITE)

        line2_y = top_y + line1_h + gap
        lbl_w   = tw(d, lbl_str + " ", f_seclbl)
        put(d, lbl_str, sx, line2_y + 3, f_seclbl, DIM2)
        put(d, sec_str, sx + lbl_w, line2_y, f_sec, LIGHT)

        if diff_str:
            diff_x = sx + lbl_w + tw(d, sec_str, f_sec) + 10
            put(d, diff_str, diff_x, line2_y + 2, f_diff, diff_color)

    # ── footer ────────────────────────────────────────────────────────────
    fy = H - FOOTER_H
    d.rectangle([0, fy, W, H], fill=(*PANEL, 255))
    d.rectangle([0, fy, W, fy + 2], fill=(*ACCENT_RED, 255))
    f_foot = font("OpenSans-Regular.ttf", 21)
    foot   = f"Data: baseballsavant.mlb.com  ·  {STAT['footer']}  ·  Qualified SP"
    put(d, foot, ML, fy + (FOOTER_H - th(d, "x", f_foot)) // 2, f_foot, DIM)

    canvas.convert("RGB").save(output, "PNG")
    print(f"Saved → {output}")

PHOTOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "photos")

def leader_photo(name, pid=None):
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    for ext in ("jpg", "jpeg", "png"):
        p = os.path.join(PHOTOS_DIR, f"{name}.{ext}")
        if os.path.exists(p):
            return p
    if pid and not os.getenv("NO_AUTO_PHOTO"):
        dest = os.path.join(PHOTOS_DIR, f"{name}.jpg")
        try:
            url = f"https://img.mlbstatic.com/mlb-photos/image/upload/w_1000,q_auto:best/v1/people/{pid}/headshot/67/current"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            Image.open(io.BytesIO(r.content)).save(dest)
            print(f"Downloaded photo for {name}")
            return dest
        except Exception as e:
            print(f"Could not fetch photo for {name}: {e}")
    return None

# ── Entry point ───────────────────────────────────────────────────────────────
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

    if not IMAGE_PATH:
        leader = top10.iloc[0]
        auto = leader_photo(leader["name"], int(leader["player_id"]))
        if auto:
            globals()["IMAGE_PATH"] = auto
            print(f"Auto photo: {auto}")

    print("\nBuilding graphic…")
    build(top10)
