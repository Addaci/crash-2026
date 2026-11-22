"""Build the data file the Deed Reader opens (data/deed_data.js).

Part of the Deed Reader (crash-2026). Standard library only. Reads local files only; sends no request.
Made from Build_Deed_Reader_Data v1.2 (13 Nov 2026, Claude Opus 5.5 for Colin Greenstreet); the reading
of index records, scans, HTR, translations and model readings is unchanged. What changed: every path and
every collection-specific setting now comes from a settings file, and the form's display settings travel
in the data as "ui". History in CHANGELOG.md.

Settings
  config.example.json   in the repository: every setting, with neutral values.
  config.local.json     your own copy, never committed (the data guard refuses it): real paths and values.
  python -I build_deed_data.py                  uses config.local.json beside this script
  python -I build_deed_data.py --config X.json  uses another settings file
  --replace             allow overwriting an existing output file (otherwise it stops)

Inputs (all under "input_root", folder names set in the settings file)
  register CSV (deed numbers, batch, check tier, notary); the request log and the saved index records;
  scan folders; the archive's machine text; htr/<source>/ (.txt with a "KEY: value" header above "---",
  or PAGE XML; PROVENANCE.txt adds fields to every file below it); translations/<language>/;
  a folder of model readings (basis I). Any input folder that does not exist is skipped.
Output
  out (default data/deed_data.js beside this script). Image paths are written relative to the form,
  so the form opens them from wherever the input folder is. HTR and translation files keep paths relative
  to input_root, so corrections already recorded against them still match.
"""
import csv
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import sys
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent          # the deed-reader folder, where the form is
_spec = importlib.util.spec_from_file_location("saa_jsonld", HERE / "saa_jsonld.py")
saa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(saa)

REGION = re.compile(r"^\s*(Region\d*|TextRegion\d*)\s*$", re.I)
UNPLACED = []


def load_config() -> dict:
    p = HERE / "config.local.json"
    if "--config" in sys.argv:
        p = pathlib.Path(sys.argv[sys.argv.index("--config") + 1]).resolve()
    if not p.exists():
        sys.exit(f"No settings file: {p}. Copy config.example.json to config.local.json and fill it in.")
    c = json.loads(p.read_text(encoding="utf-8"))
    c["_file"] = p
    root = pathlib.Path(c.get("input_root", "."))
    c["_root"] = (root if root.is_absolute() else (p.parent / root)).resolve()
    out = pathlib.Path(c.get("out", "data/deed_data.js"))
    c["_out"] = (out if out.is_absolute() else (HERE / out)).resolve()
    return c


def rel_root(c, f: pathlib.Path) -> str:
    return f.relative_to(c["_root"]).as_posix()


def rel_form(f: pathlib.Path) -> str:
    """A path the form (in HERE) can open."""
    return pathlib.Path(os.path.relpath(f, HERE)).as_posix()


def scans_on_disk(c) -> dict:
    found = {}
    for folder, prefix in c.get("scan_dirs", []):
        d = c["_root"] / folder
        if not d.exists():
            continue
        for f in sorted(d.glob(prefix + "*.jpg")):
            sid = f.stem[len(prefix):]
            found.setdefault(sid, []).append(rel_form(f))
    return found


def place(c, name: str, known: set) -> str:
    """The scan id in a file name, only if that scan exists in the deed data (longest pattern first)."""
    for m in re.finditer(c.get("scan_id_pattern", r"(?!)"), name):
        if m.group(0) in known:
            return m.group(0)
    for sid in sorted(known, key=len, reverse=True):
        if sid in name:
            return sid
    return ""


def header_fields(head: str) -> dict:
    out = {}
    for line in head.splitlines():
        m = re.match(r"([A-Z][A-Z0-9_ ]*?)(?: \([^)]*\))?:\s*(.*)", line)
        if m:
            out[m.group(1).strip().replace(" ", "_")] = m.group(2).strip()
    return out


