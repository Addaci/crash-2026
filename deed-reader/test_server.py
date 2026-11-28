"""Test the Deed Reader team server (server.py) on the invented sample deeds.

Part of the Deed Reader (crash-2026), 26 November 2026. Standard library only; sends no request
beyond this computer. Everything it makes (tokens, settings, readings, a test image, the logs) goes
into a temporary folder that is removed at the end; no token is ever printed.
    python -I test_server.py          (from the deed-reader folder, or give its path)

1. Refusals: without a token, or with a wrong one (link, cookie or header), the form, the data,
   the readings and saving are all refused.
2. The personal link sets the cookie and sends the browser on to the form, leaving the token
   out of the address.
3. With the cookie, the form, the sample data file and a scan load; the server's name for the
   reader is the token's.
4. Private files are refused: the server's own code, the settings, the token file, anything that
   is not an image under a scan folder, and paths that try to climb out of one.
5. Saving: the reader is taken from the token, whatever name the browser sends (D7); each save is
   added to that reader's log and the earlier lines are kept unchanged (D8); both readers' work
   is visible to each (D9); malformed saves are refused.
6. A restart rebuilds every reader's work from the logs.
7. The settings are checked at start: a port reserved on DHinfra (8080, 21800-21899) and a token
   shorter than 20 characters are refused.
8. No token appears in what the server prints or in its access log.
9. (0.3) The knowledge graph, with invented people and content only: who may open it and who may
   add to it; the author taken from the token; nothing overwritten; Gate 1 by rule and pull-back;
   Gate 2 only from the recorder's link, with both ticks; an imported store, with a void; a
   restart; the export, with no token in it; malformed settings refused.
"""
import http.server
import json
import os
import pathlib
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zlib

HERE = pathlib.Path(__file__).resolve().parent            # deed-reader/
DATA = "sample/sample_data.js"


