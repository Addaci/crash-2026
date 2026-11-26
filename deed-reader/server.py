#!/usr/bin/env python3
"""Deed Reader team server (version 0.1, 26 November 2026).

One small Python process that gives a reading team:
  1. one copy of the form, the data file and the scans;
  2. shared readings: every reader's work is kept on the server, and each reader
     can see (never edit) the others' work;
  3. (later, D11) model calls made by the server, so the API key never reaches a browser.

Standard library only, so it runs on a bare Python 3.7 or newer (a DHinfra compute
node, or a laptop). Nothing to install.

Rules it keeps (decisions of 26 Nov 2026):
  D7  the reader's name comes from their token, never from what a browser says;
  D8  every save is appended to a log; nothing is overwritten or deleted;
  D10 scans are served from the paths the data file already uses, images only;
  D12 every request needs a token; the token list lives outside the repository.

Run:   python3 server.py --config server.local.json
The config file is described in server.example.json. Tokens are made with make_tokens.py.
"""
import argparse
import hmac
import http.cookies
import json
import mimetypes
import os
import posixpath
import re
import socket
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler

try:
    from http.server import ThreadingHTTPServer
except ImportError:  # Python 3.6
    import socketserver
    from http.server import HTTPServer

    class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
        daemon_threads = True

VERSION = "0.1"
COOKIE = "dr_token"
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".tif", ".tiff"}
MAX_BODY = 20 * 1024 * 1024  # 20 MB per save


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def safe_name(s):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)[:60] or "anon"


class Store:
    """Append-only readings store (D8).

    One file per reader, readings/<reader>.jsonl. Each save appends one line:
      {"t": ..., "reader": ..., "deeds": {no: entry, ...}, "queries": [...] or absent}
    The current state of a reader is rebuilt by replaying their file, so a restart
    loses nothing. Lines are never rewritten.
    """

    def __init__(self, folder):
        self.folder = folder
        os.makedirs(folder, exist_ok=True)
        self.lock = threading.Lock()
        self.readers = {}  # reader -> {"deeds": {}, "queries": [], "t": str}
        for fn in sorted(os.listdir(folder)):
            if fn.endswith(".jsonl"):
                self._replay(os.path.join(folder, fn))

    def _apply(self, rec):
        r = self.readers.setdefault(rec["reader"], {"deeds": {}, "queries": [], "t": ""})
        for k, v in (rec.get("deeds") or {}).items():
            r["deeds"][str(k)] = v
        if isinstance(rec.get("queries"), list):
            r["queries"] = rec["queries"]
        r["t"] = rec.get("t", r["t"])

    def _replay(self, path):
        with open(path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    self._apply(json.loads(line))
                except (ValueError, KeyError) as e:
                    print("store: skipped line %d of %s (%s)" % (n, path, e), file=sys.stderr)

    def save(self, reader, deeds, queries):
        rec = {"t": now(), "reader": reader, "deeds": deeds}
        if queries is not None:
            rec["queries"] = queries
        line = json.dumps(rec, ensure_ascii=False)
        with self.lock:
            path = os.path.join(self.folder, safe_name(reader) + ".jsonl")
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
                os.fsync(f.fileno())
            self._apply(rec)
        return rec["t"]

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.readers))


class Config:
    def __init__(self, path):
        base = os.path.dirname(os.path.abspath(path))
        with open(path, encoding="utf-8") as f:
            c = json.load(f)

        def p(x):
            x = os.path.expanduser(os.path.expandvars(x))
            return x if os.path.isabs(x) else os.path.normpath(os.path.join(base, x))

        self.bind = c.get("bind", "127.0.0.1")
        self.port = int(c.get("port", 8765))
        if self.port == 8080 or 21800 <= self.port <= 21899:
            sys.exit("Port %d is not available on DHinfra (8080 and 21800-21899 are reserved)." % self.port)
        self.form_dir = p(c.get("form_dir", "."))
        self.data_file = c.get("data_file", "data/deed_data.js")
        self.store_dir = p(c["store_dir"])
        self.tokens_file = p(c["tokens_file"])
        # URL prefix -> folder; the prefix is what the data file's scan paths resolve to.
        self.mounts = {}
        for prefix, folder in (c.get("scan_mounts") or {}).items():
            prefix = "/" + prefix.strip("/") + "/"
            self.mounts[prefix] = p(folder)
        self.log_file = p(c.get("access_log", os.path.join(self.store_dir, "access.log")))


def load_tokens(path):
    """tokens file: {"<token>": {"reader": "Colin"}, ...}; kept outside the repository (D12)."""
    with open(path, encoding="utf-8") as f:
        t = json.load(f)
    out = []
    for tok, v in t.items():
        if len(tok) < 20:
            sys.exit("A token in %s is shorter than 20 characters; make tokens with make_tokens.py." % path)
        out.append((tok, v["reader"]))
    if not out:
        sys.exit("No tokens in %s." % path)
    return out


