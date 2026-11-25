"""Test the Deed Reader's sample: it builds, it is clean, and the form opens it.

Part of the Deed Reader (crash-2026). Standard library only; sends no request.
    python -I test_sample.py          (from the deed-reader folder, or give its path)

1. The inputs: make_sample_inputs.py, run into a temporary folder, gives exactly the committed sample/inputs/.
2. The build: build_deed_data.py, run on those inputs into a temporary file, gives exactly the committed
   sample/sample_data.js (the build time aside).
3. The fields: every field the form reads is there, the data is marked as a sample, and it has its own
   storage name, so trying the sample never mixes with real readings in the same browser.
4. The guard: the data guard finds nothing restricted in deed-reader/sample/, and no archive scan
   identifier or record address appears in any sample file, whatever its type.
5. The form: a copy of deed_reader.html with sample/ beside it and no data/ folder is opened in headless
   Chrome with a new, empty profile (your own Chrome profile is never touched). The page must show the
   sample banner, list every deed and open the first. Skipped if Chrome is not found; set REQUIRE_CHROME=1
   to make a missing Chrome fail the test (the GitHub workflow does).
"""
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent            # deed-reader/
SAMPLE = HERE / "sample"
ROOT = HERE.parent
DATA_PREFIX = "window.DEED_DATA = "


def load_js(path: pathlib.Path) -> dict:
    t = path.read_text(encoding="utf-8")
    i = t.index(DATA_PREFIX) + len(DATA_PREFIX)
    return json.loads(t[i:].rstrip().rstrip(";"))


def module(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def tree(folder: pathlib.Path) -> dict:
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


def find_chrome():
    for c in [os.environ.get("CHROME", ""), "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"]:
        if c and shutil.which(c):
            return shutil.which(c)
    for c in [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]:
        if pathlib.Path(c).exists():
            return c
    return None


class SampleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="deed-reader-test-"))
        cls.data = load_js(SAMPLE / "sample_data.js")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)  # only the temporary folder this test made

    def test_1_inputs_match_generator(self):
        gen = module(SAMPLE / "make_sample_inputs.py", "make_sample_inputs")
        gen.OUT = self.tmp / "inputs"
        gen.sys.argv = ["make_sample_inputs.py"]
        gen.main()
        self.assertEqual(tree(gen.OUT), tree(SAMPLE / "inputs"),
                         "sample/inputs/ differs from make_sample_inputs.py: re-run it with --replace")

    def test_2_build_matches_committed(self):
        cfg = json.loads((SAMPLE / "config.sample.json").read_text(encoding="utf-8"))
        cfg["input_root"] = str((SAMPLE / cfg["input_root"]).resolve())
        cfg["out"] = str(self.tmp / "built.js")
        cp = self.tmp / "config.json"
        cp.write_text(json.dumps(cfg), encoding="utf-8")
        r = subprocess.run([sys.executable, "-I", "-X", "utf8", str(HERE / "build_deed_data.py"), "--config", str(cp)],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        built = load_js(self.tmp / "built.js")
        a, b = dict(built), dict(self.data)
        a.pop("built"), b.pop("built")
        self.assertEqual(a, b, "sample/sample_data.js is out of date: rebuild it (see sample/README.md)")

    def test_3_fields_the_form_reads(self):
        d = self.data
        self.assertTrue(d["sample"])
        self.assertNotEqual(d["ui"].get("storage_key", "deedreader"), "deedreader")
        self.assertGreaterEqual(len(d["ui"]["models"]), 1)
        deeds = d["deeds"]
        self.assertEqual(len(deeds), 4)
        for x in deeds:
            for k in ("no", "batch", "date", "type", "language", "inventory", "notary", "check_tier",
                      "machine_text_archive", "scans", "syntheses"):
                self.assertIn(k, x, f"deed {x.get('no')}: {k}")
            self.assertTrue(x["scans"], f"deed {x['no']} has no scans")
            for s in x["scans"]:
                for k in ("id", "w", "h", "jp2_bytes", "file", "machine_text", "model_readings", "also_in", "translations"):
                    self.assertIn(k, s, f"deed {x['no']} scan {s.get('id')}: {k}")
            m = x["meta"]
            if m is not None:
                for k in ("title", "date", "type", "inventory", "inventory_title", "record_url", "index_file", "fetched_utc"):
                    self.assertIn(k, m)
                for k in ("language", "persons", "places", "note"):
                    self.assertIsInstance(m[k], list)
                self.assertIsInstance(m["other_fields"], dict)
        by = {x["no"]: x for x in deeds}
        self.assertEqual(by[1]["scans"][1]["also_in"], [2], "the shared scan should point to deed 2")
        s1 = by[1]["scans"][0]
        self.assertEqual(len(s1["machine_text"]), 2)
        self.assertEqual(len(s1["model_readings"]), 1)
        self.assertTrue(s1["translations"][0]["check"]["sha_match"], "the translation's fingerprint should match its HTR")
        self.assertEqual(len(by[1]["syntheses"]), 1)
        self.assertIsNone(by[4]["meta"])
        self.assertEqual(d["problems"], ["deed 4: no index record on disk"])
        self.assertEqual(d["htr_summary"]["unplaced_files"], [])

    def test_4_guard_and_content(self):
        guard = module(ROOT / ".github" / "scripts" / "data_guard.py", "data_guard")
        allow = guard.allowed()
        files = [p.relative_to(ROOT).as_posix() for p in sorted(SAMPLE.rglob("*"))
                 if p.is_file() and "__pycache__" not in p.parts]
        problems = {f: guard.check(f, allow) for f in files}
        self.assertEqual({f: p for f, p in problems.items() if p}, {})
        for f in files:
            text = (ROOT / f).read_text(encoding="utf-8", errors="ignore")
            for rx, what in guard.CONTENT:
                self.assertIsNone(rx.search(text), f"{f} contains {what}")
            self.assertNotIn("archief.amsterdam", text, f"{f} names an archive address")

    def test_5_form_opens_sample_in_chrome(self):
        chrome = find_chrome()
        if not chrome:
            if os.environ.get("REQUIRE_CHROME"):
                self.fail("Chrome not found and REQUIRE_CHROME is set")
            self.skipTest("Chrome not found")
        site = self.tmp / "site"
        (site / "sample").mkdir(parents=True)
        shutil.copy(HERE / "deed_reader.html", site / "deed_reader.html")
        shutil.copy(SAMPLE / "sample_data.js", site / "sample" / "sample_data.js")
        profile = self.tmp / "chrome-profile"
        r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
                            "--no-default-browser-check", f"--user-data-dir={profile}",
                            "--allow-file-access-from-files", "--virtual-time-budget=5000",
                            "--dump-dom", (site / "deed_reader.html").as_uri()],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        dom = r.stdout
        n = len(self.data["deeds"])
        self.assertRegex(dom, r"<body[^>]*>\s*<p class=\"warn\"[^>]*><b>Sample data:</b>", "no sample banner")
        self.assertRegex(dom, rf'id="listcount"[^>]*>{n} of {n} deeds<', "the deed list did not fill")
        self.assertRegex(dom, r'id="deedtitle"[^>]*> · deed 1 \(', "the first deed did not open")
        self.assertNotRegex(dom, r"<body[^>]*>\s*(<p[^>]*>.*?</p>\s*)*<p class=\"warn\" style=\"padding:10px\">",
                            "the form says the data did not load")


if __name__ == "__main__":
    unittest.main(verbosity=2)
