"""
MLB Top 10 graphic — row style
Each row: # | LOGO | SILO | FIRST / LAST | STAT (+ secondary)
Usage:
  python3 graphic.py ba          # single stat
  python3 graphic.py             # generate all stats
"""
import sys, io, os, time, json, requests
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
GREEN = (50, 205, 50)
ROSE  = (235, 70, 70)

BASE      = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(BASE, "fonts")
CACHE_DIR = os.path.join(BASE, "_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# ── Formatters ─────────────────────────────────────────────────────────────────
def _int(v):  return str(int(round(float(v))))
def _f1(v):   return f"{float(v):.1f}"
def _f2(v):   return f"{float(v):.2f}"
def _avg(v):
    v = float(v)
    return f"{v:.3f}" if v >= 1 else f".{int(round(v * 1000)):03d}"

# ── Stat config ────────────────────────────────────────────────────────────────
# secondary: {"label": "xBA", "col": "est_ba"}  (from Savant expected_statistics)
STAT_CONFIG = {
    # ── hitting ────────────────────────────────────────────────────────────────
    "ba":   {"title": "BATTING AVERAGE LEADERS",  "group": "hitting",  "mlb_cat": "battingAverage",            "rank": "largest",  "fmt": _avg, "folder": "hitting",
             "secondary": {"label": "xBA",   "col": "est_ba",   "type": "batter"}},
    "obp":  {"title": "ON-BASE % LEADERS",        "group": "hitting",  "mlb_cat": "onBasePercentage",          "rank": "largest",  "fmt": _avg, "folder": "hitting"},
    "slg":  {"title": "SLUGGING % LEADERS",       "group": "hitting",  "mlb_cat": "sluggingPercentage",        "rank": "largest",  "fmt": _avg, "folder": "hitting",
             "secondary": {"label": "xSLG",  "col": "est_slg",  "type": "batter"}},
    "ops":  {"title": "OPS LEADERS",              "group": "hitting",  "mlb_cat": "onBasePlusSlugging",        "rank": "largest",  "fmt": _avg, "folder": "hitting"},
    "woba": {"title": "wOBA LEADERS",             "group": "hitting",  "rank": "largest",  "fmt": _avg, "folder": "hitting",
             "source": "savant_expected", "col": "woba",
             "secondary": {"label": "xwOBA", "col": "est_woba", "type": "batter"}},
    "hr":   {"title": "HOME RUN LEADERS",         "group": "hitting",  "mlb_cat": "homeRuns",                  "rank": "largest",  "fmt": _int, "folder": "hitting"},
    "rbi":  {"title": "RBI LEADERS",              "group": "hitting",  "mlb_cat": "runsBattedIn",              "rank": "largest",  "fmt": _int, "folder": "hitting"},
    "hits": {"title": "HIT LEADERS",              "group": "hitting",  "mlb_cat": "hits",                      "rank": "largest",  "fmt": _int, "folder": "hitting"},
    "sb":   {"title": "STOLEN BASE LEADERS",      "group": "hitting",  "mlb_cat": "stolenBases",               "rank": "largest",  "fmt": _int, "folder": "hitting"},
    "r":    {"title": "RUNS LEADERS",             "group": "hitting",  "mlb_cat": "runs",                      "rank": "largest",  "fmt": _int, "folder": "hitting"},
    "hwar": {"title": "POSITION PLAYER WAR LEADERS", "group": "hitting", "rank": "largest", "fmt": _f1, "folder": "hitting",
             "source": "bref_war", "bref_type": "bat"},
    # ── pitching ───────────────────────────────────────────────────────────────
    "era":  {"title": "ERA LEADERS",              "group": "pitching", "mlb_cat": "earnedRunAverage",          "rank": "smallest", "fmt": _f2,  "folder": "pitching",
             "secondary": {"label": "xERA",  "col": "xera",     "type": "pitcher"}},
    "whip": {"title": "WHIP LEADERS",             "group": "pitching", "mlb_cat": "walksAndHitsPerInningPitched", "rank": "smallest", "fmt": _f2, "folder": "pitching"},
    "k":    {"title": "STRIKEOUT LEADERS",        "group": "pitching", "mlb_cat": "strikeouts",                "rank": "largest",  "fmt": _int, "folder": "pitching"},
    "w":    {"title": "WIN LEADERS",              "group": "pitching", "mlb_cat": "wins",                      "rank": "largest",  "fmt": _int, "folder": "pitching"},
    "sv":   {"title": "SAVE LEADERS",             "group": "pitching", "mlb_cat": "saves",                     "rank": "largest",  "fmt": _int, "folder": "pitching"},
    "k9":   {"title": "K/9 LEADERS",             "group": "pitching", "mlb_cat": "strikeoutsPer9Inn",          "rank": "largest",  "fmt": _f2,  "folder": "pitching"},
    "fip":  {"title": "FIP LEADERS",             "group": "pitching", "rank": "smallest", "fmt": _f2,  "folder": "pitching",
             "source": "bdfed_computed_fip"},
    "baa":  {"title": "BAA LEADERS",             "group": "pitching", "mlb_cat": "battingAverage",             "rank": "smallest", "fmt": _avg, "folder": "pitching",
             "secondary": {"label": "xBA",   "col": "est_ba",   "type": "pitcher"}},
    "pwar": {"title": "PITCHER WAR LEADERS",     "group": "pitching", "rank": "largest", "fmt": _f1, "folder": "pitching",
             "source": "bref_war", "bref_type": "pit"},
}

# ── Team hat colors ────────────────────────────────────────────────────────────
TEAM_COLORS = {
    "Arizona Diamondbacks":  (167,  25,  48),
    "Atlanta Braves":        ( 19,  39,  79),   # #13274F
    "Baltimore Orioles":     (223,  70,   1),   # #DF4601
    "Boston Red Sox":        ( 12,  35,  64),   # #0C2340
    "Chicago Cubs":          ( 14,  51, 134),   # #0E3386
    "Chicago White Sox":     ( 39,  37,  31),   # #27251F
    "Cincinnati Reds":       (198,   1,  31),   # #C6011F
    "Cleveland Guardians":   (204,   0,  36),   # #CC0024 red (swapped)
    "Colorado Rockies":      ( 51,   0, 111),   # #33006F
    "Detroit Tigers":        (  0,  30,  98),   # #001E62
    "Houston Astros":        (  0,  45,  98),   # #002D62
    "Kansas City Royals":    (  0,  70, 135),   # #004687
    "Los Angeles Angels":    (186,   0,  33),   # #BA0021
    "Los Angeles Dodgers":   (  0,  90, 156),   # #005A9C
    "Miami Marlins":         (  0, 119, 200),   # #0077C8
    "Milwaukee Brewers":     ( 18,  40,  75),   # #12264B
    "Minnesota Twins":       (  0,  43,  92),   # #002B5C
    "New York Mets":         (  0,  45, 114),   # #002D72
    "New York Yankees":      ( 19,  36,  72),   # #132448
    "Athletics":             (  0,  56,  49),   # #003831
    "Philadelphia Phillies": (232,  24,  40),   # #E81828
    "Pittsburgh Pirates":    ( 39,  37,  31),   # #27251F
    "San Diego Padres":      ( 47,  36,  29),   # #2F241D
    "San Francisco Giants":  ( 55,  28,   0),
    "Seattle Mariners":      ( 12,  44,  86),   # #0C2C56
    "St. Louis Cardinals":   (196,  30,  58),   # #C41E3A
    "Tampa Bay Rays":        (  9,  44,  92),   # #092C5C
    "Texas Rangers":         (  0,  50, 120),   # #003278
    "Toronto Blue Jays":     ( 19,  74, 142),   # #134A8E
    "Washington Nationals":  (171,   0,   3),   # #AB0003
}

# Teams whose logo should be recolored to a solid color (R, G, B)
LOGO_TINT = {
    "Cincinnati Reds":     (255, 255, 255),
    "Cleveland Guardians": (255, 255, 255),
    "St. Louis Cardinals": (255, 255, 255),
}

LOGO_OUTLINE = set()

# Erode alpha mask before tinting to thin thick-stroked logos
LOGO_ERODE = {
    "St. Louis Cardinals": 6,
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

def outline_logo(img, thickness=4):
    """Add a white outline around a logo by dilating its alpha mask."""
    from scipy.ndimage import binary_dilation
    arr    = np.array(img, dtype=np.uint8)
    alpha  = arr[..., 3] > 50
    dilated = binary_dilation(alpha, iterations=thickness)
    out    = arr.copy()
    border = dilated & ~alpha
    out[border, 0] = 255
    out[border, 1] = 255
    out[border, 2] = 255
    out[border, 3] = 255
    return Image.fromarray(out, "RGBA")

def tint_logo(img, color, erode=0):
    """Replace all visible pixels with `color`; optionally erode mask first to thin strokes."""
    from scipy.ndimage import binary_erosion
    tr, tg, tb = color
    arr = np.array(img, dtype=np.uint8)
    mask = arr[..., 3] > 50
    if erode > 0:
        mask = binary_erosion(mask, iterations=erode)
    out = np.zeros_like(arr)
    out[mask, 0] = tr
    out[mask, 1] = tg
    out[mask, 2] = tb
    out[mask, 3] = 255
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
    img = fetch_img(
            f"https://a.espncdn.com/i/teamlogos/mlb/500-dark/{espn}.png",
            f"logo_cap_{espn}.png")
    if img is None:
        return None
    # Crop transparent padding so every logo scales to the same apparent size
    arr = np.array(img)
    mask = arr[..., 3] > 10
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    return img.crop((cmin, rmin, cmax + 1, rmax + 1))

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

def _bdfed_meta(group="hitting", limit=500):
    """Return {playerId: {name, team, team_abbrev, pa, ip}} from bdfed."""
    sort = "avg" if group == "hitting" else "era"
    url = (f"https://bdfed.stitch.mlbinfra.com/bdfed/stats/player"
           f"?stitch_env=prod&season=2026&sportId=1&stats=season"
           f"&group={group}&gameType=R&offset=0&sortStat={sort}&order=desc&limit={limit}")
    data = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15).json()
    meta = {}
    for s in data.get("stats", []):
        pid = int(s["playerId"])
        meta[pid] = {
            "name":        s["playerFullName"],
            "player_id":   pid,
            "team":        s["teamName"],
            "team_abbrev": s.get("teamAbbrev", ""),
            "pa":          int(s.get("plateAppearances", 0)),
            "ip":          _parse_ip(s.get("inningsPitched", "0")),
            "raw":         s,
        }
    return meta

def _fmt_dp(fmt):
    """Return display decimal places for a formatter function."""
    if fmt is _int:  return 0
    if fmt is _f1:   return 1
    if fmt is _f2:   return 2
    return 3  # _avg

def _tiebreak(players, rank, fmt=None):
    """Re-sort players so tied primary stats are broken by their expected (secondary) stat."""
    reverse = (rank == "largest")
    INF     = float("inf")
    dp      = _fmt_dp(fmt) if fmt is not None else 2

    def key(p):
        # Round to display precision so visually identical values are treated as tied
        primary = round(float(p["val"]), dp)
        sec     = p.get("secondary") or {}
        col     = p.get("secondary_col")
        try:
            sec_val = float(sec[col]) if (sec and col and col in sec) else None
        except (TypeError, ValueError):
            sec_val = None
        if sec_val is None:
            sec_val = -INF if reverse else INF
        return (primary, sec_val)

    return sorted(players, key=key, reverse=reverse)


def _parse_ip(ip_str):
    try:
        parts = str(ip_str).split(".")
        return int(parts[0]) + int(parts[1]) / 3 if len(parts) == 2 else float(ip_str)
    except Exception:
        return 0.0

def _fetch_fip_top10(games):
    """Compute FIP and xFIP from bdfed pitching data."""
    FIP_CONST  = 3.10
    LG_HR_FB   = 0.104   # league-average HR/FB rate for xFIP
    min_ip = max(1, games - 2)
    meta = _bdfed_meta("pitching", limit=500)
    rows = []
    for pid, m in meta.items():
        if m["ip"] < min_ip:
            continue
        s = m["raw"]
        try:
            hr   = float(s.get("homeRuns",    0) or 0)
            bb   = float(s.get("baseOnBalls", 0) or 0)
            hbp  = float(s.get("hitByPitch",  0) or 0)
            so   = float(s.get("strikeOuts",  0) or 0)
            fb   = float(s.get("airOuts",     0) or 0) + hr  # fly balls ≈ air outs + HR
            ip   = m["ip"]
            fip  = (13 * hr + 3 * (bb + hbp) - 2 * so) / ip + FIP_CONST
            xfip = (13 * fb * LG_HR_FB + 3 * (bb + hbp) - 2 * so) / ip + FIP_CONST
        except (ZeroDivisionError, TypeError):
            continue
        rows.append({**m, "val": fip, "xfip": round(xfip, 2)})
    rows.sort(key=lambda x: x["val"])
    top10 = rows[:10]
    for p in top10:
        p["secondary"]       = {"xfip": p["xfip"]}
        p["secondary_label"] = "xFIP"
        p["secondary_col"]   = "xfip"
    top10 = _tiebreak(top10, "smallest", _f2)
    return top10


def _download_bref_file(bref_type):
    """Download one bref WAR file to cache, respecting rate limits."""
    cache_path = os.path.join(CACHE_DIR, f"bref_war_{bref_type}.txt")
    needs_fetch = (
        not os.path.exists(cache_path) or
        time.time() - os.path.getmtime(cache_path) > 20 * 3600
    )
    if not needs_fetch:
        return
    url = f"https://www.baseball-reference.com/data/war_daily_{bref_type}.txt"
    for attempt in range(4):
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        if r.status_code == 200 and r.text.strip() and not r.text.lstrip().startswith("<"):
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(r.text)
            return
        wait = 15 * (2 ** attempt)
        print(f"  bref {bref_type} attempt {attempt+1} got {r.status_code}, retrying in {wait}s…")
        time.sleep(wait)
    if os.path.exists(cache_path):
        print(f"  bref {bref_type}: using stale cache (bref blocked)")
        return
    raise ValueError(f"Baseball Reference blocked after 4 attempts for {bref_type}")


def prefetch_bref_cache(keys):
    """Pre-fetch both bref WAR files upfront with a gap to avoid rate limiting."""
    types_needed = set()
    for k in keys:
        cfg = STAT_CONFIG.get(k, {})
        if cfg.get("source") == "bref_war":
            types_needed.add(cfg["bref_type"])
    for i, bref_type in enumerate(sorted(types_needed)):
        if i > 0:
            print("  Waiting 30s before next Baseball Reference request…")
            time.sleep(30)
        try:
            _download_bref_file(bref_type)
        except ValueError as e:
            print(f"  WARNING: {e} — skipping {bref_type} graphics")


def _fetch_bref_war_top10(bref_type, games):
    """Fetch WAR from locally-cached Baseball Reference data."""
    cache_path = os.path.join(CACHE_DIR, f"bref_war_{bref_type}.txt")
    if not os.path.exists(cache_path):
        try:
            _download_bref_file(bref_type)
        except ValueError:
            raise RuntimeError(f"No cache for bref {bref_type} and download failed")
    with open(cache_path, encoding="utf-8") as f:
        text = f.read()
    df = pd.read_csv(io.StringIO(text), on_bad_lines="skip", engine="python")
    df = df[df["year_ID"] == 2026].copy()
    df["mlb_ID"] = pd.to_numeric(df["mlb_ID"], errors="coerce")
    df = df.dropna(subset=["mlb_ID", "WAR"])
    # Sum WAR across stints (players who changed teams)
    war_by_id = df.groupby("mlb_ID")["WAR"].sum().reset_index()
    war_by_id["mlb_ID"] = war_by_id["mlb_ID"].astype(int)

    group = "hitting" if bref_type == "bat" else "pitching"
    meta  = _bdfed_meta(group, limit=500)
    games_count = games

    rows = []
    for _, row in war_by_id.iterrows():
        pid = int(row["mlb_ID"])
        if pid not in meta:
            continue
        m = meta[pid]
        # Qualification filter
        if bref_type == "bat" and m["pa"] < int(3.1 * games_count):
            continue
        if bref_type == "pit" and m["ip"] < games_count * 1.0:
            continue
        rows.append({**m, "val": float(row["WAR"])})

    rows.sort(key=lambda x: x["val"], reverse=True)
    top10 = rows[:10]
    for p in top10:
        p["secondary"] = None
    return top10


def fetch_top10(stat_key):
    cfg   = STAT_CONFIG[stat_key]
    group = cfg["group"]
    rank  = cfg["rank"]
    hdrs  = {"User-Agent": "Mozilla/5.0"}

    if cfg.get("source") == "savant_expected":
        return _fetch_top10_savant(stat_key, season_games())
    if cfg.get("source") == "bdfed_computed_fip":
        return _fetch_fip_top10(season_games())
    if cfg.get("source") == "bref_war":
        return _fetch_bref_war_top10(cfg["bref_type"], season_games())

    # Use MLB.com official leaderboard (qualification rules built in)
    mlb_cat = cfg["mlb_cat"]
    url = (f"https://statsapi.mlb.com/api/v1/stats/leaders"
           f"?leaderCategories={mlb_cat}&season=2026&leaderGameTypes=R"
           f"&limit=10&statGroup={group}&hydrate=person,team")
    data = requests.get(url, headers=hdrs, timeout=15).json()
    if not data.get("leagueLeaders"):
        time.sleep(3)
        data = requests.get(url, headers=hdrs, timeout=15).json()
    leaders = data["leagueLeaders"][0]["leaders"]

    rows = []
    for entry in leaders:
        try:
            val = float(entry["value"])
        except (ValueError, TypeError):
            continue
        rows.append({
            "name":        entry["person"]["fullName"],
            "player_id":   int(entry["person"]["id"]),
            "team":        entry["team"]["name"],
            "team_abbrev": entry["team"].get("abbreviation", ""),
            "val":         val,
        })

    top10 = rows[:10]  # already ranked by MLB.com; cap at 10

    # Secondary stat (expected version from Savant)
    sec = cfg.get("secondary")
    if sec:
        sec_map = fetch_savant_expected(sec["type"])
        for p in top10:
            p["secondary"] = sec_map.get(p["player_id"])
            p["secondary_label"] = sec["label"]
            p["secondary_col"]   = sec["col"]
        top10 = _tiebreak(top10, rank, cfg.get("fmt"))
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
        top10 = _tiebreak(top10, "largest", cfg.get("fmt"))
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
_RANKS_FILE = os.path.join(CACHE_DIR, "rankings.json")

def load_prev_ranks():
    if not os.path.exists(_RANKS_FILE):
        return {}
    with open(_RANKS_FILE) as f:
        return json.load(f)

def save_ranks(rankings):
    with open(_RANKS_FILE, "w") as f:
        json.dump(rankings, f)


def build(players, stat_key, prev_ranks=None, output=None):
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
    y  = 6

    f_title = font("OpenSans-ExtraBold.ttf", 72)
    f_date  = font("OpenSans-Semibold.ttf", 28)

    title_w = int(d.textlength(cfg["title"], font=f_title))
    put(d, cfg["title"], (W - title_w) // 2, y, f_title, WHITE)
    y += f_title.getbbox(cfg["title"])[3] + 10

    today  = datetime.now(ZoneInfo("America/New_York")).strftime("%m/%d/%Y")
    date_w = int(d.textlength(today, font=f_date))
    put(d, today, (W - date_w) // 2, y, f_date, WHITE)

    f_wm = font("OpenSans-Semibold.ttf", 22)
    d.text((ML, y + 3), "unclebensarroz", font=f_wm, fill=(255, 255, 255, 140))

    y += f_date.getbbox(today)[3] + 20

    # ── Player rows ─────────────────────────────────────────────────────────────
    ROW_H   = 111
    LOGO_SZ = 74
    SILO_SZ = ROW_H
    RANK_W  = 54

    f_rank  = font("OpenSans-ExtraBold.ttf", 28)
    f_first = font("OpenSans-Bold.ttf", 22)
    f_last  = font("OpenSans-ExtraBold.ttf", 44)
    f_stat  = font("OpenSans-ExtraBold.ttf", 52)
    f_sec   = font("OpenSans-Semibold.ttf", 22)

    STAT_R = W - 150  # TikTok right safe zone (120-150px for like/comment buttons)

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
                erode = LOGO_ERODE.get(p["team"], 0)
                logo = tint_logo(logo, tint, erode=erode)
            if p["team"] in LOGO_OUTLINE:
                logo = outline_logo(logo, thickness=8)
            logo.thumbnail((LOGO_SZ, LOGO_SZ), Image.LANCZOS)
            lw, lh = logo.size
            lx = ML + RANK_W + (LOGO_SZ - lw) // 2
            ly = cy - lh // 2
            canvas.paste(logo, (lx, ly), logo)

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
            stat_bbox  = f_stat.getbbox(stat_str)
            sec_bbox   = f_sec.getbbox(sec_str)
            stat_blk_h = stat_bbox[3] + 6 + sec_bbox[3]
            sy         = cy - stat_blk_h // 2
            sw         = int(d.textlength(stat_str, font=f_stat))
            put(d, stat_str, STAT_R - sw, sy, f_stat, WHITE)
            xw = int(d.textlength(sec_str, font=f_sec))
            put(d, sec_str, STAT_R - xw, sy + stat_bbox[3] + 4, f_sec, WHITE)
        else:
            bbox = f_stat.getbbox(stat_str)
            sw = int(d.textlength(stat_str, font=f_stat))
            put(d, stat_str, STAT_R - sw, cy - (bbox[1] + bbox[3]) // 2, f_stat, WHITE)


    rows_end = y + 10 * ROW_H
    canvas = canvas.crop((0, 0, W, rows_end + 6))
    canvas.convert("RGB").save(output, "PNG")
    print(f"  Saved → {output}")


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    keys = sys.argv[1:] if len(sys.argv) > 1 else list(STAT_CONFIG.keys())

    prefetch_bref_cache(keys)
    all_prev   = load_prev_ranks()
    today_ranks = {}
    failed = []

    for stat_key in keys:
        if stat_key not in STAT_CONFIG:
            print(f"Unknown stat: {stat_key}. Options: {list(STAT_CONFIG.keys())}")
            continue
        print(f"\n{'─'*40}")
        print(f"Fetching {STAT_CONFIG[stat_key]['title']}…")
        try:
            players = fetch_top10(stat_key)
        except Exception as e:
            print(f"  ERROR fetching {stat_key}: {e}")
            failed.append(stat_key)
            continue
        for p in players:
            print(f"  {p['name']:<25}  {STAT_CONFIG[stat_key]['fmt'](p['val']):<8}  ({p['team']})")
        ensure_silos(players)

        prev_ranks = all_prev.get(stat_key, {})
        build(players, stat_key, prev_ranks=prev_ranks)

        today_ranks[stat_key] = {str(p["player_id"]): i + 1 for i, p in enumerate(players)}

    save_ranks({**all_prev, **today_ranks})

    if failed:
        print(f"\nWARNING: Failed to generate graphics for: {failed}")
