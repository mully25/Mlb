"""Minimal one-shot file upload server. Visit http://localhost:8765 to upload."""
from http.server import HTTPServer, BaseHTTPRequestHandler
import cgi, os, sys

SAVE_PATH = "/home/user/Mlb/player.jpg"

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass   # silence access logs

    def do_GET(self):
        html = b"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:500px;margin:60px auto;text-align:center">
<h2>Upload player photo</h2>
<form method="post" enctype="multipart/form-data">
  <input type="file" name="photo" accept="image/*"><br><br>
  <button type="submit" style="padding:10px 24px;font-size:16px">Upload</button>
</form></body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html)

    def do_POST(self):
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers,
                                environ={"REQUEST_METHOD":"POST",
                                         "CONTENT_TYPE": self.headers["Content-Type"]})
        item = form["photo"]
        data = item.file.read()
        with open(SAVE_PATH, "wb") as f:
            f.write(data)
        msg = f"Saved {len(data):,} bytes → {SAVE_PATH}".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(msg)
        print(f"\n✓  {msg.decode()}")
        sys.stdout.flush()
        # shut down after one upload
        os._exit(0)

print("Upload server running → http://localhost:8765")
print("Open that URL in your browser, pick the photo, hit Upload.\n")
HTTPServer(("0.0.0.0", 8765), Handler).serve_forever()
