#!/usr/bin/env python3
"""Deed Reader team server (version 0.3, 28 November 2026).

One small Python process that gives a reading team:
  1. one copy of the form, the data file and the scans;
  2. shared readings: every reader's work is kept on the server, and each reader
     can see (never edit) the others' work;
  3. (D11, 27 Nov 2026) questions to the cluster's own models, asked by the server, so the
     API key never reaches a browser. On only when DHINFRA_API_KEY is set in the server's
     environment (never in a file); otherwise the form keeps its clipboard route alone;
  4. (0.3, 28 Nov 2026) a shared knowledge graph with a Hopper and two gates (graph.html),
     on only when the settings have a "graph" section. Its rules:
       K4  add-only: an item is added once and never changed; a comment, a revision, a score,
           a tick or a pull-back is a new entry beside it, signed by its author;
       K5  Gate 1 is passed by a rule over the latest score (graph_rule_v1), and any author may
           pull an item back with a reason; Gate 2 needs both deciders' ticks, recorded only
           from the recorder's token (a decider without a token ticks "said aloud");
       K9-K12 who may open the graph, and who may add to it, is set per reader in the settings,
           never in this code; a reader not named there is refused.
     The graph's content (people, texts, the base network) lives in a file named in the
     settings, outside the repository.

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

VERSION = "0.3"
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


def iso_now():
    """UTC, to the millisecond, so entries made in the same second keep their order."""
    t = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".%03dZ" % int((t % 1) * 1000)


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


# ---- the knowledge graph (0.3) ----
GRAPH_KINDS = ("voyage", "organisation", "identity", "source lead", "database match", "context")
GRAPH_NINE_KINDS = ("voyage", "organisation", "context")     # scored on the nine criteria
GRAPH_STAGES = ("in", "gate1", "approved", "aside")
GRAPH_STAGE_LABEL = {"in": "In", "gate1": "Gate 1, active consideration", "approved": "Gate 2, approved for the graph",
                     "aside": "Set aside"}
# Moves made by the deciders' two ticks. In to Gate 1 is not among them: only the rule makes it (K5).
GRAPH_NEXT = {"in": ("aside",), "gate1": ("approved", "aside"), "approved": ("aside",), "aside": ("in",)}
GRAPH_ANSWERS = ("yes", "partly", "no", "not yet known")
# Basis codes for new items. P always carries its code (P-H, P-MHC, P-MUC); imported items may keep a bare "P".
GRAPH_BASIS = ("P-H", "P-MHC", "P-MUC", "D", "S", "Q", "X", "A", "B", "N", "R", "I")
GRAPH_CRITERIA = ("In scope", "Variables", "Route", "Discriminating power", "Directness", "Specificity",
                  "Adds something new", "Citable", "Graph-ready")
GRAPH_QUESTIONS = {
    "identity": ("Is the lead specific?", "Does it rest on primary text?",
                 "Would it change how a voyage or organisation item is read?"),
    "source lead": ("Does it name the sources precisely enough to find them?",
                    "Are they primary, and can we reach them?",
                    "If read, could they change a voyage or organisation item, or how a database's figures are read?"),
    "database match": ("Does the match hold on at least two independent fields (name, master, year, route, owner)?",
                       "What does each side supply that the other lacks?",
                       "Are the database's own sources named, and can they be read?")}
GRAPH_RULE = "v1.1"


def graph_rule_v1(score):
    """The holding rule for Gate 1 (K14, 27 Nov 2026), the strawman of 9 Nov 2026.
    Voyage and organisation: 12 or more of 18, criterion 4 at least 1, criteria 1-4 at least 5.
    Identity, source lead, database match: all three answers "yes". Context: never by rule.
    v1.1 (K16, 28 Nov 2026): a provisional score, made without re-reading the passage, never passes;
    a later score that is not provisional may.
    Returns (passes, the reason in words). Change the rule here, and its name in GRAPH_RULE."""
    kind = score.get("kind")
    if score.get("provisional") is True:
        return False, "%s: a provisional score does not pass Gate 1 by rule" % kind
    if score.get("method") == "nine" and kind in ("voyage", "organisation"):
        parts = {}
        for p in score.get("parts") or []:
            try:
                parts[int(p.get("n"))] = int(p.get("score"))
            except (TypeError, ValueError, AttributeError):
                pass
        total, floor, c4 = sum(parts.values()), sum(parts.get(i, 0) for i in (1, 2, 3, 4)), parts.get(4, 0)
        why = "%s: %d of 18; criteria 1-4, %d of 8; criterion 4, %d" % (kind, total, floor, c4)
        return total >= 12 and c4 >= 1 and floor >= 5, why
    if score.get("method") == "test" and kind in GRAPH_QUESTIONS:
        ans = [str(a.get("answer", "")).strip().lower() for a in score.get("answers") or [] if isinstance(a, dict)]
        return len(ans) == 3 and all(a == "yes" for a in ans), "%s: answers %s" % (kind, ", ".join(ans))
    return False, "%s items do not pass Gate 1 by rule" % kind


def norm_ws(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


class GraphError(Exception):
    def __init__(self, msg, code=400):
        Exception.__init__(self, msg)
        self.code = code


def _text(body, key, most, need=False):
    v = body.get(key)
    if v is None:
        v = ""
    if not isinstance(v, str):
        raise GraphError("%s must be text" % key)
    v = v.strip()
    if need and not v:
        raise GraphError("%s is needed" % key)
    if len(v) > most:
        raise GraphError("%s is longer than %d characters" % (key, most))
    return v


def _whole(body, key, most=999999):
    """An optional whole number from 1 to most, sent as a number or as digits; None if left empty."""
    v = body.get(key)
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, str) and re.match(r"\s*\d+\s*$", v):
        v = int(v)
    if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= most:
        raise GraphError("%s must be a whole number from 1 to %d" % (key, most))
    return v


class GraphStore:
    """The knowledge graph's Hopper: items and the entries beside them, append-only (D8, K4).

    One file per author, <store_dir>/<reader>.jsonl, and _rule.jsonl for the server's own Gate 1
    decisions; an optional import file (an earlier store, made by graph_seed.py) is read, never
    written. Each line: {"t": ..., "author": ..., "col": "items" | "entries", "doc": {...}}.
    The stage of each item is worked out afresh by replaying its entries in time order.
    """

    def __init__(self, g):
        self.g = g
        self.folder = g["store_dir"]
        os.makedirs(self.folder, exist_ok=True)
        self.lock = threading.Lock()
        self.items, self.entries, self.ids, self.seq = {}, [], set(), 0
        files = [g["import_file"]] if g.get("import_file") else []
        files += [os.path.join(self.folder, f) for f in sorted(os.listdir(self.folder)) if f.endswith(".jsonl")]
        for path in files:
            with open(path, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self._apply(json.loads(line))
                    except (ValueError, KeyError, TypeError) as e:
                        print("graph: skipped line %d of %s (%s)" % (n, path, e), file=sys.stderr)
        if g["gate1"] == "rule":  # scores already in the store that pass the rule (an import, or a rule change)
            with self.lock:
                for iid in sorted(self.items):
                    self._rule(iid)

    def _apply(self, rec):
        col, doc = rec["col"], rec["doc"]
        if col == "items":
            self.items.setdefault(doc["id"], doc)
        elif col == "entries" and doc["_id"] not in self.ids:
            self.seq += 1
            doc["_seq"] = self.seq
            self.entries.append(doc)
            self.ids.add(doc["_id"])

    def _write(self, author, col, doc):
        rec = {"t": iso_now(), "author": author, "col": col, "doc": doc}
        line = json.dumps(rec, ensure_ascii=False)
        with open(os.path.join(self.folder, safe_name(author) + ".jsonl"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
        self._apply(json.loads(line))

    def _voided(self):
        """A "void" entry (in an imported store only) sets named entries aside; nothing is deleted."""
        return {i for e in self.entries if e.get("type") == "void" for i in (e.get("entries") or [])}

    def _derive(self, iid, gone=None):
        it, dec = self.items[iid], self.g["deciders"]
        gone = self._voided() if gone is None else gone
        es = sorted((e for e in self.entries if e.get("item") == iid and e.get("type") != "void" and e["_id"] not in gone),
                    key=lambda e: (str(e.get("at") or ""), e["_seq"]))
        stage = it.get("stage") if it.get("stage") in GRAPH_STAGES else "in"
        live, ruled, scores = {}, set(), []
        hist = [{"at": h.get("at"), "what": h.get("stage") or h.get("what") or "", "by": h.get("by"), "why": h.get("why") or ""}
                for h in it.get("history") or [] if isinstance(h, dict)]
        for e in es:
            t, by, at, to = e.get("type"), e.get("by"), e.get("at"), e.get("to")
            if t == "score":
                scores.append(e)
            elif t == "tick" and (to is None or to in GRAPH_STAGES):
                said = " Said aloud." if e.get("via") == "spoken" else " From a comment." if e.get("via") == "comment" else ""
                why = (e.get("why") or "") + said + (" Words: “%s”." % e["quote"] if e.get("quote") else "")
                if by not in dec:
                    hist.append({"at": at, "what": "ticked " + GRAPH_STAGE_LABEL.get(to, "(withdrawn)"), "by": by,
                                 "why": why + " [not counted: not a Gate 2 decider]"})
                    continue
                live[by] = e if to else None
                hist.append({"at": at, "what": "ticked " + GRAPH_STAGE_LABEL[to] if to else "withdrew the tick",
                             "by": by, "why": why.strip()})
            elif t == "agree" and to in GRAPH_STAGES:
                if to != stage and dec and all(live.get(d) and live[d].get("to") == to for d in dec):
                    stage, live = to, {}
                    hist.append({"at": at, "what": "moved to " + GRAPH_STAGE_LABEL[to], "by": "+".join(dec),
                                 "why": "Both ticks named this stage and the move was confirmed."})
                else:
                    hist.append({"at": at, "what": "move to " + GRAPH_STAGE_LABEL[to] + " entered", "by": by,
                                 "why": "[not counted: the ticks did not both name this stage at that moment]"})
            elif t == "rule":
                ruled.add(e.get("score"))
                if stage == "in":
                    stage = "gate1"
                    hist.append({"at": at, "what": "passed Gate 1 by rule " + str(e.get("rule", "")), "by": "rule",
                                 "why": e.get("why") or ""})
            elif t == "pullback" and stage == "gate1":
                stage = "in"
                hist.append({"at": at, "what": "pulled back to In", "by": by, "why": e.get("why") or ""})
            elif t == "gate" and to in GRAPH_STAGES:  # an older one-person form: never moves an item
                hist.append({"at": at, "what": "move to " + GRAPH_STAGE_LABEL[to] + " entered for one person", "by": by,
                             "why": (e.get("why") or "") + " [not counted: an item moves only when both ticks agree]"})
        ready = None
        if dec and live.get(dec[0]):
            t0 = live[dec[0]].get("to")
            if t0 != stage and all(live.get(d) and live[d].get("to") == t0 for d in dec):
                ready = t0
        ticks = {d: {k: v.get(k) for k in ("to", "at", "via", "quote", "entered_by")} for d, v in live.items() if v}
        return {"stage": stage, "ticks": ticks, "ready": ready, "history": hist,
                "score": scores[-1]["_id"] if scores else None, "ruled": ruled, "_score": scores[-1] if scores else None}

    def _rule(self, iid):
        d = self._derive(iid)
        s = d["_score"]
        if d["stage"] != "in" or not s or s["_id"] in d["ruled"]:
            return
        ok, why = graph_rule_v1(s)
        if ok:
            self._write("_rule", "entries", {"_id": "rule-" + s["_id"], "item": iid, "type": "rule", "to": "gate1",
                                             "rule": GRAPH_RULE, "score": s["_id"], "by": "rule", "why": why,
                                             "at": iso_now(), "entered_by": "the server, by rule " + GRAPH_RULE})

    def state(self):
        with self.lock:
            gone = self._voided()
            items = []
            for iid in sorted(self.items):
                d = self._derive(iid, gone)
                for k in ("ruled", "_score"):
                    d.pop(k)
                items.append(dict(self.items[iid], entered_stage=self.items[iid].get("stage"), **d))
            # in time order, so the list is the same whichever author's log was read first
            entries = [{k: v for k, v in e.items() if k != "_seq"}
                       for e in sorted(self.entries, key=lambda e: (str(e.get("at") or ""), e["_id"]))
                       if e.get("type") != "void" and e["_id"] not in gone]
            return json.loads(json.dumps({"items": items, "entries": entries, "voided": len(gone)}))

    def counts(self):
        with self.lock:
            return len(self.items), len(self.entries)

    # ---- adding ----
    def add_item(self, reader, person, body):
        cat = body.get("category")
        if cat not in GRAPH_KINDS:
            raise GraphError("category must be one of: " + ", ".join(GRAPH_KINDS))
        basis = body.get("basis") or None
        if basis is not None and basis not in GRAPH_BASIS:
            raise GraphError("basis must be one of the codes " + ", ".join(GRAPH_BASIS))
        doc = {"kind": _text(body, "kind", 200) or cat, "category": cat, "words": _text(body, "words", 4000, True),
               "source": _text(body, "source", 2000), "reference": _text(body, "reference", 2000),
               "text": _text(body, "text", 50000), "text_extent": _text(body, "text_extent", 200),
               "next": _text(body, "next", 2000), "basis": basis}
        # Where in the Deed Reader the item comes from (optional): the deed's number, the scan's id and
        # the line, which the Deed Reader counts within each scan.
        deed, line = _whole(body, "deed"), _whole(body, "line")
        scan = _text(body, "scan", 100)
        if scan and not re.match(r"[A-Za-z0-9._-]+$", scan):
            raise GraphError("scan may hold only letters, digits, '.', '_' and '-'")
        if scan and deed is None:
            raise GraphError("a scan needs its deed")
        if line is not None and not scan:
            raise GraphError("a line needs its scan: the Deed Reader counts lines within each scan")
        if deed is not None:
            doc.update(deed=deed, scan=scan or None, line=line)
        with self.lock:
            nums = [int(m.group(1)) for m in (re.match(r"HOP-(\d+)$", i) for i in self.items) if m]
            iid = "HOP-%03d" % (max(nums + [0]) + 1)
            doc.update({"id": iid, "by": person["id"], "entered": iso_now(), "stage": "in", "history": [],
                        "schema": "graph-item/1", "entered_by": person["name"] + ", on the server"})
            self._write(reader, "items", doc)
        return iid

    def _score(self, body, person):
        kind = body.get("kind")
        if kind not in GRAPH_KINDS:
            raise GraphError("kind must be one of: " + ", ".join(GRAPH_KINDS))
        out = {"kind": kind, "scorer": person["name"], "provisional": body.get("provisional") is True,
               "scored_from": _text(body, "scored_from", 500), "criteria": "rule " + GRAPH_RULE + " (strawman of 9 Nov 2026)"}
        if kind in GRAPH_NINE_KINDS:
            parts = body.get("parts")
            if not isinstance(parts, list) or len(parts) != 9:
                raise GraphError("a %s item is scored on nine criteria" % kind)
            clean = []
            for i, p in enumerate(parts, 1):
                s = p.get("score") if isinstance(p, dict) else None
                if isinstance(s, bool) or s not in (0, 1, 2):
                    raise GraphError("each criterion is scored 0, 1 or 2")
                clean.append({"n": i, "criterion": GRAPH_CRITERIA[i - 1], "score": s, "why": _text(p, "why", 1000)})
            total, floor = sum(p["score"] for p in clean), sum(p["score"] for p in clean[:4])
            reading = ("context" if kind == "context" or clean[3]["score"] < 1 or floor < 5
                       else "strong" if total >= 12 else "checks" if total >= 8 else "hold")
            out.update(method="nine", parts=clean, total=total, floor_sum=floor, reading=reading)
        else:
            answers = body.get("answers")
            if not isinstance(answers, list) or len(answers) != 3:
                raise GraphError("a %s item answers three questions" % kind)
            clean = []
            for i, a in enumerate(answers, 1):
                ans = a.get("answer") if isinstance(a, dict) else None
                if ans not in GRAPH_ANSWERS:
                    raise GraphError("each answer is one of: " + ", ".join(GRAPH_ANSWERS))
                clean.append({"n": i, "question": GRAPH_QUESTIONS[kind][i - 1], "answer": ans, "why": _text(a, "why", 1000)})
            vals = [a["answer"] for a in clean]
            reading = ("strong" if all(v == "yes" for v in vals) else
                       "checks" if any(v in ("yes", "partly") for v in vals) else "hold")
            out.update(method="test", answers=clean, reading=reading)
        return out

    def add_entry(self, reader, person, body):
        iid, t = body.get("item"), body.get("type")
        with self.lock:
            if iid not in self.items:
                raise GraphError("no such item", 404)
            it, d = self.items[iid], self._derive(iid)
            stage = d["stage"]
            doc = {"item": iid, "type": t, "by": person["id"], "at": iso_now(),
                   "entered_by": person["name"] + ", on the server"}
            if t == "comment":
                doc["text"] = _text(body, "text", 20000, True)
            elif t == "revise":
                doc.update(words=_text(body, "words", 4000, True), why=_text(body, "why", 2000, True))
            elif t == "excerpt":
                q = _text(body, "quote", 5000, True)
                if not it.get("text") or norm_ws(q) not in norm_ws(it["text"]):
                    raise GraphError("an excerpt must be copied exactly from the item's primary text")
                doc.update(quote=q, location=_text(body, "location", 200))
            elif t == "score":
                doc.update(self._score(body, person))
            elif t == "pullback":
                if stage != "gate1":
                    raise GraphError("only an item at Gate 1 can be pulled back", 409)
                doc.update(to="in", why=_text(body, "why", 2000, True))
            elif t in ("tick", "agree"):
                if reader != self.g["recorder"]:
                    raise GraphError("Gate 2 is recorded only from the gate's recorder's link", 403)
                to, allowed = body.get("to"), GRAPH_NEXT.get(stage, ())
                if t == "tick":
                    by = body.get("by")
                    if by not in self.g["deciders"]:
                        raise GraphError("not one of the gate's deciders")
                    if to is not None and to not in allowed:
                        raise GraphError("an item at %s cannot be ticked for %s" % (stage, to), 409)
                    doc.update(by=by, to=to)
                    if by != person["id"]:
                        doc["via"] = "spoken"  # K13: said aloud on a call, entered by the recorder
                    quote = _text(body, "quote", 1000)
                    if quote:
                        doc["quote"] = quote
                    if to is None:
                        doc["why"] = "withdrawn"
                else:
                    if to not in allowed or d["ready"] != to:
                        raise GraphError("both deciders' ticks must name this stage first", 409)
                    doc["to"] = to
            else:
                raise GraphError("type must be comment, revise, excerpt, score, pullback, tick or agree")
            doc["_id"] = "e-%s-%s" % (time.strftime("%Y%m%d%H%M%S", time.gmtime()), os.urandom(4).hex())
            self._write(reader, "entries", doc)
            if t == "score" and self.g["gate1"] == "rule":
                self._rule(iid)
            return doc["_id"]


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
        # 0.3: the knowledge graph, on only with a "graph" section (see server.example.json).
        self.graph = None
        g = c.get("graph")
        if g:
            people = {}
            for reader, v in (g.get("people") or {}).items():
                if not (isinstance(v, dict) and re.match(r"[a-z0-9_-]{1,40}$", str(v.get("id", ""))) and
                        v.get("role") in ("author", "reader")):
                    sys.exit("graph.people.%s needs an id (a-z, 0-9, _ or -) and a role, author or reader." % reader)
                people[reader] = dict(v, name=v.get("name") or reader)
            # K17: names and badges to show, which open nothing. To make a label a member, move its
            # entry to "people" and give it a role.
            labels, ids = {}, {v["id"] for v in people.values()}
            for reader, v in (g.get("labels") or {}).items():
                if not (isinstance(v, dict) and re.match(r"[a-z0-9_-]{1,40}$", str(v.get("id", "")))):
                    sys.exit("graph.labels.%s needs an id (a-z, 0-9, _ or -)." % reader)
                if reader in people or v["id"] in ids:
                    sys.exit("graph.labels.%s is also in graph.people; keep it in one place." % reader)
                ids.add(v["id"])
                labels[reader] = {k: v[k] for k in ("id", "badge", "color", "color_dark") if k in v}
                labels[reader]["name"] = v.get("name") or reader
            gate2 = g.get("gate2") or {}
            self.graph = {"content_file": p(g["content_file"]) if g.get("content_file") else None,
                          "store_dir": p(g.get("store_dir", os.path.join(os.path.dirname(self.store_dir), "graph"))),
                          "import_file": p(g["import_file"]) if g.get("import_file") else None,
                          "gate1": g.get("gate1", "rule"), "people": people, "labels": labels,
                          "recorder": gate2.get("recorder"), "deciders": list(gate2.get("deciders") or [])}
            if self.graph["gate1"] not in ("rule", "hold"):
                sys.exit("graph.gate1 must be \"rule\" or \"hold\".")
            if self.graph["recorder"] and people.get(self.graph["recorder"], {}).get("role") != "author":
                sys.exit("graph.gate2.recorder must be one of graph.people with the role author.")
            for f in (self.graph["content_file"], self.graph["import_file"]):
                if f and not os.path.isfile(f):
                    sys.exit("Missing: " + f)


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


def graph_people(cfg, content):
    """Everyone the graph shows by name: the content file's people, the settings' labels (which open
    nothing), then the settings' people."""
    out = {}
    for v in (content or {}).get("people") or []:
        if isinstance(v, dict) and v.get("id"):
            out[v["id"]] = dict(v)
    for v in cfg.graph["labels"].values():
        out[v["id"]] = dict(out.get(v["id"], {}), **v)
    for reader, v in cfg.graph["people"].items():
        out[v["id"]] = dict(out.get(v["id"], {}), **{k: v[k] for k in ("id", "name", "badge", "color", "color_dark")
                                                     if k in v})
    return list(out.values())