def make_handler(cfg, store, tokens):
    allowed_static = {"/deed_reader.html": os.path.join(cfg.form_dir, "deed_reader.html"),
                      "/" + cfg.data_file.strip("/"): os.path.join(cfg.form_dir, cfg.data_file)}
    log_lock = threading.Lock()

    def who(tok):
        if not tok:
            return None
        found = None
        for t, reader in tokens:  # compare every token, in constant time
            if hmac.compare_digest(t.encode(), tok.encode()):
                found = reader
        return found

    class H(BaseHTTPRequestHandler):
        server_version = "DeedReaderServer/" + VERSION
        sys_version = ""

        def log_message(self, fmt, *args):
            msg = re.sub(r"([?&]t=)[^&\s\"]*", r"\1[token]", fmt % args)  # never a token in the log
            line = "%s %s %s\n" % (now(), self.address_string(), msg)
            with log_lock:
                with open(cfg.log_file, "a", encoding="utf-8") as f:
                    f.write(line)

        # ---- helpers ----
        def send_json(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def send_text(self, code, text):
            body = text.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def send_file(self, path, cache):
            try:
                size = os.path.getsize(path)
                f = open(path, "rb")
            except OSError:
                return self.send_text(404, "Not found.")
            with f:
                ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
                if path.endswith(".js"):
                    ctype = "text/javascript"
                self.send_response(200)
                self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") else ""))
                self.send_header("Content-Length", str(size))
                self.send_header("Cache-Control", "private, max-age=3600" if cache else "no-store")
                self.end_headers()
                while True:
                    chunk = f.read(1 << 16)
                    if not chunk:
                        break
                    self.wfile.write(chunk)

        def token(self):
            auth = self.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                return auth[7:].strip()
            c = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
            return c[COOKIE].value if COOKIE in c else None

        def deny(self):
            self.send_text(401, "<p>This Deed Reader is for its reading team only. "
                                "Open the personal link your team lead gave you.</p>")

        # ---- GET ----
        def do_GET(self):
            u = urllib.parse.urlsplit(self.path)
            q = urllib.parse.parse_qs(u.query)
            # First visit with ?t=TOKEN: set the cookie and drop the token from the address bar.
            if "t" in q:
                tok = q["t"][0]
                if not who(tok):
                    return self.deny()
                self.send_response(303)
                self.send_header("Set-Cookie", "%s=%s; HttpOnly; SameSite=Strict; Path=/" % (COOKIE, tok))
                self.send_header("Location", "/deed_reader.html")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
            reader = who(self.token())
            if not reader:
                return self.deny()
            path = posixpath.normpath(urllib.parse.unquote(u.path))
            if path in ("/", "."):
                self.send_response(303)
                self.send_header("Location", "/deed_reader.html")
                self.end_headers()
                return
            if path == "/api/me":
                return self.send_json(200, {"reader": reader, "server": VERSION, "readers": sorted({r for _, r in tokens}),
                                            "ask": False})
            if path == "/api/state":
                return self.send_json(200, {"t": now(), "readers": store.snapshot()})
            if path in allowed_static:
                return self.send_file(allowed_static[path], cache=False)
            for prefix, folder in cfg.mounts.items():
                if path.startswith(prefix):
                    rel = path[len(prefix):]
                    if os.path.splitext(rel)[1].lower() not in IMAGE_EXT:
                        return self.send_text(404, "Not found.")
                    full = os.path.normpath(os.path.join(folder, *rel.split("/")))
                    if not full.startswith(os.path.normpath(folder) + os.sep):
                        return self.send_text(404, "Not found.")
                    return self.send_file(full, cache=True)
            return self.send_text(404, "Not found.")

        # ---- POST ----
        def do_POST(self):
            reader = who(self.token())
            if not reader:
                return self.deny()
            path = urllib.parse.urlsplit(self.path).path
            try:
                n = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                n = 0
            if n <= 0 or n > MAX_BODY:
                return self.send_json(413, {"error": "body missing or over 20 MB"})
            try:
                body = json.loads(self.rfile.read(n).decode("utf-8"))
            except ValueError:
                return self.send_json(400, {"error": "not JSON"})
            if path == "/api/save":
                # D7: the reader is the token's reader; whatever name the browser sends is ignored.
                deeds = body.get("deeds") or {}
                queries = body.get("queries")
                if not isinstance(deeds, dict) or (queries is not None and not isinstance(queries, list)):
                    return self.send_json(400, {"error": "deeds must be an object, queries a list"})
                t = store.save(reader, deeds, queries)
                return self.send_json(200, {"saved": t, "reader": reader, "deeds": len(deeds)})
            if path == "/api/ask":
                return self.send_json(501, {"error": "Asking a model through the server is not switched on yet."})
            return self.send_json(404, {"error": "no such endpoint"})

    return H


def main():
    ap = argparse.ArgumentParser(description="Deed Reader team server")
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg = Config(a.config)
    tokens = load_tokens(cfg.tokens_file)
    store = Store(cfg.store_dir)
    for need in (os.path.join(cfg.form_dir, "deed_reader.html"), os.path.join(cfg.form_dir, cfg.data_file)):
        if not os.path.isfile(need):
            sys.exit("Missing: " + need)
    srv = ThreadingHTTPServer((cfg.bind, cfg.port), make_handler(cfg, store, tokens))
    host = socket.gethostname()
    print("Deed Reader server %s started %s on %s, port %d" % (VERSION, now(), host, cfg.port))
    print("Readers with tokens: %s" % ", ".join(sorted({r for _, r in tokens})))
    print("Readings kept in: %s (%d readers so far)" % (cfg.store_dir, len(store.readers)))
    if cfg.bind == "127.0.0.1":
        print("Open: http://localhost:%d/?t=<your token>" % cfg.port)
    else:
        print("From your own computer, open a tunnel (one line), then the link with your token:")
        print("  ssh -N -L %d:%s:%d <your-username>@dhinfra.uni-graz.at" % (cfg.port, host, cfg.port))
        print("  http://localhost:%d/?t=<your token>" % cfg.port)
    sys.stdout.flush()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("Stopped " + now())


if __name__ == "__main__":
    main()
