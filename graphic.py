"""
MLB Top 10 graphic — row style
Each row: LOGO | HEADSHOT | FIRST / LAST NAME | STAT
Usage: python3 graphic.py
Outputs: hitting/ba_top10.png
"""
import io, os, requests
import numpy as np
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

# ── Team primary colors ────────────────────────────────────────────────────────
TEAM_COLORS = {
    "Arizona Diamondbacks":  (167, 25,  48),
    "Atlanta Braves":        (206, 17,  65),
    "Baltimore Orioles":     (223, 70,   1),
    "Boston Red Sox":        (189, 48,  57),
    "Chicago Cubs":          ( 14, 51, 134),
    "Chicago White Sox":     ( 50, 50,  50),
    "Cincinnati Reds":       (198,  1,  31),
    "Cleveland Guardians":   (  0, 56,  93),
    "Colorado Rockies":      ( 51,  0, 111),
    "Detroit Tigers":        ( 12, 35,  64),
    "Houston Astros":        (  0, 45,  98),
    "Kansas City Royals":    (  0, 70, 135),
    "Los Angeles Angels":    (186,  0,  33),
    "Los Angeles Dodgers":   (  0, 90, 156),
    "Miami Marlins":         (  0,163, 224),
    "Milwaukee Brewers":     ( 18, 40,  75),
    "Minnesota Twins":       (  0, 43,  92),
    "New York Mets":         (  0, 45, 114),
    "New York Yankees":      ( 12, 35,  64),
    "Athletics":             (  0, 56,  49),
    "Philadelphia Phillies": (232, 24,  40),
    "Pittsburgh Pirates":    ( 50, 50,  50),
    "San Diego Padres":      ( 47, 36,  29),
    "San Francisco Giants":  (200, 70,  20),
    "Seattle Mariners":      ( 12, 44,  86),
    "St. Louis Cardinals":   (196, 30,  58),
    "Tampa Bay Rays":        (  9, 44,  92),
    "Texas Rangers":         (  0, 50, 120),
    "Toronto Blue Jays":     ( 19, 74, 142),
    "Washington Nationals":  (171,  0,   3),
}

# ── Helpers ────────────────────────────────────────────────────────────────────
def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS_DIR, name), size)

def put(d, text, x, y, fnt, color):
    d.text((x, y), text, font=fnt, fill=(*color, 255))

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

def get_headshot(pid):
    return fetch_img(
        f"https://img.mlbstatic.com/mlb-photos/image/upload/w_180,q_auto:best/v1/people/{pid}/headshot/67/current",
        f"hs_{pid}.png")

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

def get_logo(team_abbrev):
    espn = ESPN_ABBR.get(team_abbrev, team_abbrev.lower())
    return fetch_img(
        f"https://a.espncdn.com/i/teamlogos/mlb/500/{espn}.png",
        f"logo_espn_{espn}.png")

def circle_crop(img, size):
    img = img.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out

def row_solid(team_color, row_h, row_w):
    r, g, b = team_color
    arr = np.full((row_h, row_w, 4), (r, g, b, 255), dtype=np.uint8)
    return Image.fromarray(arr, "RGBA")

# ── Data ───────────────────────────────────────────────────────────────────────
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

def fetch_ba():
    hdrs = {"User-Agent": "Mozilla/5.0"}
    url  = ("https://bdfed.stitch.mlbinfra.com/bdfed/stats/player"
            "?stitch_env=prod&season=2026&sportId=1&stats=season"
            "&group=hitting&gameType=R&offset=0&sortStat=avg&order=desc&limit=60")
    data   = requests.get(url, headers=hdrs, timeout=15).json()
    min_pa = int(3.1 * season_games())
    rows   = []
    for s in data.get("stats", []):
        if int(s.get("plateAppearances", 0)) < min_pa:
            continue
        rows.append({
            "name":        s["playerFullName"],
            "player_id":   int(s["playerId"]),
            "team":        s["teamName"],
            "team_abbrev": s.get("teamAbbrev", ""),
            "val":         float(s.get("avg", "0")),
        })
    rows.sort(key=lambda x: x["val"], reverse=True)
    return rows[:10]

