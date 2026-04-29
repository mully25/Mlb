"""
MLB Top 10 stat graphic – Instagram-ready (1080x1350)

Usage:
  python3 mlb_graphic.py [photo.jpg] [stat]

Stat options:
  xwoba   Expected Weighted On-Base Average  (default)
  ba      Batting Average  (with xBA shown alongside)
  obp     On-Base Percentage
  slg     Slugging Percentage
  woba    Weighted On-Base Average
"""
import sys, io, os, time, requests, pandas as pd, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from datetime import date, datetime
from zoneinfo import ZoneInfo

# ── Stat config ───────────────────────────────────────────────────────────────
#  col       – primary sort/display column
#  secondary – (optional) companion column shown next to primary
#  sec_label – short label for the secondary value
#  title     – graphic subtitle
#  footer    – footer descriptor
#  endpoint  – "expected" or "custom"
#  custom_sel– Baseball Savant custom-leaderboard selections key (if custom)
#  fmt       – value formatter

def _avg(v):
    return f".{int(round(v * 1000)):03d}"

STAT_CONFIG = {
    # col       = primary sort/display column in the CSV
    # secondary = companion expected-stat column
    # sec_label = short label shown before expected value
    # diff_col  = API column for (expected - actual); we negate it to get actual - expected
    # endpoint  = "expected" | "custom"
    # custom_sel= Baseball Savant selections key when endpoint="custom"
    "xwoba": {
        "col": "est_woba",  "secondary": None,       "diff_col": None,
        "title": "xwOBA LEADERS",         "footer": "Statcast xwOBA",
        "endpoint": "expected",           "fmt": _avg,
    },
    "ba": {
        "col": "ba",        "secondary": "est_ba",   "sec_label": "xBA",
        "diff_col": "est_ba_minus_ba_diff",
        "title": "BATTING AVG LEADERS",   "footer": "Batting Average  ·  xBA  ·  Diff",
        "endpoint": "expected",           "fmt": _avg,
    },
    "obp": {
        "col": "on_base_percent", "secondary": None, "diff_col": None,
        "title": "OBP LEADERS",           "footer": "On-Base Percentage  ·  (no Statcast xOBP)",
        "endpoint": "custom",
        "custom_sel": "on_base_percent",  "fmt": _avg,
    },
    "slg": {
        "col": "slg",       "secondary": "est_slg",  "sec_label": "xSLG",
        "diff_col": "est_slg_minus_slg_diff",
        "title": "SLUGGING LEADERS",      "footer": "Slugging Percentage  ·  xSLG  ·  Diff",
        "endpoint": "expected",           "fmt": _avg,
    },
    "woba": {
        "col": "woba",      "secondary": "est_woba", "sec_label": "xwOBA",
        "diff_col": "est_woba_minus_woba_diff",
        "title": "wOBA LEADERS",          "footer": "wOBA  ·  xwOBA  ·  Diff",
        "endpoint": "expected",           "fmt": _avg,
    },
}

# ── CLI args ──────────────────────────────────────────────────────────────────
IMAGE_PATH = sys.argv[1] if len(sys.argv) > 1 else None
STAT_KEY   = sys.argv[2].lower() if len(sys.argv) > 2 else "xwoba"
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
    "Minnesota Twins":        (  0,  43, 92),
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

