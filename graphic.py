"""
MLB Top 10 graphic — row style
Each row: # | LOGO | SILO | FIRST / LAST | STAT (+ secondary)
Usage:
  python3 graphic.py ba          # single stat
  python3 graphic.py             # generate all stats
"""
import sys, io, os, time, requests
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from zoneinfo import ZoneInfo

# ── Canvas ─────────────────────────────────────────────────────────────────────
W, H  = 1080, 1350
BG    = (13, 13, 18)
WHITE = (255, 255, 255)
RED   = (220, 30, 30)
DIM   = (140, 140, 150)

BASE      = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(BASE, "fonts")
CACHE_DIR = os.path.join(BASE, "_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# ── Formatters ─────────────────────────────────────────────────────────────────
def _int(v):  return str(int(round(float(v))))
def _f2(v):   return f"{float(v):.2f}"
def _avg(v):
    v = float(v)
    return f"{v:.3f}" if v >= 1 else f".{int(round(v * 1000)):03d}"

# ── Stat config ────────────────────────────────────────────────────────────────
# secondary: {"label": "xBA", "col": "est_ba"}  (from Savant expected_statistics)
STAT_CONFIG = {
    # ── hitting ────────────────────────────────────────────────────────────────
    "ba":   {"title": "BATTING AVERAGE LEADERS",  "group": "hitting",  "col": "avg",          "rank": "largest",  "fmt": _avg, "folder": "hitting",
             "secondary": {"label": "xBA",   "col": "est_ba",   "type": "batter"}},
    "obp":  {"title": "ON-BASE % LEADERS",         "group": "hitting",  "col": "obp",          "rank": "largest",  "fmt": _avg, "folder": "hitting"},
    "slg":  {"title": "SLUGGING % LEADERS",        "group": "hitting",  "col": "slg",          "rank": "largest",  "fmt": _avg, "folder": "hitting",
             "secondary": {"label": "xSLG",  "col": "est_slg",  "type": "batter"}},
    "ops":  {"title": "OPS LEADERS",               "group": "hitting",  "col": "ops",          "rank": "largest",  "fmt": _avg, "folder": "hitting"},
    "woba": {"title": "wOBA LEADERS",              "group": "hitting",  "col": "woba",         "rank": "largest",  "fmt": _avg, "folder": "hitting",
             "source": "savant_expected",
             "secondary": {"label": "xwOBA", "col": "est_woba", "type": "batter"}},
    "hr":   {"title": "HOME RUN LEADERS",          "group": "hitting",  "col": "homeRuns",     "rank": "largest",  "fmt": _int, "folder": "hitting"},
    "rbi":  {"title": "RBI LEADERS",               "group": "hitting",  "col": "rbi",          "rank": "largest",  "fmt": _int, "folder": "hitting"},
    "hits": {"title": "HIT LEADERS",               "group": "hitting",  "col": "hits",         "rank": "largest",  "fmt": _int, "folder": "hitting"},
    "sb":   {"title": "STOLEN BASE LEADERS",       "group": "hitting",  "col": "stolenBases",  "rank": "largest",  "fmt": _int, "folder": "hitting"},
    "r":    {"title": "RUNS LEADERS",              "group": "hitting",  "col": "runs",         "rank": "largest",  "fmt": _int, "folder": "hitting"},
    # ── pitching ───────────────────────────────────────────────────────────────
    "era":  {"title": "ERA LEADERS",               "group": "pitching", "col": "era",          "rank": "smallest", "fmt": _f2,  "folder": "pitching", "min_ip": True,
             "secondary": {"label": "xERA",  "col": "xera",     "type": "pitcher"}},
    "whip": {"title": "WHIP LEADERS",              "group": "pitching", "col": "whip",         "rank": "smallest", "fmt": _f2,  "folder": "pitching", "min_ip": True},
    "k":    {"title": "STRIKEOUT LEADERS",         "group": "pitching", "col": "strikeOuts",   "rank": "largest",  "fmt": _int, "folder": "pitching"},
    "w":    {"title": "WIN LEADERS",               "group": "pitching", "col": "wins",         "rank": "largest",  "fmt": _int, "folder": "pitching"},
    "sv":   {"title": "SAVE LEADERS",              "group": "pitching", "col": "saves",        "rank": "largest",  "fmt": _int, "folder": "pitching"},
}

# ── Team hat colors ────────────────────────────────────────────────────────────
TEAM_COLORS = {
    "Arizona Diamondbacks":  (167,  25,  48),
    "Atlanta Braves":        ( 19,  39,  79),
    "Baltimore Orioles":     (223,  70,   1),
    "Boston Red Sox":        ( 12,  35,  64),
    "Chicago Cubs":          ( 14,  51, 134),
    "Chicago White Sox":     ( 39,  37,  31),
    "Cincinnati Reds":       ( 95,   0,  18),
    "Cleveland Guardians":   (  0,  56,  93),
    "Colorado Rockies":      ( 51,   0, 111),
    "Detroit Tigers":        ( 12,  35,  64),
    "Houston Astros":        (  0,  45,  98),
    "Kansas City Royals":    (  0,  70, 135),
    "Los Angeles Angels":    (186,   0,  33),
    "Los Angeles Dodgers":   (  0,  90, 156),
    "Miami Marlins":         (  0, 163, 224),
    "Milwaukee Brewers":     ( 18,  40,  75),
    "Minnesota Twins":       (  0,  43,  92),
    "New York Mets":         (  0,  45, 114),
    "New York Yankees":      ( 12,  35,  64),
    "Athletics":             (  0,  56,  49),
    "Philadelphia Phillies": (232,  24,  40),
    "Pittsburgh Pirates":    ( 55,  42,   0),
    "San Diego Padres":      ( 47,  36,  29),
    "San Francisco Giants":  ( 55,  28,   0),
    "Seattle Mariners":      ( 12,  44,  86),
    "St. Louis Cardinals":   (196,  30,  58),
    "Tampa Bay Rays":        ( 10,  52, 104),
    "Texas Rangers":         (  0,  50, 120),
    "Toronto Blue Jays":     ( 19,  74, 142),
    "Washington Nationals":  ( 20,  34,  90),
}

# Teams whose logo should be recolored to a solid color (R, G, B)
LOGO_TINT = {
    "New York Mets": (255, 92, 0),
}

ESPN_ABBR = {
    "AZ": "ari", "ATL": "atl", "BAL": "bal", "BOS": "bos",
    "CHC": "chc", "CWS": "chw", "CIN": "cin", "CLE": "cle",
    "COL": "col", "DET": "det", "HOU": "hou", "KC":  "kc",
    "LAA": "laa", "LAD": "lad", "MIA": "mia", "MIL": "mil",
    "MIN": "min", "NYM": "nym", "NYY": "nyy", "OAK": "oak",
    "ATH": "oak", "PHI": "phi", "PIT": "pit", "SD":  "sd",
    "SF":  "sf",  "SEA": "sea", "STL": "stl", "TB":  "tb",
    "TEX": "tex", "TOR": "tor", "WSH": "wsh",
}

# ── Helpers ────────────────────────────────────────────────────────────────────
def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS_DIR, name), size)

