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
# Hat crown colors (the main color of each team's cap)
TEAM_COLORS = {
    "Arizona Diamondbacks":  (167,  25,  48),
    "Atlanta Braves":        ( 19,  39,  79),
    "Baltimore Orioles":     (223,  70,   1),
    "Boston Red Sox":        ( 12,  35,  64),
    "Chicago Cubs":          ( 14,  51, 134),
    "Chicago White Sox":     ( 39,  37,  31),
    "Cincinnati Reds":       (198,   1,  31),
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
    "Pittsburgh Pirates":    (253, 184,  39),
    "San Diego Padres":      ( 47,  36,  29),
    "San Francisco Giants":  (253,  90,  30),
    "Seattle Mariners":      ( 12,  44,  86),
    "St. Louis Cardinals":   (196,  30,  58),
    "Tampa Bay Rays":        ( 16,  78, 146),
    "Texas Rangers":         (  0,  50, 120),
    "Toronto Blue Jays":     ( 19,  74, 142),
    "Washington Nationals":  ( 20,  34,  90),
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

def get_silo(pid):
    return fetch_img(
        f"https://img.mlbstatic.com/mlb-photos/image/upload/w_1000,q_auto:best/v1/people/{pid}/headshot/silo/current",
        f"silo_{pid}.png")

def ensure_silos(players):
    """Download any missing silo images before building, with retries."""
    missing = [p for p in players
               if not os.path.exists(os.path.join(CACHE_DIR, f"silo_{p['player_id']}.png"))]
    if not missing:
        return
    print(f"Downloading {len(missing)} missing silo(s)…")
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
                import time; time.sleep(wait)
        else:
            print(f"  ✗ Could not download silo for {p['name']} after 3 attempts")

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
        f"https://a.espncdn.com/i/teamlogos/mlb/500-dark/{espn}.png",
        f"logo_cap_{espn}.png")

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
    y  = 30

    f_title = font("OpenSans-ExtraBold.ttf", 72)
    f_date  = font("OpenSans-Semibold.ttf", 28)

    # Title — left aligned
    put(d, "BATTING AVERAGE LEADERS", ML, y, f_title, WHITE)
    title_h = f_title.getbbox("BATTING AVERAGE LEADERS")[3]
    y += title_h + 10

    # Date — centered, MM/DD/YYYY
    today     = datetime.now(ZoneInfo("America/New_York")).strftime("%m/%d/%Y")
    date_w    = int(d.textlength(today, font=f_date))
    put(d, today, (W - date_w) // 2, y, f_date, WHITE)
    y += f_date.getbbox(today)[3] + 20

    # ── Player rows ─────────────────────────────────────────────────────────────
    ROW_H   = (H - y - 6) // 10
    LOGO_SZ = 74
    SILO_SZ = ROW_H  # fill full row height

    f_first = font("OpenSans-Bold.ttf", 22)
    f_last  = font("OpenSans-ExtraBold.ttf", 44)
    f_stat  = font("OpenSans-ExtraBold.ttf", 52)

    f_rank = font("OpenSans-ExtraBold.ttf", 28)
    RANK_W = 54  # space reserved for rank number

    for i, p in enumerate(players):
        ry = y + i * ROW_H
        tc = TEAM_COLORS.get(p["team"], (55, 55, 75))

        # Solid team color background (+1 to eliminate any sub-pixel gaps)
        canvas.paste(row_solid(tc, ROW_H + 1, W), (0, ry))

        # Divider line between rows
        if i > 0:
            sep = Image.new("RGBA", (W, 1), (255, 255, 255, 45))
            canvas.paste(sep, (0, ry), sep)

        cy = ry + ROW_H // 2  # vertical centre of row

        # Rank number (#1, #2 …) — flush to left edge
        rank_str = f"#{i + 1}"
        rw = int(d.textlength(rank_str, font=f_rank))
        put(d, rank_str, (RANK_W - rw) // 2 + 4, cy - 14, f_rank, WHITE)

        # Team cap logo
        logo = get_logo(p["team_abbrev"])
        if logo:
            logo = logo.resize((LOGO_SZ, LOGO_SZ), Image.LANCZOS)
            canvas.paste(logo, (ML + RANK_W, cy - LOGO_SZ // 2), logo)

        # Player silo cutout (head & shoulders, transparent bg)
        silo = get_silo(p["player_id"])
        if silo:
            silo = silo.resize((SILO_SZ, SILO_SZ), Image.LANCZOS)
            hx = ML + RANK_W + LOGO_SZ + 8
            canvas.paste(silo, (hx, ry), silo)

        # Name (first / LAST stacked)
        parts  = p["name"].split(" ", 1)
        first  = parts[0].upper()
        last   = parts[1].upper() if len(parts) > 1 else ""
        nx     = ML + RANK_W + LOGO_SZ + 8 + SILO_SZ + 8
        block_h = 22 + 6 + 44
        ny     = cy - block_h // 2
        put(d, first, nx, ny,      f_first, WHITE)
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
    ensure_silos(players)
    build(players)
