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