def make_handler(cfg, store, tokens, asker, graph=None, gcontent=None):
    allowed_static = {"/deed_reader.html": os.path.join(cfg.form_dir, "deed_reader.html"),
                      "/" + cfg.data_file.strip("/"): os.path.join(cfg.form_dir, cfg.data_file)}
    log_lock = threading.Lock()

    def graph_person(reader):
        return cfg.graph["people"].get(reader) if graph else None

    def graph_me(reader):
        p = graph_person(reader)
        return {"reader": reader, "id": p["id"], "name": p["name"], "role": p["role"],
                "recorder": reader == cfg.graph["recorder"]}

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
                # the link may open the graph instead of the form: /graph.html?t=TOKEN
                self.send_header("Location", "/graph.html" if graph and u.path == "/graph.html" else "/deed_reader.html")
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
                gp = graph_person(reader)
                return self.send_json(200, {"reader": reader, "server": VERSION, "readers": sorted({r for _, r in tokens}),
                                            "ask": asker.on(),
                                            "ask_models": [{"id": k, "label": v} for k, v in asker.models.items()],
                                            "graph": gp["role"] if gp else None})
            if graph and (path == "/graph.html" or path.startswith("/api/graph")):
                if not graph_person(reader):
                    return self.send_text(403, "<p>The knowledge graph is not open to this reader.</p>")
                if path == "/graph.html":
                    return self.send_file(os.path.join(cfg.form_dir, "graph.html"), cache=False)
                if path == "/api/graph":
                    st = graph.state()
                    st.update(t=iso_now(), me=graph_me(reader), gate1=cfg.graph["gate1"], rule=GRAPH_RULE,
                              deciders=cfg.graph["deciders"])
                    return self.send_json(200, st)
                if path == "/api/graph/content":
                    return self.send_json(200, {"content": gcontent or {}, "people": graph_people(cfg, gcontent),
                                                "me": graph_me(reader), "kinds": GRAPH_KINDS,
                                                "nine_kinds": GRAPH_NINE_KINDS, "criteria": GRAPH_CRITERIA,
                                                "questions": GRAPH_QUESTIONS, "answers": GRAPH_ANSWERS,
                                                "basis": GRAPH_BASIS, "stages": GRAPH_STAGE_LABEL,
                                                "next": GRAPH_NEXT, "deciders": cfg.graph["deciders"],
                                                "gate1": cfg.graph["gate1"], "rule": GRAPH_RULE})
                if path == "/api/graph/export":
                    out = graph.state()
                    out = {"exported": iso_now(), "server": VERSION, "rule": GRAPH_RULE, "content": gcontent or {},
                           "people": graph_people(cfg, gcontent), "items": out["items"], "entries": out["entries"]}
                    body = json.dumps(out, ensure_ascii=False, indent=1).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Disposition",
                                     'attachment; filename="graph-export-%s.json"' % time.strftime("%Y%m%d-%H%M"))
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                return self.send_text(404, "Not found.")
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
            if path == "/api/graph" and graph:
                p = graph_person(reader)
                if not p:
                    return self.send_json(403, {"error": "the knowledge graph is not open to this reader"})
                if p["role"] != "author":
                    return self.send_json(403, {"error": "this reader may read the graph but not add to it"})
                try:
                    if body.get("op") == "item":
                        return self.send_json(200, {"added": graph.add_item(reader, p, body.get("item") or {})})
                    if body.get("op") == "entry":
                        return self.send_json(200, {"added": graph.add_entry(reader, p, body.get("entry") or {})})
                except GraphError as e:
                    return self.send_json(e.code, {"error": str(e)})
                return self.send_json(400, {"error": "op must be item or entry"})
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
    graph, gcontent = None, None
    if cfg.graph:
        if not os.path.isfile(os.path.join(cfg.form_dir, "graph.html")):
            sys.exit("Missing: " + os.path.join(cfg.form_dir, "graph.html"))
        if cfg.graph["content_file"]:
            with open(cfg.graph["content_file"], encoding="utf-8") as f:
                gcontent = json.load(f)
        graph = GraphStore(cfg.graph)
    srv = ThreadingHTTPServer((cfg.bind, cfg.port), make_handler(cfg, store, tokens, asker, graph, gcontent))
    host = socket.gethostname()
    print("Deed Reader server %s started %s on %s, port %d" % (VERSION, now(), host, cfg.port))
    print("Readers with tokens: %s" % ", ".join(sorted({r for _, r in tokens})))
    print("Readings kept in: %s (%d readers so far)" % (cfg.store_dir, len(store.readers)))
    if asker.on():
        print("Asking the cluster's models: on (%s); up to %d tokens and %d seconds an answer"
              % (", ".join(asker.models.values()), asker.max_tokens, asker.timeout))
    else:
        print("Asking the cluster's models: off (no DHINFRA_API_KEY in this job's environment)")
    if graph:
        ni, ne = graph.counts()
        print("Knowledge graph: on (%d items, %d entries; Gate 1 %s); open to: %s"
              % (ni, ne, "by rule " + GRAPH_RULE if cfg.graph["gate1"] == "rule" else "held",
                 ", ".join("%s (%s)" % (r, v["role"]) for r, v in sorted(cfg.graph["people"].items()))))
    else:
        print("Knowledge graph: off (no graph section in the settings)")
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
