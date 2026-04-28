"""
MLB Top 10 counting stat graphic – Instagram-ready (1080x1350)
Covers both batter and pitcher leaderboards.

Usage: python3 counting_graphic.py [photo.jpg] [stat]

  Batter stats:
    hr    – Home Runs
    rbi   – RBIs
    sb    – Stolen Bases
    r     – Runs Scored
    xbh   – Extra Base Hits
    kbat  – Strikeouts (batters)
    war   – WAR (batters)

  Pitcher stats:
    k     – Strikeouts
    w     – Wins
    fip   – FIP  (lowest = best)
    whip  – WHIP (lowest = best)
    warp  – WAR (pitchers)
"""
import sys, io, os, time, requests, pandas as pd, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from datetime import date

# ── Stat config ───────────────────────────────────────────────────────────────
def _int(v):   return str(int(round(v)))
def _f2(v):    return f"{v:.2f}"
def _f1(v):    return f"{v:.1f}"

STAT_CONFIG = {
    # ── batters ──
    "hr":   {"col":"home_run",      "player_type":"batter",  "rank":"largest",  "title":"HOME RUN LEADERS",       "footer":"Home Runs",            "fmt":_int},
    "rbi":  {"col":"b_rbi",         "player_type":"batter",  "rank":"largest",  "title":"RBI LEADERS",            "footer":"RBIs",                  "fmt":_int},
    "sb":   {"col":"b_stolen_base", "player_type":"batter",  "rank":"largest",  "title":"STOLEN BASE LEADERS",    "footer":"Stolen Bases",          "fmt":_int},
    "r":    {"col":"b_runs_scored", "player_type":"batter",  "rank":"largest",  "title":"RUNS LEADERS",           "footer":"Runs Scored",           "fmt":_int},
    "xbh":  {"col":"xbh",           "player_type":"batter",  "rank":"largest",  "title":"EXTRA BASE HIT LEADERS", "footer":"Extra Base Hits",       "fmt":_int},
    "kbat": {"col":"strikeout",     "player_type":"batter",  "rank":"largest",  "title":"STRIKEOUT LEADERS",      "footer":"Strikeouts (Batters)",  "fmt":_int},
    "war":  {"col":"b_war",         "player_type":"batter",  "rank":"largest",  "title":"WAR LEADERS",            "footer":"WAR (Batters)",         "fmt":_f1},
    # ── pitchers ──
    "k":    {"col":"p_strikeout",   "player_type":"pitcher", "rank":"largest",  "title":"STRIKEOUT LEADERS",      "footer":"Pitcher Strikeouts",    "fmt":_int},
    "w":    {"col":"p_win",         "player_type":"pitcher", "rank":"largest",  "title":"WIN LEADERS",            "footer":"Pitcher Wins",          "fmt":_int},
    "fip":  {"col":"p_fip",         "player_type":"pitcher", "rank":"smallest", "title":"FIP LEADERS",            "footer":"FIP (lower = better)",  "fmt":_f2},
    "whip": {"col":"whip",          "player_type":"pitcher", "rank":"smallest", "title":"WHIP LEADERS",           "footer":"WHIP (lower = better)", "fmt":_f2},
    "warp": {"col":"p_war",         "player_type":"pitcher", "rank":"largest",  "title":"WAR LEADERS",            "footer":"WAR (Pitchers)",        "fmt":_f1},
}

# selections to request per player type
BATTER_SELS  = "home_run,b_rbi,b_stolen_base,b_runs_scored,xbh,strikeout,b_war,pa"
PITCHER_SELS = "p_win,p_strikeout,p_era,whip,p_fip,p_war"

