#!/usr/bin/env python3
"""Make the knowledge graph's content file and import log from an ML-088-style page (28 Nov 2026).

Part of the Deed Reader team server (server.py 0.3). Standard library only; reads two inputs as
data and runs nothing from them:
  --page  the published page, saved as HTML (its base network, people, texts and settings are in it)
  --db    a folder with the page's store, one JSON file per document: items/<id>.json and
          entries/<id>.json (as the artifact database tool saves them)
and writes, into --out:
  graph_content.json  the people, texts, groups and base network the server shows (content_file)
  import.jsonl        every item and entry, one line each, for the server to read (import_file)

Both outputs are research data: keep them on the cluster, never in the repository.
    python -I graph_seed.py --page ML-088.html --db store-copy --out graph-out
"""
import argparse
import glob
import hashlib
import html
import json
import os
import re
import sys
import time


def grab(pattern, text, what, flags=re.S):
    m = re.search(pattern, text, flags)
    if not m:
        sys.exit("Could not find %s in the page." % what)
    return m.group(1)


def between(text, start, end, what, start_at=0):
    i = text.find(start, start_at)
    j = text.find(end, i + len(start)) if i >= 0 else -1
    if i < 0 or j < 0:
        sys.exit("Could not find %s in the page." % what)
    return text[i:j]


