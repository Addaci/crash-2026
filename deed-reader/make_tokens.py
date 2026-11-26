#!/usr/bin/env python3
"""Make one token per reader for the Deed Reader server (D12, 26 November 2026).

    python3 make_tokens.py --out ~/deedreader_tokens.json Anna Ben

Writes the token file (readable by you only) and prints one personal link per reader.
Give each person their own link privately: never by chat, email to a group, or a
repository. Running it again for a name that already has a token keeps the old token
unless you add --renew NAME.
"""
import argparse
import json
import os
import secrets
import stat

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True, help="token file, outside the repository (e.g. ~/deedreader_tokens.json)")
ap.add_argument("--port", type=int, default=8765)
ap.add_argument("--renew", action="append", default=[], help="give this reader a new token")
ap.add_argument("readers", nargs="+")
a = ap.parse_args()

path = os.path.expanduser(a.out)
tokens = {}
if os.path.exists(path):
    with open(path, encoding="utf-8") as f:
        tokens = json.load(f)
by_reader = {v["reader"]: t for t, v in tokens.items()}
for r in a.renew:
    if r in by_reader:
        del tokens[by_reader.pop(r)]
for r in a.readers:
    if r not in by_reader:
        t = secrets.token_urlsafe(24)
        tokens[t] = {"reader": r}
        by_reader[r] = t

fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as f:
    json.dump(tokens, f, indent=1)
try:
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
except OSError:
    pass
print("Token file: %s (%d readers)" % (path, len(tokens)))
for r in a.readers:
    print("%-10s http://localhost:%d/?t=%s" % (r, a.port, by_reader[r]))
