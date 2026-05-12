"""
TikTok auto-poster — regenerates graphics and posts 4/day on rotation.
Usage:
  python3 tiktok_post.py          # post today's 4 graphics now
  python3 tiktok_post.py --dry-run  # show what would be posted without posting
"""
import os, sys, json, time, math, requests
from datetime import date
from dotenv import load_dotenv

load_dotenv()

CLIENT_KEY    = os.environ["TIKTOK_CLIENT_KEY"]
CLIENT_SECRET = os.environ["TIKTOK_CLIENT_SECRET"]
TOKEN_FILE    = os.path.join(os.path.dirname(__file__), "tiktok_token.json")
BASE          = os.path.dirname(os.path.abspath(__file__))

# Rotation order — 20 graphics, 4/day, 5-day cycle then repeats
ROTATION = [
    ("hitting/ba_top10.png",    "Batting Average Leaders 🏆 #MLB #Baseball #Stats"),
    ("pitching/era_top10.png",  "ERA Leaders 🏆 #MLB #Baseball #Stats"),
    ("hitting/hr_top10.png",    "Home Run Leaders 🏆 #MLB #Baseball #Stats"),
    ("pitching/k_top10.png",    "Strikeout Leaders 🏆 #MLB #Baseball #Stats"),

    ("hitting/obp_top10.png",   "On-Base % Leaders 🏆 #MLB #Baseball #Stats"),
    ("pitching/whip_top10.png", "WHIP Leaders 🏆 #MLB #Baseball #Stats"),
    ("hitting/rbi_top10.png",   "RBI Leaders 🏆 #MLB #Baseball #Stats"),
    ("pitching/sv_top10.png",   "Save Leaders 🏆 #MLB #Baseball #Stats"),

    ("hitting/slg_top10.png",   "Slugging % Leaders 🏆 #MLB #Baseball #Stats"),
    ("pitching/fip_top10.png",  "FIP Leaders 🏆 #MLB #Baseball #Stats"),
    ("hitting/ops_top10.png",   "OPS Leaders 🏆 #MLB #Baseball #Stats"),
    ("pitching/k9_top10.png",   "K/9 Leaders 🏆 #MLB #Baseball #Stats"),

    ("hitting/woba_top10.png",  "wOBA Leaders 🏆 #MLB #Baseball #Stats"),
    ("pitching/baa_top10.png",  "BAA Leaders 🏆 #MLB #Baseball #Stats"),
    ("hitting/sb_top10.png",    "Stolen Base Leaders 🏆 #MLB #Baseball #Stats"),
    ("pitching/w_top10.png",    "Win Leaders 🏆 #MLB #Baseball #Stats"),

    ("hitting/hits_top10.png",  "Hit Leaders 🏆 #MLB #Baseball #Stats"),
    ("pitching/pwar_top10.png","Pitching WAR Leaders 🏆 #MLB #Baseball #Stats"),
    ("hitting/r_top10.png",     "Runs Leaders 🏆 #MLB #Baseball #Stats"),
    ("hitting/hwar_top10.png", "Batting WAR Leaders 🏆 #MLB #Baseball #Stats"),
]

CYCLE = 5        # days per full rotation
PER_DAY = 4      # graphics per day


def load_token():
    if not os.path.exists(TOKEN_FILE):
        sys.exit("No token file found. Run tiktok_auth.py first.")
    with open(TOKEN_FILE) as f:
        return json.load(f)


def save_token(data):
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f, indent=2)


def refresh_token(token_data):
    r = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key":     CLIENT_KEY,
            "client_secret":  CLIENT_SECRET,
            "grant_type":     "refresh_token",
            "refresh_token":  token_data["refresh_token"],
        },
        timeout=15,
    )
    r.raise_for_status()
    new_token = r.json()
    save_token(new_token)
    print("Token refreshed.")
    return new_token


def get_access_token():
    token = load_token()
    # Refresh if less than 1 hour left
    expires_at = token.get("expires_in", 0) + token.get("_fetched_at", 0)
    if time.time() > expires_at - 3600:
        token = refresh_token(token)
    return token["access_token"]


def upload_image(access_token, image_path):
    """Upload a single image and return its image_url for the post API."""
    # Step 1: initialize upload
    init_r = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json={
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": os.path.getsize(image_path),
                "chunk_size": os.path.getsize(image_path),
                "total_chunk_count": 1,
            }
        },
        timeout=15,
    )
    init_r.raise_for_status()
    init_data = init_r.json().get("data", {})
    upload_url = init_data.get("upload_url")
    if not upload_url:
        raise RuntimeError(f"No upload_url in response: {init_r.text}")
    return upload_url, init_data


def post_photo(access_token, image_path, caption, dry_run=False):
    if dry_run:
        print(f"  [DRY RUN] Would post: {image_path}")
        print(f"  Caption: {caption}")
        return

    file_size = os.path.getsize(image_path)

    # Initialize the photo post
    init_r = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/content/init/",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json={
            "post_info": {
                "title":          caption,
                "privacy_level":  "PUBLIC_TO_EVERYONE",
                "disable_duet":   False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source":            "FILE_UPLOAD",
                "photo_cover_index": 0,
                "photo_images":      [{"size": file_size}],
            },
            "media_type": "PHOTO",
            "post_mode":  "DIRECT_POST",
        },
        timeout=15,
    )
    init_r.raise_for_status()
    init_data = init_r.json().get("data", {})
    publish_id  = init_data.get("publish_id")
    upload_urls = init_data.get("photo_upload_urls", [])

    if not upload_urls:
        raise RuntimeError(f"No upload URLs: {init_r.text}")

    # Upload the image binary
    with open(image_path, "rb") as f:
        img_bytes = f.read()

    up_r = requests.put(
        upload_urls[0],
        headers={"Content-Type": "image/png", "Content-Length": str(file_size)},
        data=img_bytes,
        timeout=30,
    )
    up_r.raise_for_status()

    print(f"  Posted: {os.path.basename(image_path)} (publish_id={publish_id})")
    return publish_id


def todays_graphics():
    """Return the 4 graphics scheduled for today based on day-of-year rotation."""
    day_of_year = date.today().timetuple().tm_yday
    slot = (day_of_year % (CYCLE * PER_DAY))  # 0–19
    start = (slot // PER_DAY) * PER_DAY        # round down to nearest group of 4
    return ROTATION[start: start + PER_DAY]


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv

    # Regenerate all graphics with fresh stats
    print("Regenerating graphics…")
    os.system(f"cd {BASE} && python3 graphic.py")

    # Get today's 4 graphics
    todays = todays_graphics()
    day_of_year = date.today().timetuple().tm_yday
    cycle_day = (day_of_year % (CYCLE * PER_DAY)) // PER_DAY + 1
    print(f"\nCycle day {cycle_day}/{CYCLE} — posting {len(todays)} graphics:")
    for path, caption in todays:
        print(f"  • {path}")

    if not dry_run:
        access_token = get_access_token()

    print()
    for path, caption in todays:
        full_path = os.path.join(BASE, path)
        if not os.path.exists(full_path):
            print(f"  SKIP (file not found): {full_path}")
            continue
        try:
            post_photo(access_token if not dry_run else None, full_path, caption, dry_run)
            if not dry_run:
                time.sleep(10)  # brief pause between posts
        except Exception as e:
            print(f"  ERROR posting {path}: {e}")

    print("\nDone.")
