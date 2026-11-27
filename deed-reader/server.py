#!/usr/bin/env python3
"""Deed Reader team server (version 0.1, 26 November 2026).

One small Python process that gives a reading team:
  1. one copy of the form, the data file and the scans;
  2. shared readings: every reader's work is kept on the server, and each reader
     can see (never edit) the others' work;
  3. (D11, 27 Nov 2026) questions to the cluster's own models, asked by the server, so the
     API key never reaches a browser. On only when DHINFRA_API_KEY is set in the server's
     environment (never in a file); otherwise the form keeps its clipboard route alone.

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
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

try:
    from http.server import ThreadingHTTPServer
except ImportError:  # Python 3.6
    import socketserver
    from http.server import HTTPServer

    class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
        daemon_threads = True

VERSION = "0.2"
COOKIE = "dr_token"
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".tif", ".tiff"}
MAX_BODY = 20 * 1024 * 1024  # 20 MB per save

# D11: the cluster's chat models that can read an image (DHinfra console, 27 Nov 2026).
# A name ending ":no-thinking" asks the same model with its thinking switched off. Tested on the cluster
# on 27 Nov 2026: DeepSeek V4.1 Flash honours chat_template_kwargs enable_thinking=false; GLM 5.3 Flash
# thinks whatever it is sent, so it has no such variant.
ASK_MODELS = {"deepseek-v4.1-flash": "DeepSeek V4.1 Flash (cluster)",
              "deepseek-v4.1-flash:no-thinking": "DeepSeek V4.1 Flash, no thinking (cluster)",
              "glm-5.3-flash": "GLM 5.3 Flash (cluster)"}
NO_THINKING = {"chat_template_kwargs": {"enable_thinking": False}}
ASK_BASE_URL = "https://api.dhinfra.uni-graz.at/v1"
ASK_MAX_TOKENS = 32768         # room for a reasoning model's thinking and then a whole page of transcription
ASK_TIMEOUT = 600              # seconds to wait for one answer (a long answer at about 100 tokens a second)
ASK_MAX_QUESTION = 20000       # characters
ASK_MAX_IMAGE = 8 * 1024 * 1024  # characters of the image's data URL


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
        # D11: who asked which model, when, how long and how many tokens; never the question or the key.
        self.ask_log = p(c.get("ask_log", os.path.join(os.path.dirname(self.log_file), "ask.log")))
        self.ask_base_url = c.get("ask_base_url", ASK_BASE_URL).rstrip("/")
        self.ask_models = dict(c.get("ask_models") or ASK_MODELS)
        self.ask_answers_dir = p(c.get("ask_answers_dir", os.path.join(os.path.dirname(self.store_dir), "answers")))
        self.ask_max_tokens = int(c.get("ask_max_tokens", ASK_MAX_TOKENS))
        self.ask_timeout = int(c.get("ask_timeout", ASK_TIMEOUT))


class Asker:
    """D11: asks one of the cluster's models on a reader's behalf.

    The key comes only from the environment variable DHINFRA_API_KEY of the server's own
    process (set by the person who starts the job); it is never written, printed, logged
    or sent to a browser. Without it, asking through the server stays off.
    """

    def __init__(self, cfg):
        self.key = os.environ.get("DHINFRA_API_KEY", "").strip()
        self.base = cfg.ask_base_url
        self.models = cfg.ask_models if self.key else {}
        self.log_file = cfg.ask_log
        self.max_tokens = cfg.ask_max_tokens
        self.timeout = cfg.ask_timeout
        self.lock = threading.Lock()
        # Answers are kept, one file per question, beside the readings: answers/<reader>/<id>.json.
        # Written once when the model replies; a reload, or a server restart, loses nothing.
        self.answers_dir = cfg.ask_answers_dir
        self.working = {}  # (reader, id) -> time started

    def _path(self, reader, qid):
        return os.path.join(self.answers_dir, safe_name(reader), qid + ".json")

    def start(self, reader, qid, model, question, image):
        """Start asking in the background; asking twice for one question starts it once."""
        key = (reader, qid)
        with self.lock:
            if key not in self.working and not os.path.exists(self._path(reader, qid)):
                self.working[key] = time.time()
                threading.Thread(target=self._run, args=(reader, qid, model, question, image), daemon=True).start()
        return {"id": qid, "state": "working"}

    def _run(self, reader, qid, model, question, image):
        try:
            code, out = self.ask(reader, model, question, image)
        except Exception as e:  # never leave a question working for ever
            code, out = 500, {"error": self.scrub("the server failed while asking (%s)" % type(e).__name__)}
        out = dict(out, id=qid, http=code, state="done")
        path = self._path(reader, qid)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".part", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
        os.replace(path + ".part", path)
        with self.lock:
            self.working.pop((reader, qid), None)

    def collect(self, reader, qid):
        """A reader's own answer: 200 when kept, 202 while the model works, 404 if never asked."""
        if not re.match(r"[A-Za-z0-9_-]{1,80}$", qid or ""):
            return 400, {"error": "question id missing or malformed"}
        with self.lock:
            started = self.working.get((reader, qid))
        if started is not None:
            return 202, {"id": qid, "state": "working", "seconds": round(time.time() - started)}
        try:
            with open(self._path(reader, qid), encoding="utf-8") as f:
                return 200, json.load(f)
        except OSError:
            return 404, {"id": qid, "state": "unknown"}

    def on(self):
        return bool(self.key and self.models)

    def scrub(self, s):
        return s.replace(self.key, "[key]") if self.key else s

    def log(self, reader, model, seconds, outcome, usage):
        u = usage or {}
        line = "%s reader=%s model=%s seconds=%.1f outcome=%s tokens_in=%s tokens_out=%s\n" % (
            now(), safe_name(reader), model, seconds, outcome.replace(" ", "_"),
            u.get("prompt_tokens", "-"), u.get("completion_tokens", "-"))
        with self.lock:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line)

    def ask(self, reader, model, question, image):
        content = [{"type": "text", "text": question}]
        if image:
            content.append({"type": "image_url", "image_url": {"url": image}})
        name, _, variant = model.partition(":")
        body = {"model": name, "messages": [{"role": "user", "content": content}],
                "max_tokens": self.max_tokens, "temperature": 0.2}
        if variant == "no-thinking":
            body.update(NO_THINKING)
        req = urllib.request.Request(self.base + "/chat/completions", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + self.key}, method="POST")
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                res = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                detail = e.read(400).decode("utf-8", "replace")
            except Exception:
                detail = ""
            self.log(reader, model, time.time() - t0, "http %d" % e.code, None)
            return 502, {"error": self.scrub("the cluster's model service answered %d %s" % (e.code, detail.strip()))}
        except Exception as e:  # network, timeout, not JSON
            self.log(reader, model, time.time() - t0, type(e).__name__, None)
            return 504, {"error": self.scrub("no answer from the cluster's model service (%s: %s)" % (type(e).__name__, e))}
        choice = (res.get("choices") or [{}])[0] or {}
        msg = choice.get("message") or {}
        answer = msg.get("content") or ""
        if isinstance(answer, list):  # some services return a list of text parts
            answer = "".join(p.get("text", "") for p in answer if isinstance(p, dict))
        reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
        usage = res.get("usage") or {}
        usage = {k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens") if k in usage}
        seconds = time.time() - t0
        self.log(reader, model, seconds, "answered" if answer.strip() else "empty", usage)
        return 200, {"t": now(), "model": model, "label": self.models[model], "answer": answer.strip(),
                     "reasoning": str(reasoning).strip()[:20000], "finish": choice.get("finish_reason"),
                     "usage": usage, "seconds": round(seconds, 1)}


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


def make_handler(cfg, store, tokens, asker):
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
                                            "ask": asker.on(),
                                            "ask_models": [{"id": k, "label": v} for k, v in asker.models.items()]})
            if path == "/api/ask":
                code, out = asker.collect(reader, (q.get("id") or [""])[0])
                return self.send_json(code, out)
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
                if not asker.on():
                    return self.send_json(501, {"error": "Asking a model through the server is not switched on yet."})
                model, question, image = body.get("model"), body.get("question"), body.get("image")
                if model not in asker.models:
                    return self.send_json(400, {"error": "not one of the cluster models this server asks"})
                if not isinstance(question, str) or not question.strip() or len(question) > ASK_MAX_QUESTION:
                    return self.send_json(400, {"error": "question missing or too long"})
                if image is not None and not (isinstance(image, str) and len(image) <= ASK_MAX_IMAGE and
                                              re.match(r"data:image/(jpeg|png);base64,[A-Za-z0-9+/=]+$", image)):
                    return self.send_json(400, {"error": "image must be a JPEG or PNG data URL under 8 MB"})
                qid = body.get("id")
                if not (isinstance(qid, str) and re.match(r"[A-Za-z0-9_-]{1,80}$", qid)):
                    return self.send_json(400, {"error": "question id missing or malformed"})
                # Answered later: the browser collects the answer with GET /api/ask?id=..., so no
                # connection is held open while the model thinks (the cluster drops long silent ones).
                return self.send_json(202, asker.start(reader, qid, model, question, image))
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
    asker = Asker(cfg)
    srv = ThreadingHTTPServer((cfg.bind, cfg.port), make_handler(cfg, store, tokens, asker))
    host = socket.gethostname()
    print("Deed Reader server %s started %s on %s, port %d" % (VERSION, now(), host, cfg.port))
    print("Readers with tokens: %s" % ", ".join(sorted({r for _, r in tokens})))
    print("Readings kept in: %s (%d readers so far)" % (cfg.store_dir, len(store.readers)))
    if asker.on():
        print("Asking the cluster's models: on (%s); up to %d tokens and %d seconds an answer"
              % (", ".join(asker.models.values()), asker.max_tokens, asker.timeout))
    else:
        print("Asking the cluster's models: off (no DHINFRA_API_KEY in this job's environment)")
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