# ── Build ──────────────────────────────────────────────────────────────────────
def build(players, output=None):
    if output is None:
        out_dir = os.path.join(BASE, "hitting")
        os.makedirs(out_dir, exist_ok=True)
        output = os.path.join(out_dir, "ba_top10.png")

    canvas = Image.new("RGBA", (W, H), (*BG, 255))
    d      = ImageDraw.Draw(canvas)

    # ── Header ─────────────────────────────────────────────────────────────────
    ML = 44
    y  = 26

    f_top  = font("OpenSans-ExtraBold.ttf", 88)
    f_sub  = font("OpenSans-Bold.ttf", 34)
    f_date = font("OpenSans-Semibold.ttf", 20)

    top_w = int(d.textlength("TOP ", font=f_top))
    put(d, "TOP ", ML, y, f_top, WHITE)
    put(d, "10",   ML + top_w, y, f_top, RED)
    y += 86

    put(d, "BATTING AVERAGE LEADERS", ML, y, f_sub, WHITE)
    y += 40

    d.rectangle([ML, y, ML + 580, y + 3], fill=(*RED, 255))
    y += 13

    today = datetime.now(ZoneInfo("America/New_York")).strftime("%-m/%-d/%y")
    put(d, f"2026 MLB Season  ·  Qualified PA  ·  As of {today}", ML, y, f_date, DIM)
    y += 32

    # ── Player rows ─────────────────────────────────────────────────────────────
    ROW_H   = (H - y - 6) // 10
    LOGO_SZ = 74
    HEAD_SZ = 100

    f_first = font("OpenSans-Bold.ttf", 22)
    f_last  = font("OpenSans-ExtraBold.ttf", 44)
    f_stat  = font("OpenSans-ExtraBold.ttf", 52)

    for i, p in enumerate(players):
        ry = y + i * ROW_H
        tc = TEAM_COLORS.get(p["team"], (55, 55, 75))

        # Solid team color background
        canvas.paste(row_solid(tc, ROW_H, W), (0, ry))

        # Divider line between rows
        if i > 0:
            sep = Image.new("RGBA", (W, 1), (255, 255, 255, 45))
            canvas.paste(sep, (0, ry), sep)

        cy = ry + ROW_H // 2  # vertical centre of row

        # Team logo on white circle badge
        BADGE_PAD = 6
        badge_sz  = LOGO_SZ + BADGE_PAD * 2
        badge     = Image.new("RGBA", (badge_sz, badge_sz), (0, 0, 0, 0))
        ImageDraw.Draw(badge).ellipse((0, 0, badge_sz - 1, badge_sz - 1),
                                      fill=(255, 255, 255, 255))
        logo_cx = ML + LOGO_SZ // 2
        canvas.paste(badge, (logo_cx - badge_sz // 2, cy - badge_sz // 2), badge)
        logo = get_logo(p["team_abbrev"])
        if logo:
            logo = logo.resize((LOGO_SZ, LOGO_SZ), Image.LANCZOS)
            canvas.paste(logo, (ML, cy - LOGO_SZ // 2), logo)

        # Player headshot (circle)
        hs = get_headshot(p["player_id"])
        if hs:
            hs = circle_crop(hs, HEAD_SZ)
            hx = ML + LOGO_SZ + 14
            canvas.paste(hs, (hx, cy - HEAD_SZ // 2), hs)

        # Name (first / LAST stacked)
        parts  = p["name"].split(" ", 1)
        first  = parts[0].upper()
        last   = parts[1].upper() if len(parts) > 1 else ""
        nx     = ML + LOGO_SZ + 14 + HEAD_SZ + 16
        block_h = 22 + 6 + 44
        ny     = cy - block_h // 2
        put(d, first, nx, ny,      f_first, DIM)
        put(d, last,  nx, ny + 28, f_last,  WHITE)

        # Stat value (right-aligned)
        stat_str = (f"{p['val']:.3f}" if p["val"] >= 1
                    else f".{int(round(p['val'] * 1000)):03d}")
        sw = int(d.textlength(stat_str, font=f_stat))
        put(d, stat_str, W - 48 - sw, cy - 26, f_stat, WHITE)

    canvas.convert("RGB").save(output, "PNG")
    print(f"Saved → {output}")


if __name__ == "__main__":
    print("Fetching batting average leaders…")
    players = fetch_ba()
    for p in players:
        print(f"  {p['name']:<25}  {p['val']:.3f}  ({p['team']})")
    build(players)