def get_season_games():
    try:
        r = requests.get(
            "https://statsapi.mlb.com/api/v1/standings",
            params={"leagueId": "103,104", "season": "2026"},
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        gp = [t.get("gamesPlayed", 0)
              for div in r.json().get("records", [])
              for t in div.get("teamRecords", [])]
        return max(gp) if gp else 162
    except Exception:
        return 162

def fetch_top10():
    games   = get_season_games()
    min_pa  = int(3.1 * games)
    if STAT["endpoint"] == "expected":
        text = _get("https://baseballsavant.mlb.com/expected_statistics",
                    {"type":"batter","year":"2026","position":"","team":"","min":"1","csv":"true"})
        df = pd.read_csv(io.StringIO(text.lstrip('﻿')))
        df.columns = df.columns.str.strip()
        nc = df.columns[0]
        df[["last","first"]] = df[nc].str.split(", ", n=1, expand=True)
        df["name"] = df["first"].str.strip() + " " + df["last"].str.strip()
        df["val"]  = pd.to_numeric(df[STAT["col"]].astype(str).str.strip(), errors="coerce")
        df["bip"]  = pd.to_numeric(df["bip"], errors="coerce")
        df["pa"]   = pd.to_numeric(df["pa"],  errors="coerce")
        df = df[df["pa"] >= min_pa]
        if STAT.get("secondary"):
            df["sec_val"] = pd.to_numeric(df[STAT["secondary"]].astype(str).str.strip(), errors="coerce")
        if STAT.get("diff_col"):
            # API stores (expected - actual); negate so positive = outperforming
            df["diff_val"] = pd.to_numeric(df[STAT["diff_col"]].astype(str).str.strip(), errors="coerce") * -1
    else:
        # custom leaderboard (OBP etc.) — add pa to selections so we can filter
        sel = STAT["custom_sel"] + ",pa"
        text = _get("https://baseballsavant.mlb.com/leaderboard/custom",
                    {"year":"2026","type":"batter","filter":"","min":"1",
                     "selections": sel,
                     "chart":"false","x":STAT["custom_sel"],"y":STAT["custom_sel"],
                     "r":"no","chartType":"bbs","csv":"true"})
        df = pd.read_csv(io.StringIO(text.lstrip('﻿')))
        df.columns = df.columns.str.strip()
        nc = df.columns[0]
        df["last"]  = df[nc].str.split(", ").str[0].str.strip()
        df["first"] = df[nc].str.split(", ").str[1].str.strip()
        df["name"]  = df["first"] + " " + df["last"]
        df["val"]   = pd.to_numeric(df[STAT["col"]].astype(str).str.strip(), errors="coerce")
        df["pa"]    = pd.to_numeric(df["pa"],  errors="coerce")
        df = df[df["pa"] >= min_pa]

    top10 = df.nlargest(10, "val").reset_index(drop=True)
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
                              f"?stats=gameLog&season=2026&group=hitting",
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

    HAS_SEC  = bool(STAT.get("secondary") and "sec_val" in top10.columns)
    HAS_DIFF = bool(STAT.get("diff_col") and "diff_val" in top10.columns)

    canvas = Image.new("RGBA", (W, H), (*BG, 255))

    # photo on right
    if IMAGE_PATH:
        photo = Image.open(IMAGE_PATH).convert("RGB")
        pw, ph = photo.size
        scale  = max(W / pw, H / ph)
        new_w  = int(pw * scale)
        new_h  = int(ph * scale)
        photo  = photo.resize((new_w, new_h), Image.LANCZOS)
        photo  = ImageEnhance.Brightness(photo).enhance(0.95)
        canvas.paste(photo.convert("RGBA"), ((W - new_w) // 2, (H - new_h) // 2))

    # gradient overlay
    grad = side_gradient(W, H, BG, solid_until=0.42, fade_end=0.72)
    canvas.paste(grad, (0, 0), grad)

    d = ImageDraw.Draw(canvas)


    # ── header ────────────────────────────────────────────────────────────
    ML = 54
    y  = 36
    f_big = font("OpenSans-ExtraBold.ttf", 100)
    top_w = tw(d, "TOP ", f_big)
    put(d, "TOP ", ML, y, f_big, WHITE)
    put(d, "10",  ML + top_w, y, f_big, ACCENT_RED)
    y += th(d, "TOP 10", f_big) + 4

    f_sub = font("OpenSans-Bold.ttf", 38)
    put(d, STAT["title"], ML, y, f_sub, WHITE)
    y += th(d, "x", f_sub) + 14

    d.rectangle([ML, y, ML + 520, y + 3], fill=(*ACCENT_RED, 255))
    y += 16

    f_lbl = font("OpenSans-Semibold.ttf", 24)
    today = datetime.now(ZoneInfo("America/New_York")).strftime("%-m/%-d/%y")
    put(d, f"2026 MLB Season  ·  Qualified PA  ·  As of {today}", ML, y, f_lbl, DIM)
    y += th(d, "x", f_lbl) + 36

    # ── player rows ───────────────────────────────────────────────────────
    FOOTER_H = 0
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
    MAX_NAME_W = 310 if HAS_SEC else 380

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

        # rank badge
        rank_str   = f"#{rank}"
        rank_color = (245, 200, 24) if rank == 1 else ACCENT_RED if rank <= 3 else DIM
        rw = tw(d, rank_str, f_rank)
        rh = th(d, rank_str, f_rank)
        put(d, rank_str, ML + (RANK_COL_W - rw) // 2, mid_y - rh // 2, f_rank, rank_color)

        # player name pill
        pill_x   = ML + RANK_COL_W + 10
        # scale font down until full name fits — never truncate
        name_fnt = f_name
        for size in range(31, 17, -1):
            name_fnt = font("OpenSans-Bold.ttf", size)
            if tw(d, name, name_fnt) <= MAX_NAME_W - PAD_X * 2:
                break
        display = name

        nw  = tw(d, display, name_fnt)
        nh  = th(d, display, name_fnt)
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
        put(d, display, pill_x + PAD_X, py + PAD_Y, name_fnt, WHITE)

        # stat value(s)
        sx = pill_x + pw2 + 16

        if HAS_SEC:
            primary_str = STAT["fmt"](val)
            sec_val     = row.get("sec_val", float("nan"))
            diff_val    = row.get("diff_val", float("nan"))
            sec_str     = STAT["fmt"](sec_val) if pd.notna(sec_val) else "—"
            lbl_str     = STAT.get("sec_label", "")

            # diff string and color
            if pd.notna(diff_val):
                sign      = "+" if diff_val >= 0 else ""
                diff_str  = f"{sign}{diff_val:+.3f}".replace("+", "+").lstrip()
                diff_str  = f"{sign}{abs(diff_val):.3f}"
                diff_str  = ("+" if diff_val >= 0 else "-") + f"{abs(diff_val):.3f}"
                diff_color = GREEN if diff_val >= 0 else RED
            else:
                diff_str, diff_color = "", DIM2

            # layout: two lines stacked
            # line 1: primary value (large)
            # line 2: xLABEL value   ±diff
            gap     = 3
            line1_h = th(d, primary_str, f_stat)
            line2_h = th(d, lbl_str, f_seclbl)
            total_h = line1_h + gap + line2_h
            top_y   = mid_y - total_h // 2

            put(d, primary_str, sx, top_y, f_stat, WHITE)

            line2_y = top_y + line1_h + gap
            lbl_w   = tw(d, lbl_str + " ", f_seclbl)
            put(d, lbl_str, sx, line2_y + 3, f_seclbl, DIM2)
            put(d, sec_str, sx + lbl_w, line2_y, f_sec, LIGHT)

            if diff_str:
                diff_x = sx + lbl_w + tw(d, sec_str, f_sec) + 10
                put(d, diff_str, diff_x, line2_y + 2, f_diff, diff_color)
        else:
            sv  = STAT["fmt"](val)
            sh2 = th(d, sv, f_stat)
            put(d, sv, sx, mid_y - sh2 // 2, f_stat, WHITE)

    canvas.convert("RGB").save(output, "PNG")
    print(f"Saved → {output}")

PHOTOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "photos")

def _normalize(s):
    import unicodedata
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()

def leader_photo(name, pid=None):
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    for ext in ("jpg", "jpeg", "png", "webp"):
        p = os.path.join(PHOTOS_DIR, f"{name}.{ext}")
        if os.path.exists(p):
            return p
    # accent-insensitive fallback — matches "Nasim Nunez" to "Nasim Nuñez"
    norm_name = _normalize(name)
    for fname in os.listdir(PHOTOS_DIR):
        stem, dot, fext = fname.rpartition(".")
        if fext.lower() in ("jpg", "jpeg", "png", "webp") and _normalize(stem) == norm_name:
            return os.path.join(PHOTOS_DIR, fname)
    # auto-download MLB headshot if we have a player_id (skipped in CI)
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
