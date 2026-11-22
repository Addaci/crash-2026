"""Data guard for the public crash-2026 repository.

Fails if a commit would publish archive images, data, ground truth or secrets.
Runs on every push and pull request (.github/workflows/data-guard.yml), and can be
run locally before pushing:  python .github/scripts/data_guard.py

Checks every file that git tracks (or the paths given on the command line):
  1. file types that never belong here (images, PDFs, archives, scans);
  2. folders that hold data (data/, raw*, htr/, translations/, readings/, ...);
  3. secrets (.env, *.key);
  4. files over 1 MB;
  5. inside text files: archive scan identifiers (e.g. KLAB04781000044),
     Amsterdam index record addresses, PAGE XML and Transkribus metadata.

A file that must pass anyway is listed, with a reason, in .github/data-guard-allow.txt.
Standard library only.
"""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ALLOW_FILE = ROOT / ".github" / "data-guard-allow.txt"
SELF = {".github/scripts/data_guard.py", ".github/data-guard-allow.txt"}  # the guard's own files name the patterns

BAD_EXT = {".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".jp2", ".bmp", ".webp",
           ".pdf", ".zip", ".7z", ".tar", ".gz", ".rar", ".parquet", ".duckdb", ".sqlite", ".db"}
OK_IMAGE_DIR = "docs/figures/"          # deliberate documentation figures only
BAD_DIRS = re.compile(r"(^|/)(data|scans|raw[^/]*|htr|translations|readings|colin-notes|"
                      r"queries|answers|ground-truth|test-set)/")
SECRETS = re.compile(r"(^|/)(\.env(\..*)?|.*\.key|config\.local\..*)$")
MAX_BYTES = 1_000_000
TEXT_EXT = {".py", ".js", ".mjs", ".html", ".htm", ".css", ".md", ".txt", ".json", ".csv",
            ".tsv", ".xml", ".yml", ".yaml", ".cff", ".sh", ".toml", ".ini", ""}
CONTENT = [
    (re.compile(r"\bKLA[A-Z]?\d{8,11}\b"), "an archive scan identifier"),
    (re.compile(r"id\.archief\.amsterdam/(resources/records/)?[0-9a-f]{8}-[0-9a-f]{4}"), "an Amsterdam index record address"),
    (re.compile(r"<PcGts\b|TranskribusMetadata"), "PAGE XML or Transkribus metadata"),
]


def tracked(paths):
    if paths:
        return paths
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return [p for p in out.stdout.splitlines() if p]


def allowed():
    if not ALLOW_FILE.exists():
        return set()
    return {l.split("#")[0].strip() for l in ALLOW_FILE.read_text(encoding="utf-8").splitlines()
            if l.split("#")[0].strip()}


def check(path, allow):
    rel = path.replace("\\", "/")
    if rel in allow or rel in SELF:
        return []
    problems = []
    p = ROOT / rel
    ext = p.suffix.lower()
    if ext in BAD_EXT and not (rel.startswith(OK_IMAGE_DIR) and ext in {".png", ".svg"}):
        problems.append(f"file type {ext} is not allowed in this repository")
    if BAD_DIRS.search(rel):
        problems.append("sits in a data folder")
    if SECRETS.search(rel):
        problems.append("looks like a secret or local settings file")
    if p.exists():
        size = p.stat().st_size
        if size > MAX_BYTES:
            problems.append(f"is {size / 1e6:.1f} MB (limit 1 MB)")
        if ext in TEXT_EXT and size <= 20 * MAX_BYTES:
            text = p.read_text(encoding="utf-8", errors="ignore")
            for rx, what in CONTENT:
                m = rx.search(text)
                if m:
                    line = text.count("\n", 0, m.start()) + 1
                    problems.append(f"contains {what} (line {line})")
    return problems


def main():
    allow = allowed()
    failures = {}
    files = tracked(sys.argv[1:])
    for f in files:
        probs = check(f, allow)
        if probs:
            failures[f] = probs
    if failures:
        print("DATA GUARD: this commit would publish material that must stay private.\n")
        for f, probs in failures.items():
            for pr in probs:
                print(f"  {f}: {pr}")
        print("\nRemove these files (git rm --cached <file>), or, if one truly belongs here,"
              "\nlist it with a reason in .github/data-guard-allow.txt.")
        sys.exit(1)
    print(f"DATA GUARD: {len(files)} files checked, nothing restricted found.")


if __name__ == "__main__":
    main()