def texts_by_scan(c, folder: pathlib.Path, known: set, exts=(".txt",)) -> dict:
    out = {}
    if not folder.exists():
        return out
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() not in exts:
            continue
        sid = place(c, f.name, known)
        if not sid:
            UNPLACED.append(rel_root(c, f))
            continue
        raw = f.read_text(encoding="utf-8")
        head, _, body = raw.partition("\n---\n")
        if not body:
            head, body = "", raw
        out.setdefault(sid, []).append({
            "file": rel_root(c, f), "header": head.strip(), "text": body.rstrip(),
            "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest()})
    return out


def source_info(c, folder_name: str) -> dict:
    s = dict(c.get("htr_sources", {}).get(folder_name, {}))
    s.setdefault("class", folder_name)
    s.setdefault("label", folder_name)
    s.setdefault("made_by", "not stated")
    s.setdefault("platform", "not stated")
    s.setdefault("corrected_default", "not stated")
    return s


def prov_for(entry: dict, s: dict, extra: dict) -> dict:
    """Provenance fields for the form, from the source settings, PROVENANCE.txt and the file header."""
    h = dict(extra)
    h.update(header_fields(entry.get("header", "")))
    basis = h.get("BASIS", "P-MUC")
    return {"label": s["label"] + (" · " + h["MODEL"] if h.get("MODEL") else ""),
            "made_by": h.get("MADE_BY", s["made_by"]), "platform": h.get("PLATFORM", s["platform"]),
            "model": h.get("MODEL") or "not stated",
            "corrected": h.get("CORRECTED", s["corrected_default"]),
            "fetched": h.get("READ") or h.get("EXPORTED") or h.get("FETCHED", "not stated"),
            "route": h.get("ROUTE", ""), "basis": basis.split(" ")[0] if basis else "P-MUC",
            "basis_note": basis, "url": h.get("URL", ""), "document": h.get("SOURCE", "")}


def page_xml(f: pathlib.Path) -> dict:
    """Text, image file name and Transkribus metadata from one PAGE XML file."""
    import xml.etree.ElementTree as ET
    root = ET.parse(f).getroot()
    ns = {"p": root.tag.split("}")[0].strip("{")} if root.tag.startswith("{") else {"p": ""}
    q = (lambda t: "p:" + t) if ns["p"] else (lambda t: t)
    page = root.find(q("Page"), ns)
    meta = root.find(q("Metadata"), ns)
    info = {}
    if meta is not None:
        for t in ("Creator", "Created", "LastChange", "Comments"):
            e = meta.find(q(t), ns)
            if e is not None and e.text:
                info[t] = e.text.strip()
        for e in meta.iter():
            if e.tag.endswith("TranskribusMetadata"):
                info.update(dict(e.attrib))
    lines = []
    if page is not None:
        for i, r in enumerate(page.findall(".//" + q("TextRegion"), ns), 1):
            lines.append(f"Region{i}")
            for tl in r.findall(q("TextLine"), ns):
                u = tl.find(q("TextEquiv") + "/" + q("Unicode"), ns)
                if u is not None and u.text is not None:
                    lines.append(u.text)
    head = "\n".join(f"{k}: {v}" for k, v in info.items())
    return {"image": page.get("imageFilename", "") if page is not None else "", "header": head,
            "text": "\n".join(lines), "info": info}


def htr_by_scan(c, known: set) -> dict:
    """HTR files under htr/<source>/ (any depth): .txt with header, or PAGE XML."""
    out = {}
    htr_dir = c["_root"] / c.get("htr_dir", "htr")
    if not htr_dir.exists():
        return out
    for src_dir in sorted(p for p in htr_dir.iterdir() if p.is_dir()):
        s = source_info(c, src_dir.name)
        for f in sorted(src_dir.rglob("*")):
            if f.suffix.lower() not in (".txt", ".xml") or f.name.upper() == "PROVENANCE.TXT":
                continue
            extra = {}
            for d in [src_dir] + [p for p in f.parents if src_dir in p.parents]:
                pf = d / "PROVENANCE.txt"
                if pf.exists():
                    extra.update(header_fields(pf.read_text(encoding="utf-8")))
            raw = f.read_bytes()
            if f.suffix.lower() == ".xml":
                x = page_xml(f)
                sid = place(c, x["image"], known) or place(c, f.name, known)
                entry = {"header": x["header"], "text": x["text"]}
                if x["info"].get("Created"):
                    extra.setdefault("EXPORTED", x["info"]["Created"])
                if x["info"].get("status"):
                    extra.setdefault("CORRECTED", "Transkribus page status " + x["info"]["status"]
                                     + " (NEW or IN_PROGRESS: machine only; DONE, FINAL or GT: checked by hand)")
            else:
                sid = place(c, f.name, known)
                t = raw.decode("utf-8")
                head, _, body = t.partition("\n---\n")
                if not body:
                    head, body = "", t
                entry = {"header": head.strip(), "text": body.rstrip()}
            if not sid:
                UNPLACED.append(rel_root(c, f))
                continue
            entry.update({"file": rel_root(c, f), "sha256": hashlib.sha256(raw).hexdigest(), "source": s["class"]})
            entry["prov"] = prov_for(entry, s, extra)
            out.setdefault(sid, []).append(entry)
    return out


def source_lines(text: str) -> list:
    """The numbered lines of an HTR text, as the form numbers them (region labels not counted)."""
    return [l for l in text.split("\n") if not REGION.match(l)]


def read_translations(c, deeds: list, problems: list) -> dict:
    """translations/<lang>/*.txt (diplomatic, one scan) and *.md (synthesis, one deed); newest version only."""
    summary = {"diplomatic": 0, "synthesis": 0, "files": []}
    for d in deeds:
        d["syntheses"] = []
        for s in d["scans"]:
            s["translations"] = []
    tr_dir = c["_root"] / c.get("translations_dir", "translations")
    if not tr_dir.exists():
        return summary
    byno = {d["no"]: d for d in deeds}
    files = [f for f in sorted(tr_dir.rglob("*")) if f.suffix.lower() in (".txt", ".md") and "archive" not in f.parts]

    def vkey(f):
        m = re.search(r"_v(\d+)\.(\d+)_\d{8}", f.name)
        return (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    newest = {}
    for f in files:
        stem = (f.parent / re.sub(r"_v\d+\.\d+_\d{8}", "", f.name)).as_posix()
        if stem not in newest or vkey(f) > vkey(newest[stem]):
            newest[stem] = f
    summary["superseded"] = [rel_root(c, f) for f in files if f not in newest.values()]
    for f in files:
        if f not in newest.values():
            continue
        rel = rel_root(c, f)
        raw = f.read_text(encoding="utf-8")
        head, _, body = raw.partition("\n---\n")
        h = header_fields(head)
        lang = h.get("LANGUAGE", f.parent.name)
        kind = h.get("KIND", "synthesis" if f.suffix.lower() == ".md" else "diplomatic").lower()
        try:
            d = byno[int(h.get("DEED", "0"))]
        except (ValueError, KeyError):
            problems.append(f"translation {rel}: DEED missing or unknown")
            continue
        entry = {"file": rel, "lang": lang, "kind": kind, "prov": h, "header": head.strip(),
                 "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest()}
        if kind == "synthesis":
            entry["text"] = body.strip()
            d["syntheses"].append(entry)
            summary["synthesis"] += 1
            summary["files"].append(rel)
            continue
        s = next((x for x in d["scans"] if x["id"] == h.get("SCAN", "")), None)
        if not s:
            problems.append(f"translation {rel}: SCAN {h.get('SCAN', '')!r} is not a scan of deed {d['no']}")
            continue
        lines, ranges, notes = {}, [], {}
        for l in body.split("\n"):
            m = re.match(r"^(\d+)-(\d+) \| (.*)$", l)
            if m:
                ranges.append({"from": int(m.group(1)), "to": int(m.group(2)), "text": m.group(3)})
                continue
            m = re.match(r"^(\d+) \| (.*)$", l)
            if m:
                lines[m.group(1)] = m.group(2)
                continue
            m = re.match(r"^(\d+) note: (.*)$", l)
            if m:
                notes.setdefault(m.group(1), []).append(m.group(2))
        entry.update({"lines": lines, "ranges": ranges, "notes": notes})
        src = next((i for i in s["machine_text"] if i["file"] == h.get("SOURCE_FILE", "")), None)
        check = {"source_found": bool(src)}
        if src:
            sl = source_lines(src["text"])
            covered = {int(k) for k in lines} | {n for r in ranges for n in range(r["from"], r["to"] + 1)}
            check.update({
                "source_lines": len(sl),
                "missing": [n for n in range(1, len(sl) + 1) if n not in covered],
                "extra": sorted(n for n in covered if n > len(sl)),
                "sha_now": hashlib.sha256("\n".join(sl).encode("utf-8")).hexdigest(),
            })
            check["sha_match"] = check["sha_now"] == h.get("SOURCE_SHA256", "")
            if check["missing"] or check["extra"] or not check["sha_match"]:
                problems.append(f"translation {rel}: missing lines {check['missing'][:10]}, extra {check['extra'][:10]}, "
                                f"fingerprint {'matches' if check['sha_match'] else 'DIFFERS'}")
        elif h.get("SOURCE_KIND", "HTR") == "HTR":
            problems.append(f"translation {rel}: SOURCE_FILE not among this scan's HTR")
        entry["check"] = check
        s["translations"].append(entry)
        summary["diplomatic"] += 1
        summary["files"].append(rel)
    unrev = lambda e: e["prov"].get("REVIEWED_BY", "none").lower() in ("", "none")
    for d in deeds:  # a reviewed translation comes first
        for s in d["scans"]:
            s["translations"].sort(key=lambda e: (unrev(e), e["file"]))
        d["syntheses"].sort(key=lambda e: (unrev(e), e["file"]))
    return summary


def main() -> None:
    c = load_config()
    R = c["_root"]
    out_path = c["_out"]
    if out_path.exists() and "--replace" not in sys.argv:
        sys.exit(f"STOP: {out_path} exists; add --replace to overwrite it.")
    raw_index = R / c.get("index_dir", "index")
    log_file = raw_index / c.get("request_log", "request_log.jsonl")
    log = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines() if l.strip()] if log_file.exists() else []
    by_index = {r["url"].rsplit("/", 1)[1]: r for r in log}
    disk = scans_on_disk(c)
    rows = list(csv.DictReader(open(R / c["register"], encoding="utf-8")))
    known = {s.strip() for r in rows for s in r["scans"].split(";") if s.strip()}
    for e in c.get("extra_deeds", []):
        p = saa.parse(R / e["file"])
        rows.append({"no": str(e["no"]), "batch": e.get("batch", ""), "date": p["date_index"], "deed_type": p["type_index"],
                     "language": ", ".join(p["specs"].get("taal", [])), "inventory": p["inv"], "index_id": e["index_id"],
                     "scans": " ; ".join(s["name"] for s in p["scans"]), "_how": e.get("how", "")})
        by_index[e["index_id"]] = {"status": 200, "path": R / e["file"],
                                   "url": c.get("index_base_url", "") + e["index_id"], "started_utc": ""}
        known.update(s["name"] for s in p["scans"])
    archive_src = source_info(c, c.get("machine_text_source", "archive"))
    mt = texts_by_scan(c, R / c.get("machine_text_dir", "machine_text"), known)
    for items in mt.values():  # the archive's own machine text, read from its folder
        for it in items:
            it["source"] = archive_src["class"]
            it["prov"] = prov_for(it, archive_src, {})
    for sid, items in htr_by_scan(c, known).items():
        mt.setdefault(sid, []).extend(items)
    cr = texts_by_scan(c, R / c.get("model_readings_dir", "model-readings"), known, (".txt", ".md"))
    deeds, problems = [], []
    for r in rows:
        no = int(r["no"])
        rec = by_index.get(r.get("index_id", ""))
        meta = None
        rec_path = (rec.get("path") or raw_index / rec["file"]) if rec else None
        if rec and rec.get("status") == 200 and rec_path.exists():
            rec_path = rec_path.resolve()
            p = saa.parse(rec_path)
            raw = json.loads(rec_path.read_text(encoding="utf-8"))
            shown = next((n.get("memorix:isShownAt") for n in raw["@graph"] if n.get("memorix:isShownAt")), "")
            meta = {
                "title": p["title"], "date": p["date_index"], "type": p["type_index"],
                "inventory": p["inv"], "inventory_title": p["inv_title"],
                "language": p["specs"].get("taal", []),
                "persons": [{"order": o, "name": n, "role": role} for o, n, role in p["persons"]],
                "places": p["locs"],
                "note": p["specs"].get("onderwerpsomschrijving", []),
                "other_fields": {k: v for k, v in p["specs"].items() if k not in ("taal", "onderwerpsomschrijving")},
                "record_url": shown, "index_uri": rec["url"],
                "index_file": rel_root(c, rec_path), "fetched_utc": rec.get("started_utc", ""),
            }
            scan_meta = p["scans"]
        else:
            problems.append(f"deed {no}: no index record on disk")
            scan_meta = [{"name": s.strip(), "w": 0, "h": 0, "bytes": 0, "iiif": ""} for s in r["scans"].split(";") if s.strip()]
        scans = []
        for s in scan_meta:
            files = disk.get(s["name"], [])
            scans.append({"id": s["name"], "w": s["w"], "h": s["h"], "jp2_bytes": s["bytes"],
                          "file": files[0] if files else "", "other_files": files[1:],
                          "machine_text": mt.get(s["name"], []), "claude_readings": cr.get(s["name"], [])})
        deeds.append({
            "no": no, "batch": r.get("batch", ""), "date": r.get("date", ""), "type": r.get("deed_type", ""),
            "language": r.get("language", ""), "inventory": r.get("inventory", ""),
            "notary": r.get("notary_per_coverage", ""), "check_tier": r.get("check_tier", ""),
            "machine_text_archive": r.get("machine_text", ""), "english_set": r.get("in_english_set_S1-05", ""),
            "index_id": r.get("index_id", ""), "meta": meta, "scans": scans,
            "how_found": r.get("_how") or c.get("how_found_default", ""),
        })
    share = {}
    for d in deeds:
        for s in d["scans"]:
            share.setdefault(s["id"], []).append(d["no"])
    for d in deeds:
        for s in d["scans"]:
            s["also_in"] = [n for n in share[s["id"]] if n != d["no"]]
    tr_summary = read_translations(c, deeds, problems)
    data = {
        "ui": c.get("ui", {}), "sample": bool(c.get("sample", False)),
        "translation_summary": tr_summary,
        "built": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "builder": "deed-reader/build_deed_data.py",
        "register": c["register"],
        "htr_summary": {"pages": sum(len(v) for v in mt.values()),
                        "by_source": {k: sum(1 for v in mt.values() for i in v if i.get("source") == k)
                                      for k in sorted({i.get("source", "") for v in mt.values() for i in v})},
                        "deeds_with_htr": sorted({d["no"] for d in deeds for s in d["scans"] if s["machine_text"]}),
                        "unplaced_files": UNPLACED},
        "deeds": deeds, "problems": problems,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("/* Deed Reader data, built from local files only. Do not edit by hand: re-run build_deed_data.py. */\n"
                        "window.DEED_DATA = " + json.dumps(data, ensure_ascii=False, indent=0) + ";\n", encoding="utf-8")
    print("settings", c["_file"].name, "· input", R)
    print("wrote", out_path, "· deeds", len(deeds),
          "· scan slots with image", sum(1 for d in deeds for s in d["scans"] if s["file"]),
          "of", sum(len(d["scans"]) for d in deeds))
    print("machine text pages", sum(len(v) for v in mt.values()), "· model readings", sum(len(v) for v in cr.values()))
    print("shared scans", {k: v for k, v in share.items() if len(v) > 1})
    print("problems", problems)
    print("htr summary", json.dumps(data["htr_summary"], ensure_ascii=False))
    print("translation summary", json.dumps(tr_summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
