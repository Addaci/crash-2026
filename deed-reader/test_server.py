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
"""
import json
import os
import pathlib
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
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


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="deed-reader-server-test-"))
        t = cls.tmp
        (t / "scans").mkdir()
        (t / "scans" / "page1.png").write_bytes(tiny_png())
        (t / "scans" / "note.txt").write_text("not an image", encoding="utf-8")
        (t / "outside.png").write_bytes(tiny_png())          # beside the scan folder, never to be served
        cls.tokens_file = t / "tokens.json"
        r = subprocess.run([sys.executable, "-I", str(HERE / "make_tokens.py"), "--out", str(cls.tokens_file),
                            "Anna", "Ben"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
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
    def write_cfg(cls, name, **over):
        c = {"bind": "127.0.0.1", "port": 8765, "form_dir": str(HERE), "data_file": DATA,
             "store_dir": str(cls.tmp / "store" / "readings"), "access_log": str(cls.tmp / "store" / "access.log"),
             "tokens_file": str(cls.tokens_file), "scan_mounts": {"/scans/": str(cls.tmp / "scans")}}
        c.update(over)
        p = cls.tmp / name
        p.write_text(json.dumps(c, indent=1), encoding="utf-8")
        return p

    @classmethod
    def start(cls):
        cls.proc = subprocess.Popen([sys.executable, "-I", "-u", str(HERE / "server.py"), "--config", str(cls.cfg)],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