def put(d, text, x, y, fnt, color):
    d.text((x, y), text, font=fnt, fill=(*color, 255))

def tint_logo(img, color):
    """
    Extract the warm/orange outline pixels, fill their interior, then
    recolor to `color`. Produces a clean solid shape without the fat
    blue-letter layer.
    """
    from scipy.ndimage import binary_fill_holes
    tr, tg, tb = color
    arr = np.array(img, dtype=np.uint8)
    r, g, b, a = arr[...,0].astype(int), arr[...,1].astype(int), arr[...,2].astype(int), arr[...,3]
    # Orange pixels: red dominates over blue
    orange_mask = (r - b > 60) & (a > 10)
    # Fill holes inside the orange outline to get a solid shape
    filled = binary_fill_holes(orange_mask)
    out = np.zeros_like(arr)
    out[filled, 0] = tr
    out[filled, 1] = tg
    out[filled, 2] = tb
    out[filled, 3] = 255
    return Image.fromarray(out, "RGBA")

def fetch_img(url, cache_key):
    path = os.path.join(CACHE_DIR, cache_key)
    if os.path.exists(path):
        return Image.open(path).convert("RGBA")
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        img.save(path, "PNG")
        return img
    except Exception as e:
        print(f"  [fetch] {cache_key}: {e}")
        return None