# ── CLI args ──────────────────────────────────────────────────────────────────
IMAGE_PATH = sys.argv[1] if len(sys.argv) > 1 else None
STAT_KEY   = sys.argv[2].lower() if len(sys.argv) > 2 else "hr"
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
def side_gradient(width, height, color_rgb, solid_until=0.42, fade_end=0.72):
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
    ptype = STAT["player_type"]
    sels  = BATTER_SELS if ptype == "batter" else PITCHER_SELS
    col   = STAT["col"]
    text  = _get("https://baseballsavant.mlb.com/leaderboard/custom",
                 {"year":"2026","type":ptype,"filter":"","min":"1",
                  "selections":sels,"chart":"false",
                  "x":col,"y":col,"r":"no","chartType":"bbs","csv":"true"})
    df = pd.read_csv(io.StringIO(text.lstrip('﻿')))
    df.columns = df.columns.str.strip()
    nc = df.columns[0]
    df["last"]  = df[nc].str.split(", ").str[0].str.strip()
    df["first"] = df[nc].str.split(", ").str[1].str.strip()
    df["name"]  = df["first"] + " " + df["last"]
    df["val"]   = pd.to_numeric(df[col].astype(str).str.strip(), errors="coerce")
    df = df.dropna(subset=["val"])
    if ptype == "batter":
        games  = get_season_games()
        min_pa = int(3.1 * games)
        df["pa"] = pd.to_numeric(df["pa"], errors="coerce")
        df = df[df["pa"] >= min_pa]
    if STAT["rank"] == "largest":
        top10 = df.nlargest(10, "val").reset_index(drop=True)
    else:
        top10 = df.nsmallest(10, "val").reset_index(drop=True)
    top10["rank"] = range(1, 11)
    return top10

def fetch_team(pid, ptype):
    headers = {"User-Agent": "Mozilla/5.0"}
    for attempt in range(3):
        try:
            # try current team directly first — works even without game log
            r = requests.get(f"https://statsapi.mlb.com/api/v1/people/{pid}?hydrate=currentTeam",
                             headers=headers, timeout=10)
            team = r.json().get("people", [{}])[0].get("currentTeam", {}).get("name", "")
            if team:
                return team
            # fallback: game log
            group = "hitting" if ptype == "batter" else "pitching"
            r2 = requests.get(f"https://statsapi.mlb.com/api/v1/people/{pid}/stats"
                              f"?stats=gameLog&season=2026&group={group}",
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

    grad = side_gradient(W, H, BG)
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
    put(d, STAT["title"], ML, y, f_sub, WHITE)
    y += th(d, "x", f_sub) + 14

    d.rectangle([ML, y, ML + 520, y + 3], fill=(*ACCENT_RED, 255))
    y += 16

    f_lbl = font("OpenSans-Semibold.ttf", 24)
    today = date.today().strftime("%-m/%-d/%y")
    qualifier = "Qualified SP" if STAT["player_type"] == "pitcher" else "Qualified PA"
    put(d, f"Baseball Savant  ·  {qualifier}  ·  As of {today}", ML, y, f_lbl, DIM)
    y += th(d, "x", f_lbl) + 36

    # ── player rows ───────────────────────────────────────────────────────
    FOOTER_H = 52
    ROW_H    = (H - y - FOOTER_H - 10) // 10
    PILL_R   = 14
    PAD_X    = 16
    PAD_Y    = 9

    f_rank = font("OpenSans-ExtraBold.ttf", 36)
    f_name = font("OpenSans-Bold.ttf", 31)
    f_stat = font("OpenSans-ExtraBold.ttf", 44)

    RANK_COL_W = 64
    MAX_NAME_W = 420

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
            d.line([(ML, row_top), (int(W * 0.62), row_top)],
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

        stat_str = STAT["fmt"](val)
        sx  = pill_x + pw2 + 20
        sh2 = th(d, stat_str, f_stat)
        put(d, stat_str, sx, mid_y - sh2 // 2, f_stat, WHITE)

    # ── footer ────────────────────────────────────────────────────────────
    fy = H - FOOTER_H
    d.rectangle([0, fy, W, H], fill=(*PANEL, 255))
    d.rectangle([0, fy, W, fy + 2], fill=(*ACCENT_RED, 255))
    f_foot = font("OpenSans-Regular.ttf", 21)
    foot   = f"Data: baseballsavant.mlb.com  ·  {STAT['footer']}  ·  {qualifier}"
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
        team = fetch_team(int(row["player_id"]), STAT["player_type"])
        teams.append(team)
        print(f"  {row['name']:<25} → {team}")
    top10["team"] = teams

    # auto-select leader photo if no photo was passed on the command line
    if not IMAGE_PATH:
        leader = top10.iloc[0]
        auto = leader_photo(leader["name"], int(leader["player_id"]))
        if auto:
            globals()["IMAGE_PATH"] = auto
            print(f"Auto photo: {auto}")

    print("\nBuilding graphic…")
    build(top10)