def tiny_png():
    """A 1 x 1 grey PNG, made here so the test needs no image file."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\x80")) + chunk(b"IEND", b""))


def free_port():
    while True:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            p = s.getsockname()[1]
        if p != 8080 and not 21800 <= p <= 21899:
            return p


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)
PROXY_VARS = ("http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")


def server_env(key=None):
    """The server's environment: no proxy (the pretend model service is on this computer) and
    DHINFRA_API_KEY only when a test gives one."""
    env = {k: v for k, v in os.environ.items() if k not in PROXY_VARS and k != "DHINFRA_API_KEY"}
    env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost"
    if key:
        env["DHINFRA_API_KEY"] = key
    return env


class ServerHarness(unittest.TestCase):
    """Starts server.py on this computer with invented readers; the tests are in the classes below."""
    READERS = ("Anna", "Ben")

    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="deed-reader-server-test-"))
        t = cls.tmp
        (t / "scans").mkdir()
        (t / "scans" / "page1.png").write_bytes(tiny_png())
        (t / "scans" / "note.txt").write_text("not an image", encoding="utf-8")
        (t / "outside.png").write_bytes(tiny_png())          # beside the scan folder, never to be served
        cls.tokens_file = t / "tokens.json"
        cls.prepare()
        r = subprocess.run([sys.executable, "-I", str(HERE / "make_tokens.py"), "--out", str(cls.tokens_file)]
                           + list(cls.READERS), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        assert r.returncode == 0, r.stderr
        toks = json.loads(cls.tokens_file.read_text(encoding="utf-8"))
        cls.tok = {v["reader"]: k for k, v in toks.items()}
        cls.port = free_port()
        cls.base = "http://127.0.0.1:%d" % cls.port
        cls.cfg = cls.write_cfg("server.local.json", port=cls.port)
        cls.outputs = []
        cls.proc = None
        cls.start()

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        shutil.rmtree(cls.tmp, ignore_errors=True)  # only the temporary folder this test made

    # ---- helpers ----
    @classmethod
    def prepare(cls):
        """Anything a test class needs in its temporary folder before the server starts."""

    @classmethod
    def write_cfg(cls, name, **over):
        c = {"bind": "127.0.0.1", "port": 8765, "form_dir": str(HERE), "data_file": DATA,
             "store_dir": str(cls.tmp / "store" / "readings"), "access_log": str(cls.tmp / "store" / "access.log"),
             "tokens_file": str(cls.tokens_file), "scan_mounts": {"/scans/": str(cls.tmp / "scans")}}
        c.update(over)
        p = cls.tmp / name
        p.write_text(json.dumps(c, indent=1), encoding="utf-8")
        return p

    KEY = None  # no API key: asking through the server stays off

    @classmethod
    def start(cls):
        cls.proc = subprocess.Popen([sys.executable, "-I", "-u", str(HERE / "server.py"), "--config", str(cls.cfg)],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                    env=server_env(cls.KEY))
        for _ in range(100):
            if cls.proc.poll() is not None:
                raise RuntimeError("server.py stopped at start: " + cls.proc.stdout.read())
            try:
                with socket.create_connection(("127.0.0.1", cls.port), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("server.py did not start within 10 seconds")

    @classmethod
    def stop(cls):
        if cls.proc and cls.proc.poll() is None:
            cls.proc.terminate()
            try:
                out, _ = cls.proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                cls.proc.kill()
                out, _ = cls.proc.communicate()
            cls.outputs.append(out or "")
        cls.proc = None

    def req(self, path, bearer=None, cookie=None, body=None, raw=None):
        headers = {}
        if bearer:
            headers["Authorization"] = "Bearer " + bearer
        if cookie:
            headers["Cookie"] = "dr_token=" + cookie
        data = raw if raw is not None else (json.dumps(body).encode("utf-8") if body is not None else None)
        if data is not None:
            headers["Content-Type"] = "application/json"
        r = urllib.request.Request(self.base + path, data=data, headers=headers, method="POST" if data is not None else "GET")
        try:
            with OPENER.open(r, timeout=10) as resp:
                return resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.headers, e.read()

    def state(self, who="Anna"):
        code, _, b = self.req("/api/state", bearer=self.tok[who])
        self.assertEqual(code, 200)
        return json.loads(b)["readers"]

    def log_lines(self, reader):
        p = self.tmp / "store" / "readings" / (reader + ".jsonl")
        return p.read_text(encoding="utf-8").splitlines() if p.exists() else []


class ServerTest(ServerHarness):
    # ---- 1. refusals ----
    def test_01_refused_without_a_token(self):
        for path in ("/", "/deed_reader.html", "/" + DATA, "/api/me", "/api/state", "/scans/page1.png"):
            self.assertEqual(self.req(path)[0], 401, path)
        self.assertEqual(self.req("/api/save", body={"deeds": {}})[0], 401)

    def test_02_refused_with_a_wrong_token(self):
        wrong = "x" * 32
        self.assertEqual(self.req("/?t=" + wrong)[0], 401)
        self.assertEqual(self.req("/deed_reader.html", cookie=wrong)[0], 401)
        self.assertEqual(self.req("/api/state", bearer=wrong)[0], 401)
        self.assertEqual(self.req("/api/save", bearer=wrong, body={"deeds": {"1": {}}})[0], 401)
        self.assertEqual(self.req("/api/state", bearer=self.tok["Anna"][:-1])[0], 401, "a token cut short")

    # ---- 2. the personal link ----
    def test_03_link_sets_cookie_and_moves_on(self):
        code, h, _ = self.req("/?t=" + self.tok["Anna"])
        self.assertEqual(code, 303)
        self.assertEqual(h["Location"], "/deed_reader.html")
        c = h["Set-Cookie"]
        self.assertIn("dr_token=" + self.tok["Anna"], c)
        self.assertIn("HttpOnly", c)
        self.assertIn("SameSite=Strict", c)
        self.assertNotIn(self.tok["Anna"], h["Location"])

    # ---- 3. what a reader may open ----
    def test_04_form_data_and_scan_load(self):
        cookie = self.tok["Anna"]
        code, h, b = self.req("/deed_reader.html", cookie=cookie)
        self.assertEqual(code, 200)
        self.assertIn(b"Deed Reader 2.1", b)
        code, h, b = self.req("/" + DATA, cookie=cookie)
        self.assertEqual(code, 200)
        self.assertTrue(b.startswith(b"window.DEED_DATA = ") or b"window.DEED_DATA = " in b[:200])
        self.assertTrue(h["Content-Type"].startswith("text/javascript"))
        code, h, b = self.req("/scans/page1.png", cookie=cookie)
        self.assertEqual((code, h["Content-Type"], b), (200, "image/png", tiny_png()))
        code, h, _ = self.req("/", cookie=cookie)
        self.assertEqual((code, h["Location"]), (303, "/deed_reader.html"))

    def test_05_reader_is_the_tokens(self):
        for who in ("Anna", "Ben"):
            code, _, b = self.req("/api/me", bearer=self.tok[who])
            self.assertEqual(code, 200)
            me = json.loads(b)
            self.assertEqual(me["reader"], who)
            self.assertEqual(me["readers"], ["Anna", "Ben"])
            self.assertIs(me["ask"], False)
            self.assertEqual(me["ask_models"], [])

    # ---- 4. private files and escaping paths ----
    def test_06_private_files_refused(self):
        cookie = self.tok["Anna"]
        for path in ("/server.py", "/make_tokens.py", "/test_server.py", "/server.example.json",
                     "/sample/config.sample.json", "/sample/README.md", "/tokens.json",
                     "/scans/note.txt", "/scans/", "/scans/missing.png",
                     "/scans/../outside.png", "/scans/%2e%2e/outside.png", "/scans/..%2Foutside.png",
                     "/scans/..%5Coutside.png", "/scans/%2e%2e%5c%2e%2e%5cserver.py",
                     "/../server.py", "/%2e%2e/deed-reader/server.py", "/sample/../server.py"):
            code, _, b = self.req(path, cookie=cookie)
            self.assertEqual(code, 404, path)
            self.assertNotIn(b"import", b, path)

    # ---- 5. saving ----
    def test_07_save_files_under_the_tokens_reader(self):
        body = {"reader": "Ben", "who": "Ben",
                "deeds": {"1": {"transcriber": "Ben", "scans": {"S1": {"text": "Anna line one"}}}}, "queries": []}
        code, _, b = self.req("/api/save", bearer=self.tok["Anna"], body=body)
        self.assertEqual(code, 200)
        r = json.loads(b)
        self.assertEqual((r["reader"], r["deeds"]), ("Anna", 1))
        self.assertEqual(len(self.log_lines("Anna")), 1)
        self.assertEqual(self.log_lines("Ben"), [], "a save naming Ben was filed under Ben")
        self.assertEqual(json.loads(self.log_lines("Anna")[0])["reader"], "Anna")

    def test_08_both_readers_visible(self):
        code, _, _ = self.req("/api/save", bearer=self.tok["Ben"],
                              body={"deeds": {"1": {"scans": {"S1": {"text": "Ben line one"}}}}})
        self.assertEqual(code, 200)
        for who in ("Anna", "Ben"):
            st = self.state(who)
            self.assertEqual(sorted(st), ["Anna", "Ben"], who)
            self.assertEqual(st["Anna"]["deeds"]["1"]["scans"]["S1"]["text"], "Anna line one")
            self.assertEqual(st["Ben"]["deeds"]["1"]["scans"]["S1"]["text"], "Ben line one")

    def test_09_second_save_is_added_not_overwritten(self):
        first = self.log_lines("Anna")[0]
        code, _, _ = self.req("/api/save", bearer=self.tok["Anna"],
                              body={"deeds": {"1": {"scans": {"S1": {"text": "Anna line one, read again"}}},
                                              "2": {"scans": {"S3": {"text": "Anna on deed 2"}}}},
                                    "queries": [{"q": "a question"}]})
        self.assertEqual(code, 200)
        lines = self.log_lines("Anna")
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], first, "the first save was changed")
        st = self.state()["Anna"]
        self.assertEqual(st["deeds"]["1"]["scans"]["S1"]["text"], "Anna line one, read again")
        self.assertEqual(st["deeds"]["2"]["scans"]["S3"]["text"], "Anna on deed 2")
        self.assertEqual(st["queries"], [{"q": "a question"}])
        # a save without queries keeps the reader's queries
        self.req("/api/save", bearer=self.tok["Anna"], body={"deeds": {"3": {"notes": "deed 3"}}})
        st = self.state()["Anna"]
        self.assertEqual((sorted(st["deeds"]), st["queries"]), (["1", "2", "3"], [{"q": "a question"}]))

    def test_10_malformed_saves_refused(self):
        a = self.tok["Anna"]
        before = len(self.log_lines("Anna"))
        self.assertEqual(self.req("/api/save", bearer=a, raw=b"not json")[0], 400)
        self.assertEqual(self.req("/api/save", bearer=a, body={"deeds": ["1"]})[0], 400)
        self.assertEqual(self.req("/api/save", bearer=a, body={"deeds": {}, "queries": "x"})[0], 400)
        self.assertEqual(self.req("/api/save", bearer=a, raw=b"")[0], 413)
        self.assertEqual(self.req("/api/nothing", bearer=a, body={})[0], 404)
        self.assertEqual(self.req("/api/ask", bearer=a, body={"q": "x"})[0], 501)
        self.assertEqual(len(self.log_lines("Anna")), before, "a refused save reached the log")

    # ---- 6. restart ----
    def test_11_restart_rebuilds_state(self):
        before = self.state()
        type(self).stop()
        type(self).start()
        self.assertEqual(self.state(), before)

    # ---- 7. settings checked at start ----
    def test_12_reserved_ports_and_short_tokens_refused(self):
        for port in (8080, 21800, 21850, 21899):
            cfg = self.write_cfg("reserved.json", port=port)
            r = subprocess.run([sys.executable, "-I", str(HERE / "server.py"), "--config", str(cfg)],
                               capture_output=True, text=True, timeout=30)
            self.assertNotEqual(r.returncode, 0, port)
            self.assertIn("reserved", r.stderr, port)
        short = self.tmp / "short_tokens.json"
        short.write_text(json.dumps({"abc123": {"reader": "Anna"}}), encoding="utf-8")
        cfg = self.write_cfg("short.json", port=free_port(), tokens_file=str(short))
        r = subprocess.run([sys.executable, "-I", str(HERE / "server.py"), "--config", str(cfg)],
                           capture_output=True, text=True, timeout=30)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("shorter than 20", r.stderr)

    # ---- 8. no token in output or logs ----
    def test_13_no_token_in_output_or_access_log(self):
        self.req("/?t=" + self.tok["Ben"])                  # make sure a link visit is in the log
        printed = "".join(self.outputs)
        log = (self.tmp / "store" / "access.log").read_text(encoding="utf-8")
        for who, t in self.tok.items():            # assertFalse, so a failure names the reader, never the token
            self.assertFalse(t in printed, "%s's token was printed" % who)
            self.assertFalse(t in log, "%s's token is in the access log" % who)


def score_nine(kind, scores, why="test"):
    return {"type": "score", "kind": kind, "parts": [{"score": s, "why": why} for s in scores]}


def score_three(kind, answers):
    return {"type": "score", "kind": kind, "answers": [{"answer": a, "why": "test"} for a in answers]}


class GraphTest(ServerHarness):
    """9. The knowledge graph. Every person, item and text here is invented.
    Anna and Ben may add; Cara may only read; Dora has a token but no graph. Gate 2's deciders are
    Anna and Mia; Mia has no token, so Anna, the recorder, enters Mia's ticks as said aloud."""
    READERS = ("Anna", "Ben", "Cara", "Dora")
    PEOPLE = {"Anna": {"id": "anna", "name": "Anna Example", "badge": "AE", "role": "author"},
              "Ben": {"id": "ben", "name": "Ben Example", "role": "author"},
              "Cara": {"id": "cara", "name": "Cara Example", "role": "reader"}}
    # K17: Dora has a label (a name and badge to show) but no place in people, so the graph stays shut to her.
    LABELS = {"Dora": {"id": "dora", "name": "Dora Example", "badge": "DE", "color": "#55606a"}}
    TEXT = "The ship Example sailed from Port A to Port B in 1650, her master John Doe."

    @classmethod
    def prepare(cls):
        t = cls.tmp
        (t / "content.json").write_text(json.dumps({
            "title": "Invented test graph",
            "people": [{"id": "mia", "name": "Mia Example", "badge": "ME"}, {"id": "base", "name": "Base graph"}],
            "graph": {"nodes": [{"id": "n1", "type": "Ship", "label": "Example"},
                                {"id": "n2", "type": "Place", "label": "Port A"}],
                      "edges": [{"source": "n1", "target": "n2", "type": "sailed_from", "confidence": "strong"}]}}),
            encoding="utf-8")
        # An earlier store, as graph_seed.py writes it: one item, a passing score, a tick and its void.
        rec = lambda col, doc: json.dumps({"t": "2026-11-01T10:00:00Z", "author": "import", "col": col, "doc": doc})
        (t / "import.jsonl").write_text("\n".join([
            rec("items", {"id": "HOP-001", "kind": "candidate identity", "words": "Is John Doe the same man?",
                          "by": "mia", "entered": "2026-11-01T09:00", "stage": "in", "history": [], "text": cls.TEXT}),
            rec("entries", {"_id": "imp-score", "item": "HOP-001", "type": "score", "by": "anna",
                            "at": "2026-11-01T10:00:00Z", "kind": "identity", "method": "test",
                            "answers": [{"n": i, "answer": "yes"} for i in (1, 2, 3)]}),
            rec("entries", {"_id": "imp-tick", "item": "HOP-001", "type": "tick", "by": "anna", "to": "aside",
                            "at": "2026-11-01T10:01:00Z"}),
            rec("entries", {"_id": "imp-void", "item": "HOP-001", "type": "void", "by": "anna", "entries": ["imp-tick"],
                            "at": "2026-11-01T10:02:00Z", "why": "a test tick"})]) + "\n", encoding="utf-8")
        (HERE / "graph.html").stat()  # the page must exist in the deed-reader folder

    @classmethod
    def write_cfg(cls, name, **over):
        graph = {"content_file": str(cls.tmp / "content.json"), "import_file": str(cls.tmp / "import.jsonl"),
                 "store_dir": str(cls.tmp / "store" / "graph"), "gate1": "rule", "people": cls.PEOPLE,
                 "labels": cls.LABELS, "gate2": {"recorder": "Anna", "deciders": ["anna", "mia"]}}
        graph.update(over.pop("graph", {}))
        return ServerHarness.write_cfg.__func__(cls, name, graph=graph, **over)

    # ---- helpers ----
    def g(self, who="Anna"):
        code, _, b = self.req("/api/graph", bearer=self.tok[who])
        self.assertEqual(code, 200)
        return json.loads(b)

    def item(self, iid, who="Anna"):
        return next(i for i in self.g(who)["items"] if i["id"] == iid)

    def post(self, who, op, obj):
        code, _, b = self.req("/api/graph", bearer=self.tok[who], body={"op": op, op: obj})
        return code, json.loads(b)

    def add(self, who="Anna", **over):
        it = {"category": "voyage", "kind": "candidate voyage", "words": "The Example may have sailed twice.",
              "text": self.TEXT, "source": "an invented deposition", "next": "Read it again."}
        it.update(over)
        code, r = self.post(who, "item", it)
        self.assertEqual(code, 200, r)
        return r["added"]

    def entry(self, who, iid, **e):
        e["item"] = iid
        return self.post(who, "entry", e)

    def graph_lines(self, reader):
        p = self.tmp / "store" / "graph" / (reader + ".jsonl")
        return p.read_text(encoding="utf-8").splitlines() if p.exists() else []

    # ---- tests ----
    def test_g01_who_may_open_the_graph(self):
        for path in ("/graph.html", "/api/graph", "/api/graph/content", "/api/graph/export"):
            self.assertEqual(self.req(path)[0], 401, path)
            self.assertEqual(self.req(path, bearer=self.tok["Dora"])[0], 403, "Dora opened " + path)
            for who in ("Anna", "Cara"):
                self.assertEqual(self.req(path, bearer=self.tok[who])[0], 200, who + " " + path)
        self.assertEqual(self.post("Dora", "item", {"category": "voyage", "words": "x"})[0], 403)
        code, _, b = self.req("/graph.html", cookie=self.tok["Ben"])
        self.assertEqual(code, 200)
        self.assertIn(b"/api/graph", b)
        code, h, _ = self.req("/graph.html?t=" + self.tok["Ben"])
        self.assertEqual((code, h["Location"]), (303, "/graph.html"), "the graph link went elsewhere")
        self.assertNotIn(self.tok["Ben"], h["Location"])
        self.assertEqual(self.req("/?t=" + self.tok["Ben"])[1]["Location"], "/deed_reader.html")
        roles = {w: json.loads(self.req("/api/me", bearer=self.tok[w])[2])["graph"] for w in self.READERS}
        self.assertEqual(roles, {"Anna": "author", "Ben": "author", "Cara": "reader", "Dora": None})

    def test_g02_a_reader_may_read_but_not_add(self):
        before = self.g("Cara")
        self.assertEqual(self.post("Cara", "item", {"category": "voyage", "words": "Cara's idea"})[0], 403)
        self.assertEqual(self.entry("Cara", "HOP-001", type="comment", text="Cara's comment")[0], 403)
        self.assertEqual(self.graph_lines("Cara"), [])
        after = self.g("Cara")
        self.assertEqual((before["items"], before["entries"]), (after["items"], after["entries"]))
        self.assertEqual(after["me"], {"reader": "Cara", "id": "cara", "name": "Cara Example", "role": "reader",
                                       "recorder": False})

    def test_g03_additions_are_signed_by_the_token_and_seen_by_all(self):
        iid = self.add("Ben", by="anna", entered_by="Anna", stage="approved", id="HOP-900")
        self.assertRegex(iid, r"^HOP-\d{3}$")
        self.assertNotEqual(iid, "HOP-900", "the browser chose the id")
        for who in ("Anna", "Ben", "Cara"):
            it = self.item(iid, who)
            self.assertEqual((it["by"], it["stage"]), ("ben", "in"), who)
            self.assertIn("Ben Example", it["entered_by"])
        self.assertEqual(len(self.graph_lines("Ben")), 1)
        self.assertEqual(self.graph_lines("Anna"), [], "Ben's item was filed under Anna")
        code, r = self.entry("Anna", iid, by="ben", text="Anna writes this", type="comment")
        self.assertEqual(code, 200, r)
        c = [e for e in self.g("Ben")["entries"] if e["_id"] == r["added"]][0]
        self.assertEqual(c["by"], "anna", "a comment was filed under the name the browser sent")
        content = json.loads(self.req("/api/graph/content", bearer=self.tok["Ben"])[2])
        self.assertEqual({p["id"] for p in content["people"]}, {"mia", "base", "anna", "ben", "cara", "dora"})
        dora = next(p for p in content["people"] if p["id"] == "dora")
        self.assertEqual((dora["name"], dora["badge"]), ("Dora Example", "DE"))
        self.assertNotIn("role", dora, "a label was given a role")
        self.assertEqual(content["content"]["title"], "Invented test graph")

    def test_g04_nothing_is_overwritten(self):
        iid = self.add("Anna", words="First wording.")
        lines = self.graph_lines("Anna")
        code, r = self.entry("Anna", iid, type="revise", words="Second wording.", why="clearer")
        self.assertEqual(code, 200, r)
        code, r = self.entry("Ben", iid, type="excerpt", quote="sailed from  Port A", location="line 1")
        self.assertEqual(code, 200, r)
        now = self.graph_lines("Anna")
        self.assertEqual(now[:len(lines)], lines, "an earlier line was changed")
        self.assertEqual(len(now), len(lines) + 1)
        it = self.item(iid)
        self.assertEqual(it["words"], "First wording.", "the item itself was changed")
        revs = [e for e in self.g()["entries"] if e["item"] == iid and e["type"] == "revise"]
        self.assertEqual(revs[0]["words"], "Second wording.")
        self.assertEqual(self.post("Anna", "update", {"id": iid, "words": "x"})[0], 400)
        self.assertEqual(self.add("Anna", id=iid) != iid, True, "an item was added under an id in use")

    def test_g05_malformed_additions_refused(self):
        before = sum(len(self.graph_lines(w)) for w in ("Anna", "Ben"))
        bad_items = [{"category": "rumour", "words": "x"}, {"category": "voyage", "words": "  "},
                     {"category": "voyage", "words": "x", "basis": "Z"}, {"category": "voyage", "words": "x" * 4001},
                     {"category": "voyage", "words": ["x"]}]
        for it in bad_items:
            self.assertEqual(self.post("Anna", "item", it)[0], 400, it)
        for e in (dict(type="comment", text=""), dict(type="excerpt", quote="not in the text at all"),
                  dict(type="revise", words="new", why=""), dict(type="delete"),
                  score_nine("voyage", [2] * 8), score_nine("voyage", [3] + [2] * 8),
                  score_nine("voyage", [True] + [2] * 8), score_three("identity", ["yes", "yes", "maybe"]),
                  score_three("identity", ["yes", "yes"]), dict(type="score", kind="gossip")):
            self.assertEqual(self.entry("Anna", "HOP-001", **e)[0], 400, e)
        self.assertEqual(self.entry("Anna", "HOP-404", type="comment", text="x")[0], 404)
        self.assertEqual(self.req("/api/graph", bearer=self.tok["Anna"], raw=b"not json")[0], 400)
        self.assertEqual(sum(len(self.graph_lines(w)) for w in ("Anna", "Ben")), before, "a refused addition was kept")

    def test_g06_import_void_and_gate_1_by_rule(self):
        it = self.item("HOP-001")
        self.assertEqual(it["stage"], "gate1", "the imported passing score did not pass Gate 1 at start")
        self.assertEqual(it["ticks"], {}, "a voided tick still counts")
        self.assertEqual(self.g()["voided"], 1)
        self.assertNotIn("imp-tick", [e["_id"] for e in self.g()["entries"]])
        self.assertTrue(any("by rule v1" in h["what"] for h in it["history"]))
        strong = self.add("Anna")
        code, r = self.entry("Ben", strong, **score_nine("voyage", [2, 1, 1, 1, 2, 2, 1, 1, 1]))   # 12; 1-4 = 5
        self.assertEqual(code, 200, r)
        self.assertEqual(self.item(strong)["stage"], "gate1")
        s = [e for e in self.g()["entries"] if e["_id"] == r["added"]][0]
        self.assertEqual((s["total"], s["floor_sum"], s["reading"], s["scorer"], s["method"]),
                         (12, 5, "strong", "Ben Example", "nine"))
        weak = self.add("Anna")
        self.entry("Ben", weak, **score_nine("voyage", [2, 2, 2, 0, 2, 2, 2, 2, 2]))        # 16, but criterion 4 is 0
        self.entry("Ben", weak, **score_nine("organisation", [1, 1, 1, 1, 2, 2, 1, 1, 1]))  # 11
        self.assertEqual(self.item(weak)["stage"], "in")
        ctx = self.add("Anna", category="context")
        self.entry("Ben", ctx, **score_nine("context", [2] * 9))
        self.assertEqual(self.item(ctx)["stage"], "in", "a context item passed Gate 1 by rule")
        lead = self.add("Anna", category="source lead")
        self.entry("Anna", lead, **score_three("source lead", ["yes", "partly", "yes"]))
        self.assertEqual(self.item(lead)["stage"], "in")
        self.entry("Anna", lead, **score_three("source lead", ["yes", "yes", "yes"]))
        self.assertEqual(self.item(lead)["stage"], "gate1")
        self.assertTrue(any(json.loads(l)["doc"]["type"] == "rule" for l in self.graph_lines("_rule")))

    def test_g07_pull_back(self):
        iid = self.add("Anna", category="identity")
        self.entry("Anna", iid, **score_three("identity", ["yes"] * 3))
        self.assertEqual(self.item(iid)["stage"], "gate1")
        self.assertEqual(self.entry("Ben", iid, type="pullback", why="")[0], 400, "a pull-back without a reason")
        code, r = self.entry("Ben", iid, type="pullback", why="the passage is misread")
        self.assertEqual(code, 200, r)
        self.assertEqual(self.item(iid)["stage"], "in")
        self.assertEqual(self.entry("Ben", iid, type="pullback", why="again")[0], 409)
        type(self).stop()
        type(self).start()
        self.assertEqual(self.item(iid)["stage"], "in", "the same score passed the item again after a restart")
        self.entry("Ben", iid, **score_three("identity", ["yes"] * 3))
        self.assertEqual(self.item(iid)["stage"], "gate1", "a new passing score did not pass")

    def test_g08_gate_2_by_two_ticks_from_the_recorder_only(self):
        iid = self.add("Ben", category="identity")
        self.entry("Ben", iid, **score_three("identity", ["yes"] * 3))
        self.assertEqual(self.item(iid)["stage"], "gate1")
        self.assertEqual(self.entry("Ben", iid, type="tick", by="ben", to="approved")[0], 403)
        self.assertEqual(self.entry("Ben", iid, type="tick", by="anna", to="approved")[0], 403)
        self.assertEqual(self.entry("Anna", iid, type="tick", by="ben", to="approved")[0], 400, "Ben is no decider")
        self.assertEqual(self.entry("Anna", iid, type="tick", by="anna", to="in")[0], 409, "Gate 1 to In by ticks")
        self.assertEqual(self.entry("Anna", iid, type="tick", by="anna", to="approved")[0], 200)
        self.assertEqual(self.entry("Anna", iid, type="agree", to="approved")[0], 409, "agreed on one tick")
        code, r = self.entry("Anna", iid, type="tick", by="mia", to="approved", quote="Yes, approve it")
        self.assertEqual(code, 200, r)
        it = self.item(iid)
        self.assertEqual((it["ready"], it["ticks"]["mia"]["via"]), ("approved", "spoken"))
        self.assertEqual(it["stage"], "gate1", "two ticks moved the item without the confirm")
        self.assertEqual(self.entry("Anna", iid, type="agree", to="approved")[0], 200)
        it = self.item(iid)
        self.assertEqual((it["stage"], it["ticks"], it["ready"]), ("approved", {}, None))
        fresh = self.add("Anna")
        self.assertEqual(self.entry("Anna", fresh, type="tick", by="anna", to="gate1")[0], 409,
                         "Gate 1 was ticked by hand")

    def test_g09_restart_replays_the_same_graph(self):
        before = self.g()
        type(self).stop()
        type(self).start()
        after = self.g()
        for k in ("items", "entries", "voided"):
            self.assertEqual(after[k], before[k], k)

    def test_g10_export_has_everything_and_no_token(self):
        self.add("Ben", words="For the export.")
        code, h, b = self.req("/api/graph/export", bearer=self.tok["Cara"])
        self.assertEqual(code, 200)
        self.assertIn("attachment", h["Content-Disposition"])
        text = b.decode("utf-8")
        ex = json.loads(text)
        self.assertIn("For the export.", [i["words"] for i in ex["items"]])
        self.assertEqual(ex["content"]["title"], "Invented test graph")
        for who, t in self.tok.items():
            self.assertFalse(t in text, "%s's token is in the export" % who)
        files = [p.read_text(encoding="utf-8") for p in (self.tmp / "store" / "graph").glob("*.jsonl")]
        for who, t in self.tok.items():
            self.assertFalse(any(t in f for f in files), "%s's token is in the graph's logs" % who)

    def test_g11_malformed_graph_settings_refused(self):
        for over, says in (({"gate1": "sometimes"}, "graph.gate1"),
                           ({"gate2": {"recorder": "Cara", "deciders": ["cara"]}}, "recorder"),
                           ({"people": {"Anna": {"id": "Anna Example!", "role": "author"}}}, "graph.people"),
                           ({"labels": {"Anna": {"id": "anna2"}}}, "keep it in one place"),
                           ({"labels": {"Eve": {"id": "cara"}}}, "keep it in one place"),
                           ({"labels": {"Eve": {"name": "No id"}}}, "graph.labels.Eve"),
                           ({"content_file": str(self.tmp / "missing.json")}, "Missing")):
            cfg = self.write_cfg("bad_graph.json", port=free_port(), graph=over)
            r = subprocess.run([sys.executable, "-I", str(HERE / "server.py"), "--config", str(cfg)],
                               capture_output=True, text=True, timeout=30)
            self.assertNotEqual(r.returncode, 0, over)
            self.assertIn(says, r.stderr, over)

    def test_g12_held_gate_1(self):
        cfg = self.write_cfg("held.json", port=free_port(), graph={"gate1": "hold",
                                                                    "store_dir": str(self.tmp / "held")})
        p = subprocess.Popen([sys.executable, "-I", "-u", str(HERE / "server.py"), "--config", str(cfg)],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                             env=server_env())
        try:
            port = json.loads(cfg.read_text(encoding="utf-8"))["port"]
            for _ in range(100):
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.1)
            r = urllib.request.Request("http://127.0.0.1:%d/api/graph" % port,
                                       headers={"Authorization": "Bearer " + self.tok["Anna"]})
            with OPENER.open(r, timeout=10) as resp:
                st = json.loads(resp.read())
            self.assertEqual(st["gate1"], "hold")
            self.assertEqual(next(i for i in st["items"] if i["id"] == "HOP-001")["stage"], "in",
                             "an item passed Gate 1 by rule while the gate was held")
        finally:
            p.terminate()
            out, _ = p.communicate(timeout=10)
        self.assertIn("Gate 1 held", out)
        for who, t in self.tok.items():
            self.assertFalse(t in out, "%s's token was printed" % who)

    def test_g13_provisional_scores_do_not_pass_gate_1(self):
        # K16 (c): a provisional score, made without re-reading the passage, never passes by rule.
        iid = self.add("Anna")
        code, r = self.entry("Ben", iid, provisional=True, **score_nine("voyage", [2] * 9))   # 18 of 18
        self.assertEqual(code, 200, r)
        s = [e for e in self.g()["entries"] if e["_id"] == r["added"]][0]
        self.assertIs(s["provisional"], True)
        self.assertEqual(self.item(iid)["stage"], "in", "a provisional score passed Gate 1")
        self.assertFalse(any(json.loads(l)["doc"].get("item") == iid for l in self.graph_lines("_rule")))
        lead = self.add("Anna", category="identity")
        self.entry("Anna", lead, provisional=True, **score_three("identity", ["yes"] * 3))
        self.assertEqual(self.item(lead)["stage"], "in", "a provisional three-question score passed")
        code, r = self.entry("Ben", iid, **score_nine("voyage", [2] * 9))                   # now re-read
        self.assertEqual(code, 200, r)
        it = self.item(iid)
        self.assertEqual(it["stage"], "gate1", "a score that is not provisional did not pass")
        self.assertTrue(any("by rule v1.1" in h["what"] for h in it["history"]))

    def test_g14_deed_scan_line_and_basis_codes(self):
        # (b), 28 Nov 2026: where in the Deed Reader an item comes from, and P always with its code.
        iid = self.add("Anna", category="identity", deed="12", scan="SCAN-0001.b", line=7, basis="P-MUC")
        for who in ("Anna", "Ben", "Cara"):
            it = self.item(iid, who)
            self.assertEqual((it["deed"], it["scan"], it["line"], it["basis"]), (12, "SCAN-0001.b", 7, "P-MUC"), who)
        bare = self.add("Anna", deed=3)
        self.assertEqual((self.item(bare)["deed"], self.item(bare)["scan"], self.item(bare)["line"]), (3, None, None))
        plain = self.add("Anna", deed="", scan="", line="")
        self.assertNotIn("deed", self.item(plain), "empty Deed Reader fields were stored")
        before = len(self.graph_lines("Anna"))
        for bad in ({"basis": "P"}, {"deed": "twelve"}, {"deed": 0}, {"deed": True}, {"deed": 12.5},
                    {"deed": 12, "scan": "SCAN 0001"}, {"deed": 12, "scan": "x" * 101},
                    {"deed": 12, "line": 4}, {"scan": "SCAN-0001"}, {"deed": 12, "scan": "SCAN-0001", "line": 0}):
            it = {"category": "voyage", "words": "x"}
            it.update(bad)
            self.assertEqual(self.post("Anna", "item", it)[0], 400, bad)
        self.assertEqual(len(self.graph_lines("Anna")), before, "a refused item was kept")
        content = json.loads(self.req("/api/graph/content", bearer=self.tok["Anna"])[2])
        self.assertIn("P-MUC", content["basis"])
        self.assertNotIn("P", content["basis"], "bare P is still offered for new items")
        page = self.req("/graph.html", bearer=self.tok["Anna"])[2]
        self.assertIn(b'href="/deed_reader.html"', page, "the graph has no link to the Deed Reader")