def get_silo(pid):
    return fetch_img(
        f"https://img.mlbstatic.com/mlb-photos/image/upload/w_1000,q_auto:best/v1/people/{pid}/headshot/silo/current",
        f"silo_{pid}.png")

def get_logo(team_abbrev):
    espn = ESPN_ABBR.get(team_abbrev, team_abbrev.lower())
    return fetch_img(
        f"https://a.espncdn.com/i/teamlogos/mlb/500-dark/{espn}.png",
        f"logo_cap_{espn}.png")

def row_solid(team_color, row_h, row_w):
    r, g, b = team_color
    arr = np.full((row_h, row_w, 4), (r, g, b, 255), dtype=np.uint8)
    return Image.fromarray(arr, "RGBA")

def ensure_silos(players):
    missing = [p for p in players
               if not os.path.exists(os.path.join(CACHE_DIR, f"silo_{p['player_id']}.png"))]
    if not missing:
        return
    print(f"  Downloading {len(missing)} missing silo(s)…")
    for p in missing:
        pid = p["player_id"]
        url = (f"https://img.mlbstatic.com/mlb-photos/image/upload/"
               f"w_1000,q_auto:best/v1/people/{pid}/headshot/silo/current")
        dest = os.path.join(CACHE_DIR, f"silo_{pid}.png")
        for attempt in range(3):
            try:
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
                r.raise_for_status()
                img = Image.open(io.BytesIO(r.content)).convert("RGBA")
                img.save(dest, "PNG")
                print(f"  ✓ {p['name']}")
                break
            except Exception as e:
                wait = 2 ** attempt
                print(f"  attempt {attempt+1} failed for {p['name']}: {e} — retrying in {wait}s")
                time.sleep(wait)
        else:
            print(f"  ✗ Could not download silo for {p['name']}")

# ── Data fetching ──────────────────────────────────────────────────────────────
def season_games():
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

def _parse_ip(ip_str):
    try:
        parts = str(ip_str).split(".")
        return int(parts[0]) + int(parts[1]) / 3 if len(parts) == 2 else float(ip_str)
    except Exception:
        return 0.0

def fetch_top10(stat_key):
    cfg   = STAT_CONFIG[stat_key]
    group = cfg["group"]
    col   = cfg["col"]
    rank  = cfg["rank"]
    hdrs  = {"User-Agent": "Mozilla/5.0"}
    games = season_games()

    if cfg.get("source") == "savant_expected":
        return _fetch_top10_savant(stat_key, games)

    order = "desc" if rank == "largest" else "asc"
    url   = (f"https://bdfed.stitch.mlbinfra.com/bdfed/stats/player"
             f"?stitch_env=prod&season=2026&sportId=1&stats=season"
             f"&group={group}&gameType=R&offset=0&sortStat={col}"
             f"&order={order}&limit=100")
    data  = requests.get(url, headers=hdrs, timeout=15).json()

    rows = []
    for s in data.get("stats", []):
        val = s.get(col)
        if val is None:
            continue
        try:
            val = float(val)
        except (ValueError, TypeError):
            continue

        # Qualification filters
        if group == "hitting":
            min_pa = int(3.1 * games)
            if int(s.get("plateAppearances", 0)) < min_pa:
                continue
        elif cfg.get("min_ip"):
            min_ip = games * 1.0
            if _parse_ip(s.get("inningsPitched", "0")) < min_ip:
                continue

        rows.append({
            "name":        s["playerFullName"],
            "player_id":   int(s["playerId"]),
            "team":        s["teamName"],
            "team_abbrev": s.get("teamAbbrev", ""),
            "val":         val,
        })

    if rank == "smallest":
        rows.sort(key=lambda x: x["val"])
    else:
        rows.sort(key=lambda x: x["val"], reverse=True)

    top10 = rows[:10]

    # Secondary stat (expected version from Savant)
    sec = cfg.get("secondary")
    if sec:
        sec_map = fetch_savant_expected(sec["type"])
        for p in top10:
            p["secondary"] = sec_map.get(p["player_id"])
            p["secondary_label"] = sec["label"]
            p["secondary_col"]   = sec["col"]
    else:
        for p in top10:
            p["secondary"] = None

    return top10