def plain(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def people_from(page, annotators):
    """Each contributor, with the colour the page gives them (light, then dark)."""
    cols = {}
    for pid, col in re.findall(r"--a-([a-z0-9_-]+):(#[0-9a-fA-F]{3,8})", page):
        cols.setdefault(pid, []).append(col)
    out = []
    for a in annotators:
        c = cols.get(a.get("id"), [])
        p = {k: a[k] for k in ("id", "name", "badge", "affiliation", "role") if a.get(k)}
        if c:
            p["color"] = c[0]
        if len(c) > 1:
            p["color_dark"] = c[1]
        out.append(p)
    return out


def content_from(page, source_name):
    G = json.loads(grab(r"const G\s*=\s*(\{.*?\});\s*\n", page, "the base network (const G)"))
    gh = json.loads(grab(r"const GH\s*=\s*(\{.*?\});", page, "the volume texts (const GH)"))
    first = set(json.loads(grab(r"const ENG\s*=\s*new Set\((\[.*?\])\);", page, "the first group's people (ENG)")))
    groups = json.loads(grab(r"const GROUPS\s*=\s*(\[\[.*?\]\]);", page, "the groups (const GROUPS)"))
    groups = [[g, label, "var(%s)" % col if col.startswith("--") else col] for g, label, col in groups]
    sides = {g: float("0." + x) for g, x in re.findall(r'd\.group==="([^"]+)"\?W\*\.(\d+)', page)}
    start = json.loads(grab(r"const start\s*=\s*(\[\[.*?\]\]);", page, "the starting points (const start)"))
    # People are split between the first two groups, as the page does it.
    for n in G.get("nodes", []):
        n["group"] = (groups[0][0] if n.get("id") in first else groups[1][0]) if n.get("type") == "Person" else n.get("type")
    about = between(page, '<details class="aboutfold"', "</details>", "the opening section")
    if "<details" in about[10:]:
        sys.exit("The opening section has a fold inside it; this script expects none.")
    about = re.sub(r"^<details[^>]*>\s*<summary>.*?</summary>", "", about, flags=re.S).strip()
    hop = page.find('id="p-hopper"')
    intro = between(page, '<div class="purpose">', '<section class="where"', "the Hopper's introduction", hop).strip()
    if intro.count("<div") != intro.count("</div>"):
        sys.exit("The Hopper's introduction is not one closed block; this script expects it to be.")
    criteria = between(page, '<details class="svkey" id="criteria">', '<div class="scorebox" id="scorewhy">', "the criteria").strip()
    extra = between(page, '<div class="cols">', '<section class="panel" id="p-hopper"', "the method section").strip()
    extra = extra[:extra.rfind("</div>")].rstrip()  # the graph panel's own closing tag
    extra = re.sub(r'<section>\s*<h2>Open questions</h2>\s*<ol class="q" id="qs"></ol>\s*</section>', "", extra)
    panels = []
    r0 = page.find('<section class="panel" id="p-readings"')
    if r0 >= 0:
        body = page[page.find(">", r0) + 1:page.find("<script src=", r0)]
        body = body[:body.rfind("</section>")].strip()
        label = plain(grab(r'data-tab="readings"[^>]*>(.*?)</button>', page, "the readings tab's name"))
        panels.append({"id": "readings", "label": label, "html": body})
    start_title = plain(grab(r'<div class="kind">Where to start</div><h3>(.*?)</h3>', page, "the starting title"))
    start_text = plain(grab(r'<div class="kind">Where to start</div><h3>.*?</h3>\s*<p class="small">(.*?)</p>', page,
                            "the starting text"))
    return {
        "title": plain(grab(r"<h1>(.*?)</h1>", page, "the heading")),
        "short_title": plain(grab(r"<title>(.*?)</title>", page, "the title")),
        "eyebrow": plain(grab(r'<div class="eyebrow">(.*?)</div>', page, "the eyebrow")),
        "people": people_from(page, G.get("annotators") or []),
        "groups": groups, "sides": sides, "hidden_groups": ["Source"],
        "start": start, "start_title": start_title, "start_text": start_text,
        "gh_texts": gh, "graph": {k: G.get(k) for k in ("nodes", "edges", "annotations") if k in G},
        "about_html": about, "hopper_intro_html": intro, "criteria_html": criteria, "graph_extra_html": extra,
        "panels": panels,
        "source": {"page": source_name, "sha256": hashlib.sha256(page.encode("utf-8")).hexdigest(),
                   "made": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "by": "graph_seed.py"},
    }


def import_lines(db):
    lines = []
    for col in ("items", "entries"):
        docs = []
        for path in sorted(glob.glob(os.path.join(db, col, "*.json"))):
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
            if not isinstance(doc, dict):
                sys.exit("Not a document: " + path)
            if col == "items":
                if not doc.get("id"):
                    doc["id"] = os.path.splitext(os.path.basename(path))[0]
            else:
                doc["_id"] = os.path.splitext(os.path.basename(path))[0]
            docs.append(doc)
        docs.sort(key=lambda d: str(d.get("at") or d.get("entered") or ""))
        for d in docs:
            lines.append({"t": str(d.get("at") or d.get("entered") or ""), "author": "import", "col": col, "doc": d})
    return lines


def main():
    ap = argparse.ArgumentParser(description="Make graph_content.json and import.jsonl from a saved page and its store")
    ap.add_argument("--page", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with open(a.page, encoding="utf-8") as f:
        page = f.read()
    content = content_from(page, os.path.basename(a.page))
    lines = import_lines(a.db)
    os.makedirs(a.out, exist_ok=True)
    for name in ("graph_content.json", "import.jsonl"):
        if os.path.exists(os.path.join(a.out, name)):
            sys.exit("Not overwriting %s; give an empty --out folder." % os.path.join(a.out, name))
    with open(os.path.join(a.out, "graph_content.json"), "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=1)
    with open(os.path.join(a.out, "import.jsonl"), "w", encoding="utf-8") as f:
        for rec in lines:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    n_items = sum(1 for r in lines if r["col"] == "items")
    print("graph_content.json: %d nodes, %d edges, %d notes, %d people, %d extra panel(s)" % (
        len(content["graph"].get("nodes") or []), len(content["graph"].get("edges") or []),
        len(content["graph"].get("annotations") or []), len(content["people"]), len(content["panels"])))
    print("import.jsonl: %d items, %d entries" % (n_items, len(lines) - n_items))
    print("Both are research data: keep them on the cluster, never in the repository.")


if __name__ == "__main__":
    main()