class PretendModels(http.server.BaseHTTPRequestHandler):
    """A pretend cluster model service on this computer: it records each request and answers."""
    seen = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(n).decode("utf-8"))
        PretendModels.seen.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
        text = body["messages"][0]["content"][0]["text"]
        if "be slow" in text:
            time.sleep(2)
        if "please fail" in text:
            out, code = {"error": "overloaded"}, 503
        elif "think too long" in text:
            out, code = {"choices": [{"message": {"content": "", "reasoning_content": "Hmm, the first letter"},
                                      "finish_reason": "length"}], "usage": {"prompt_tokens": 9, "completion_tokens": 4000}}, 200
        else:
            out, code = {"choices": [{"message": {"content": "Strong: 'Barbados'.", "reasoning_content": "b-a-r"},
                                      "finish_reason": "stop"}],
                         "usage": {"prompt_tokens": 1200, "completion_tokens": 80, "total_tokens": 1280}}, 200
        b = json.dumps(out).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


class AskTest(ServerTest):
    """D11: asking the cluster's models through the server, against the pretend service.
    The server's other behaviour is tested again with the key set (the inherited tests)."""
    KEY = "test-key-" + "k" * 30

    @classmethod
    def setUpClass(cls):
        cls.models = http.server.ThreadingHTTPServer(("127.0.0.1", 0), PretendModels)
        threading.Thread(target=cls.models.serve_forever, daemon=True).start()
        cls.models_url = "http://127.0.0.1:%d/v1" % cls.models.server_address[1]
        orig = ServerTest.write_cfg.__func__

        def write_cfg(c, name, **over):
            over.setdefault("ask_base_url", cls.models_url)
            return orig(c, name, **over)
        cls.write_cfg = classmethod(write_cfg)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.models.shutdown()

    IMG = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="

    N = [0]

    def send(self, who="Anna", **body):
        """POST a question; the server answers 202 at once (or refuses)."""
        self.N[0] += 1
        b = {"id": "Q-Test-%d" % self.N[0], "model": "glm-5.3-flash", "question": "What is this word?",
             "image": self.IMG}
        b.update(body)
        code, _, raw = self.req("/api/ask", bearer=self.tok[who] if who else None, body=b)
        return b["id"], code, (json.loads(raw) if raw[:1] == b"{" else raw)

    def collect(self, qid, who="Anna"):
        code, _, raw = self.req("/api/ask?id=" + qid, bearer=self.tok[who])
        return code, json.loads(raw)

    def ask(self, who="Anna", **body):
        """Send, then collect as the form does, until the answer is kept."""
        qid, code, r = self.send(who, **body)
        if code != 202:
            return code, r
        self.assertEqual(r["state"], "working")
        for _ in range(100):
            code, r = self.collect(qid, who)
            if code != 202:
                return code, r
            time.sleep(0.1)
        self.fail("no answer kept within 10 seconds")

    def test_05_reader_is_the_tokens(self):
        code, _, b = self.req("/api/me", bearer=self.tok["Anna"])
        me = json.loads(b)
        self.assertIs(me["ask"], True)
        self.assertEqual([m["id"] for m in me["ask_models"]],
                         ["deepseek-v4.1-flash", "deepseek-v4.1-flash:no-thinking", "glm-5.3-flash"])
        self.assertFalse(self.KEY in b.decode("utf-8"), "the key reached a browser")

    def test_10_malformed_saves_refused(self):
        self.skipTest("covered by ServerTest; here /api/ask is on")

    def test_20_ask_passes_question_image_and_key(self):
        PretendModels.seen.clear()
        code, r = self.ask(question="What is this word, please?")
        self.assertEqual(code, 200, r)
        self.assertEqual((r["answer"], r["finish"], r["model"]), ("Strong: 'Barbados'.", "stop", "glm-5.3-flash"))
        self.assertEqual(r["usage"]["prompt_tokens"], 1200)
        sent = PretendModels.seen[-1]
        self.assertEqual(sent["path"], "/v1/chat/completions")
        self.assertTrue(sent["auth"] == "Bearer " + self.KEY, "the key was not sent to the model service")
        content = sent["body"]["messages"][0]["content"]
        self.assertEqual(content[0]["text"], "What is this word, please?")
        self.assertEqual(content[1]["image_url"]["url"], self.IMG)
        self.assertEqual(sent["body"]["model"], "glm-5.3-flash")
        self.assertEqual(sent["body"]["max_tokens"], 32768, "room for thinking and a whole page")

    def test_20b_no_thinking_variant(self):
        code, r = self.ask(model="deepseek-v4.1-flash:no-thinking", question="Transcribe, no thinking")
        self.assertEqual((code, r["model"]), (200, "deepseek-v4.1-flash:no-thinking"))
        sent = [s for s in PretendModels.seen if "no thinking" in s["body"]["messages"][0]["content"][0]["text"]][-1]
        self.assertEqual(sent["body"]["model"], "deepseek-v4.1-flash", "the variant's suffix reached the service")
        self.assertEqual(sent["body"]["chat_template_kwargs"], {"enable_thinking": False})
        code, r = self.ask(model="deepseek-v4.1-flash", question="Transcribe, thinking allowed")
        sent = [s for s in PretendModels.seen if "thinking allowed" in s["body"]["messages"][0]["content"][0]["text"]][-1]
        self.assertNotIn("chat_template_kwargs", sent["body"])
        self.assertEqual(self.ask(model="glm-5.3-flash:no-thinking")[0], 400, "GLM has no such variant")

    def test_21_empty_answer_returns_reasoning(self):
        code, r = self.ask(model="deepseek-v4.1-flash", question="think too long")
        self.assertEqual(code, 200)
        self.assertEqual((r["answer"], r["finish"], r["reasoning"]), ("", "length", "Hmm, the first letter"))

    def test_22_refusals(self):
        n = len(PretendModels.seen)
        self.assertEqual(self.ask(who=None)[0], 401)
        self.assertEqual(self.ask(model="gpt-5")[0], 400)
        self.assertEqual(self.ask(question="")[0], 400)
        self.assertEqual(self.ask(question="x" * 20001)[0], 400)
        self.assertEqual(self.ask(image="https://example.org/a.jpg")[0], 400)
        self.assertEqual(self.ask(image="data:image/svg+xml;base64,PHN2Zz4=")[0], 400)
        self.assertEqual(len(PretendModels.seen), n, "a refused question reached the model service")
        self.assertEqual(self.ask(image=None)[0], 200, "a question without an image is allowed")

    def test_23_service_failure_reported_without_the_key(self):
        code, r = self.ask(question="please fail")
        self.assertEqual((code, r["http"], r["state"]), (200, 502, "done"))
        self.assertIn("503", r["error"])
        self.assertFalse(self.KEY in json.dumps(r))

    def test_25_no_connection_held_while_the_model_works(self):
        qid, code, r = self.send(question="be slow")
        self.assertEqual((code, r["state"]), (202, "working"), "the server held the connection")
        code, r = self.collect(qid)
        self.assertEqual((code, r["state"]), (202, "working"))
        self.assertEqual(self.send(id=qid, question="be slow")[1], 202, "asking again is harmless")
        for _ in range(100):
            code, r = self.collect(qid)
            if code != 202:
                break
            time.sleep(0.1)
        self.assertEqual((code, r["answer"], r["id"]), (200, "Strong: 'Barbados'.", qid))
        self.assertEqual(sum(1 for s in PretendModels.seen if "be slow" in s["body"]["messages"][0]["content"][0]["text"]),
                         1, "one question was put to the model twice")

    def test_26_answers_are_the_askers_alone_and_survive_a_restart(self):
        qid = self.send()[0]
        for _ in range(100):
            code, r = self.collect(qid)
            if code == 200:
                break
            time.sleep(0.1)
        self.assertEqual(self.collect(qid, who="Ben")[0], 404, "Ben collected Anna's answer")
        type(self).stop()
        type(self).start()
        code, r = self.collect(qid)
        self.assertEqual((code, r["answer"]), (200, "Strong: 'Barbados'."), "the answer was lost in a restart")
        self.assertEqual(self.collect("Q-never-asked")[0], 404)
        self.assertEqual(self.req("/api/ask?id=../../tokens", bearer=self.tok["Anna"])[0], 400)
        self.assertEqual(self.send(id="")[1], 400)
        self.assertEqual(self.send(id="../x")[1], 400)

    def test_24_key_never_printed_or_logged(self):
        self.ask()
        type(self).stop()      # collect what the server printed
        type(self).start()
        store = self.tmp / "store"
        texts = ["".join(self.outputs)] + [p.read_text(encoding="utf-8") for p in store.rglob("*") if p.is_file()]
        for t in texts:
            self.assertFalse(self.KEY in t, "the API key was printed or written to a file")
        ask_log = (store / "ask.log").read_text(encoding="utf-8")
        self.assertIn("model=glm-5.3-flash", ask_log)
        self.assertNotIn("What is this word", ask_log, "a question was written to the ask log")
        self.assertIn("Asking the cluster's models: on", "".join(self.outputs))
        self.assertIn("up to 32768 tokens and 600 seconds", "".join(self.outputs))


if __name__ == "__main__":
    unittest.main(verbosity=2)