def _fetch_top10_savant(stat_key, games):
    """Fetch wOBA (and similar) from Savant expected_statistics, joined with bdfed for metadata."""
    cfg    = STAT_CONFIG[stat_key]
    col    = cfg["col"]
    hdrs   = {"User-Agent": "Mozilla/5.0"}
    min_pa = int(3.1 * games)

    # Get player metadata (name, team) from bdfed
    bdfed_url = (f"https://bdfed.stitch.mlbinfra.com/bdfed/stats/player"
                 f"?stitch_env=prod&season=2026&sportId=1&stats=season"
                 f"&group=hitting&gameType=R&offset=0&sortStat=avg&order=desc&limit=500")
    bdfed_data = requests.get(bdfed_url, headers=hdrs, timeout=15).json()
    meta = {}
    for s in bdfed_data.get("stats", []):
        pid = int(s["playerId"])
        meta[pid] = {
            "name":        s["playerFullName"],
            "player_id":   pid,
            "team":        s["teamName"],
            "team_abbrev": s.get("teamAbbrev", ""),
            "pa":          int(s.get("plateAppearances", 0)),
        }

    # Get wOBA from Savant
    sav_url = ("https://baseballsavant.mlb.com/expected_statistics"
               f"?type=batter&year=2026&position=&team=&min=1&csv=true")
    r = requests.get(sav_url, headers=hdrs, timeout=20)
    df = pd.read_csv(io.StringIO(r.text.lstrip("\xef\xbb\xbf")))
    df["player_id"] = pd.to_numeric(df["player_id"], errors="coerce")
    df = df.dropna(subset=["player_id", col])

    rows = []
    for _, row in df.iterrows():
        pid = int(row["player_id"])
        if pid not in meta:
            continue
        if meta[pid]["pa"] < min_pa:
            continue
        try:
            val = float(row[col])
        except (ValueError, TypeError):
            continue
        entry = {**meta[pid], "val": val}
        rows.append(entry)

    rows.sort(key=lambda x: x["val"], reverse=True)
    top10 = rows[:10]

    sec = cfg.get("secondary")
    if sec:
        sec_map = fetch_savant_expected(sec["type"])
        for p in top10:
            p["secondary"] = sec_map.get(p["player_id"])
            p["secondary_label"] = sec["label"]
            p["secondary_col"]   = sec["col"]
    else:
        for p in top10:
            p["secondary"] = None

    return top10

