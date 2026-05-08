"""
One-time TikTok OAuth flow — run this once to get your access token.
Usage: python3 tiktok_auth.py
"""
import os, json, secrets, hashlib, base64, webbrowser, requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

load_dotenv()

CLIENT_KEY    = os.environ["TIKTOK_CLIENT_KEY"]
CLIENT_SECRET = os.environ["TIKTOK_CLIENT_SECRET"]
REDIRECT_URI  = "http://localhost:8080/callback"
SCOPE         = "video.publish,video.upload"
TOKEN_FILE    = os.path.join(os.path.dirname(__file__), "tiktok_token.json")

_auth_code = None


def generate_pkce():
    code_verifier  = secrets.token_urlsafe(64)
    digest         = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        qs = parse_qs(urlparse(self.path).query)
        if "code" in qs:
            _auth_code = qs["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h2>Authorized! You can close this tab.</h2>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing code parameter.")

    def log_message(self, *_):
        pass


def authorize(code_challenge):
    state   = secrets.token_urlsafe(16)
    auth_url = (
        f"https://www.tiktok.com/v2/auth/authorize/"
        f"?client_key={CLIENT_KEY}"
        f"&scope={SCOPE}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state={state}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )
    print("Opening browser for TikTok login…")
    print(f"\nIf browser doesn't open, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", 8080), _Handler)
    print("Waiting for TikTok callback on http://localhost:8080 …")
    while _auth_code is None:
        server.handle_request()

    return _auth_code


def exchange_code(code, code_verifier):
    r = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key":     CLIENT_KEY,
            "client_secret":  CLIENT_SECRET,
            "code":           code,
            "grant_type":     "authorization_code",
            "redirect_uri":   REDIRECT_URI,
            "code_verifier":  code_verifier,
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def save_token(data):
    import time
    data["_fetched_at"] = int(time.time())
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Token saved to {TOKEN_FILE}")


if __name__ == "__main__":
    code_verifier, code_challenge = generate_pkce()
    code  = authorize(code_challenge)
    token = exchange_code(code, code_verifier)
    if "access_token" in token:
        save_token(token)
        print("Success! Access token obtained.")
        print(f"  expires_in:    {token.get('expires_in')} seconds")
    else:
        print("Error getting token:", token)
