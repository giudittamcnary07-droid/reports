#!/data/data/com.termux/files/usr/bin/python
"""Phone-local resolver for Google Maps share links used by the Grab helper."""

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 8767
ALLOWED_ORIGIN = "https://giudittamcnary07-droid.github.io"
SHORT_HOSTS = {"maps.app.goo.gl", "goo.gl"}
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 PhoneMapsResolver/1.1"}


def fetch_text(url):
    request = urllib.request.Request(url, method="GET", headers=REQUEST_HEADERS)
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read(8_000_000).decode("utf-8", errors="replace")


def direct_coordinates(url):
    decoded = urllib.parse.unquote(url)
    patterns = (
        r"!3d(-?\d{1,2}(?:\.\d+)?)!4d(-?\d{1,3}(?:\.\d+)?)",
        r"@(-?\d{1,2}(?:\.\d+)?),(-?\d{1,3}(?:\.\d+)?)",
    )
    for pattern in patterns:
        match = re.search(pattern, decoded)
        if match:
            lat, lng = float(match.group(1)), float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return lat, lng
    return None


def place_label(final_url):
    match = re.search(r"/maps/place/([^/?]+)", final_url)
    if not match:
        return "Google Maps 地点", ""
    label = urllib.parse.unquote_plus(match.group(1)).strip()
    parts = [part.strip() for part in label.split(",") if part.strip()]
    if not parts:
        return "Google Maps 地点", ""
    return parts[0], ", ".join(parts[1:])


def translate_address_zh(address):
    address = str(address or "").strip()
    if not address:
        return ""
    query = urllib.parse.urlencode(
        {
            "client": "gtx",
            "sl": "auto",
            "tl": "zh-CN",
            "dt": "t",
            "q": address,
        }
    )
    try:
        payload = json.loads(
            fetch_text(f"https://translate.googleapis.com/translate_a/single?{query}")
        )
        translated = "".join(
            segment[0]
            for segment in (payload[0] or [])
            if isinstance(segment, list) and segment and isinstance(segment[0], str)
        ).strip()
    except Exception:
        translated = address
    replacements = (
        (r"\bLevel\s+(\d+[A-Za-z]?)\b", r"第\1层"),
        (r"\bFloor\s+(\d+[A-Za-z]?)\b", r"第\1层"),
        (r"\bKuala Lumpur City Centre\b", "吉隆坡市中心"),
        (r"\bFederal Territory of Kuala Lumpur\b", "吉隆坡联邦直辖区"),
        (r"\bKuala Lumpur\b", "吉隆坡"),
    )
    for pattern, replacement in replacements:
        translated = re.sub(pattern, replacement, translated, flags=re.IGNORECASE)
    return re.sub(r"\s*,\s*", "，", translated).strip(" ，")


def preview_coordinates(final_url):
    page = fetch_text(final_url)
    preview_match = re.search(r'href=["\'](/maps/preview/place[^"\']+)', page)
    if not preview_match:
        raise ValueError("Google Maps 地点页没有提供坐标核对入口")
    preview_url = urllib.parse.urljoin(
        "https://www.google.com", html.unescape(preview_match.group(1))
    )
    preview = fetch_text(preview_url)
    center_match = re.search(
        r"\[\[\s*[0-9.eE+-]+\s*,\s*(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,2}\.\d+)\s*\]",
        preview,
    )
    if not center_match:
        raise ValueError("Google Maps 地点 ID 已找到，但没有返回真实坐标")
    lng, lat = float(center_match.group(1)), float(center_match.group(2))
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError("Google Maps 返回的地点坐标无效")
    return lat, lng


def resolve_short_url(value):
    value = str(value or "").strip()
    if not value or len(value) > 2048:
        raise ValueError("Google Maps 分享链接为空或过长")
    parsed = urllib.parse.urlsplit(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in SHORT_HOSTS:
        raise ValueError("只支持 Google Maps 官方分享短链接")
    if host == "goo.gl" and not parsed.path.startswith("/maps"):
        raise ValueError("只支持 Google Maps 官方分享短链接")

    request = urllib.request.Request(value, method="HEAD", headers=REQUEST_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            final_url = response.geturl()
    except urllib.error.HTTPError as exc:
        if exc.code not in (400, 403, 405):
            raise
        request = urllib.request.Request(value, method="GET", headers=REQUEST_HEADERS)
        with urllib.request.urlopen(request, timeout=12) as response:
            final_url = response.geturl()

    final = urllib.parse.urlsplit(final_url)
    final_host = (final.hostname or "").lower()
    if final_host != "google.com" and not final_host.endswith(".google.com"):
        raise ValueError("短链接没有展开到 Google Maps 官方地址")
    if "/maps" not in final.path:
        raise ValueError("展开结果不是 Google Maps 地点链接")
    coordinates = direct_coordinates(final_url) or preview_coordinates(final_url)
    name, address = place_label(final_url)
    return {
        "url": final_url,
        "lat": coordinates[0],
        "lng": coordinates[1],
        "name": name,
        "address": address,
        "addressZh": translate_address_zh(address),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "PhoneMapsResolver/1.0"

    def reply(self, code, body, cors=False):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        payload = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cors:
            origin = self.headers.get("Origin", "")
            if origin == ALLOWED_ORIGIN:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        if urllib.parse.urlsplit(self.path).path != "/resolve":
            return self.reply(404, {"error": "not found"})
        if self.headers.get("Origin", "") != ALLOWED_ORIGIN:
            return self.reply(403, {"ok": False, "error": "来源被拒绝"})
        return self.reply(204, "", cors=True)

    def do_GET(self):
        parsed_request = urllib.parse.urlsplit(self.path)
        if parsed_request.path == "/health":
            return self.reply(200, {"ok": True, "service": "maps-resolver"})
        if parsed_request.path != "/resolve":
            return self.reply(404, {"error": "not found"})
        origin = self.headers.get("Origin", "")
        if origin and origin != ALLOWED_ORIGIN:
            return self.reply(403, {"ok": False, "error": "来源被拒绝"})
        try:
            query = urllib.parse.parse_qs(parsed_request.query)
            result = resolve_short_url((query.get("url") or [""])[0])
            return self.reply(200, {"ok": True, **result}, cors=True)
        except Exception as exc:
            return self.reply(400, {"ok": False, "error": str(exc)}, cors=True)

    def log_message(self, _format, *_args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