def fetch_savant_expected(player_type):
    """Return {player_id: {col: val}} from Savant expected_statistics."""
    try:
        r = requests.get(
            f"https://baseballsavant.mlb.com/expected_statistics"
            f"?type={player_type}&year=2026&position=&team=&min=q&csv=true",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        df = pd.read_csv(io.StringIO(r.text.lstrip("﻿")))
        df["player_id"] = pd.to_numeric(df["player_id"], errors="coerce")
        df = df.dropna(subset=["player_id"])
        result = {}
        for _, row in df.iterrows():
            result[int(row["player_id"])] = row.to_dict()
        return result
    except Exception as e:
        print(f"  Savant expected fetch failed: {e}")
        return {}

# ── Build ──────────────────────────────────────────────────────────────────────
def build(players, stat_key, output=None):
    cfg = STAT_CONFIG[stat_key]
    if output is None:
        folder = cfg["folder"]
        out_dir = os.path.join(BASE, folder)
        os.makedirs(out_dir, exist_ok=True)
        output = os.path.join(out_dir, f"{stat_key}_top10.png")

    canvas = Image.new("RGBA", (W, H), (*BG, 255))
    d      = ImageDraw.Draw(canvas)

    # ── Header ─────────────────────────────────────────────────────────────────
    ML = 44
    y  = 30

    f_title = font("OpenSans-ExtraBold.ttf", 72)
    f_date  = font("OpenSans-Semibold.ttf", 28)

    title_w = int(d.textlength(cfg["title"], font=f_title))
    put(d, cfg["title"], (W - title_w) // 2, y, f_title, WHITE)
    y += f_title.getbbox(cfg["title"])[3] + 10

    today  = datetime.now(ZoneInfo("America/New_York")).strftime("%m/%d/%Y")
    date_w = int(d.textlength(today, font=f_date))
    put(d, today, (W - date_w) // 2, y, f_date, WHITE)
    y += f_date.getbbox(today)[3] + 20

    # ── Player rows ─────────────────────────────────────────────────────────────
    ROW_H   = (H - y - 6) // 10
    LOGO_SZ = 74
    SILO_SZ = ROW_H
    RANK_W  = 54

    f_rank  = font("OpenSans-ExtraBold.ttf", 28)
    f_first = font("OpenSans-Bold.ttf", 22)
    f_last  = font("OpenSans-ExtraBold.ttf", 44)
    f_stat  = font("OpenSans-ExtraBold.ttf", 52)
    f_sec   = font("OpenSans-Semibold.ttf", 22)

    for i, p in enumerate(players):
        ry = y + i * ROW_H
        tc = TEAM_COLORS.get(p["team"], (55, 55, 75))

        canvas.paste(row_solid(tc, ROW_H + 1, W), (0, ry))

        if i > 0:
            sep = Image.new("RGBA", (W, 1), (255, 255, 255, 45))
            canvas.paste(sep, (0, ry), sep)

        cy = ry + ROW_H // 2

        # Rank
        rank_str = f"#{i + 1}"
        rw = int(d.textlength(rank_str, font=f_rank))
        put(d, rank_str, (RANK_W - rw) // 2 + 4, cy - 14, f_rank, WHITE)

        # Logo
        logo = get_logo(p["team_abbrev"])
        if logo:
            tint = LOGO_TINT.get(p["team"])
            if tint:
                logo = tint_logo(logo, tint)
            logo = logo.resize((LOGO_SZ, LOGO_SZ), Image.LANCZOS)
            canvas.paste(logo, (ML + RANK_W, cy - LOGO_SZ // 2), logo)

        # Silo
        silo = get_silo(p["player_id"])
        if silo:
            silo = silo.resize((SILO_SZ, SILO_SZ), Image.LANCZOS)
            canvas.paste(silo, (ML + RANK_W + LOGO_SZ + 8, ry), silo)

        # Name
        parts   = p["name"].split(" ", 1)
        first   = parts[0].upper()
        last    = parts[1].upper() if len(parts) > 1 else ""
        nx      = ML + RANK_W + LOGO_SZ + 8 + SILO_SZ + 8
        block_h = 22 + 6 + 44
        ny      = cy - block_h // 2
        put(d, first, nx, ny,      f_first, WHITE)
        put(d, last,  nx, ny + 28, f_last,  WHITE)

        # Stat + optional secondary
        stat_str = cfg["fmt"](p["val"])
        sec_val  = p.get("secondary")
        sec_col  = p.get("secondary_col")
        sec_lbl  = p.get("secondary_label", "")

        if sec_val is not None and sec_col and sec_col in sec_val:
            sec_num    = float(sec_val[sec_col])
            sec_str    = f"{sec_lbl}: " + (_avg(sec_num) if sec_num < 2 else _f2(sec_num))
            stat_blk_h = f_stat.getbbox(stat_str)[3] + 6 + f_sec.getbbox(sec_str)[3]
            sy         = cy - stat_blk_h // 2
            sw         = int(d.textlength(stat_str, font=f_stat))
            put(d, stat_str, W - 48 - sw, sy, f_stat, WHITE)
            xw = int(d.textlength(sec_str, font=f_sec))
            put(d, sec_str, W - 48 - xw, sy + f_stat.getbbox(stat_str)[3] + 4, f_sec, WHITE)
        else:
            sw = int(d.textlength(stat_str, font=f_stat))
            put(d, stat_str, W - 48 - sw, cy - f_stat.getbbox(stat_str)[3] // 2, f_stat, WHITE)

    canvas.convert("RGB").save(output, "PNG")
    print(f"  Saved → {output}")


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    keys = sys.argv[1:] if len(sys.argv) > 1 else list(STAT_CONFIG.keys())

    for stat_key in keys:
        if stat_key not in STAT_CONFIG:
            print(f"Unknown stat: {stat_key}. Options: {list(STAT_CONFIG.keys())}")
            continue
        print(f"\n{'─'*40}")
        print(f"Fetching {STAT_CONFIG[stat_key]['title']}…")
        players = fetch_top10(stat_key)
        for p in players:
            print(f"  {p['name']:<25}  {STAT_CONFIG[stat_key]['fmt'](p['val']):<8}  ({p['team']})")
        ensure_silos(players)
        build(players, stat_key)
