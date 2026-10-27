"""Build src/banter_content.json: the solo barks and two-sided banters shipped in the v0.3a test build.

Barks are listed here by handle prefix. Banters are taken by title from the per-companion drafts
(_vanilla_ref/dumps/companions/<NAME>_banter_draft.md), so no handle is retyped. Every handle is resolved against the
line dumps (Raphael's 611 lines; each companion's recorded lines) and must be unique, recorded (length > 0) and, for
a companion line, recorded by THAT companion.

Usage:  python tools/gen_banter_content.py
"""
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUMPS = os.path.join(ROOT, "_vanilla_ref", "dumps")
OUT = os.path.join(ROOT, "src", "banter_content.json")

ORIGINS = {
    "KARLACH": ("K", "2c76687d-93a2-477b-8b18-8a14b549304c"),
    "ASTARION": ("A", "c7c13742-bacd-460a-8f65-f864fe41f255"),
    "GALE": ("G", "ad9af97d-75da-406a-ae13-7071c563f604"),
    "LAEZEL": ("L", "58a69333-40bf-8358-1d17-fff240d7fb12"),
    "WYLL": ("W", "c774d764-4a17-48dc-b470-32ace9ce447d"),
}

# group -> (cooldown in ms, handle prefixes). Proposal section 3a.
BARKS = [
    ("CombatStart", 180000, ["h85f5d40f", "hc466a5ae", "h3fe48a4c"]),
    ("Kill", 90000, ["hc4e1430d", "hdb2e1731"]),
    ("Ascend", 60000, ["h228b0e8e", "hfc494b00", "h522c2dbe", "h48df382c"]),
    ("Downed", 0, ["h421e4ce3"]),
    ("HelpedUp", 120000, ["hd4564c97", "h3617634a", "hfb06e3dc"]),
    ("Won", 600000, ["h52718081"]),
]

# companion -> [(short name used in the dialog name, title as written in the draft)]
BANTERS = {
    "KARLACH": [("ExceptDevils", "Except devils"), ("SaveYourSoul", "Save your soul")],
    "ASTARION": [("TheGame", "The game"), ("EagerPup", "Eager pup"), ("ComradesInArms", "Comrades in arms")],
    "GALE": [("NeverADullDay", "Never a dull day"), ("HandsomeDevil", "Handsome devil"), ("HellIsWhere", "Hell is where")],
    "LAEZEL": [("DazzlingSmile", "Dazzling smile"), ("BestToKeepQuiet", "Best to keep quiet"),
               ("WhatAreYouHiding", "What are you hiding")],
    "WYLL": [("ShouldHaveStayedBelow", "1. Should have stayed below"), ("TheGoodEye", "2. The good eye"),
             ("HalfOfWhatHeKnows", "9. Half of what he knows")],
}

ERR = []


def load(path, text_col):
    rows = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for i, r in enumerate(csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)):
            if i == 0 or len(r) <= text_col:
                continue
            rows[r[0].strip()] = float(r[1] or 0)
    return rows


RESERVED_PATH = os.path.join(ROOT, "src", "reserved_lines.json")
if not os.path.exists(RESERVED_PATH):
    sys.exit("gen_banter_content: src/reserved_lines.json is missing (the list of lines the mod must never use)")
RESERVED = {r["handle"] for r in json.load(open(RESERVED_PATH, encoding="utf-8"))["lines"]}


def resolve(rows, h, what):
    hits = [k for k in rows if k == h or k.startswith(h)]
    if len(hits) != 1:
        ERR.append("%s: handle %s matches %d lines" % (what, h, len(hits)))
        return None, 0.0
    if hits[0] in RESERVED:
        ERR.append("%s: %s is reserved for the base game (src/reserved_lines.json)" % (what, hits[0]))
    if rows[hits[0]] <= 0:
        ERR.append("%s: %s has no recorded length" % (what, hits[0]))
    return hits[0], rows[hits[0]]


def main():
    raphael = load(os.path.join(DUMPS, "RAPHAEL_VOICED_LINES_611.tsv"), 4)
    out = {"barks": [], "banters": []}
    for group, cd, hs in BARKS:
        for n, h in enumerate(hs, 1):
            full, ln = resolve(raphael, h, "bark " + group)
            out["barks"].append({"name": "RJTP_AD_Bark_%s_%d" % (group, n), "group": group, "index": n,
                                 "cooldown_ms": cd, "line": full, "length_s": ln})
    for comp, picks in BANTERS.items():
        letter, guid = ORIGINS[comp]
        lines = load(os.path.join(DUMPS, "companions", comp + "_VOICED_LINES.tsv"), 5)
        draft = open(os.path.join(DUMPS, "companions", comp + "_banter_draft.md"), encoding="utf-8").read()
        for short, title in picks:
            m = re.search(r"^### " + re.escape(title) + r" — .*?\n((?:- [A-Z]: .*\n)+)", draft, re.M)
            if not m:
                ERR.append("%s: exchange %r not found in the draft" % (comp, title))
                continue
            head = re.search(r"^### " + re.escape(title) + r" — gate: (.*?) — where: (.*)$", draft, re.M)
            seq = []
            for ln in m.group(1).splitlines():
                who, rest = re.match(r"^- ([A-Z]): (.*)$", ln).groups()
                hm = re.match(r"\{\{(h[0-9a-g]+)\|", rest)
                if who not in ("R", letter) or not hm:
                    ERR.append("%s %r: cannot parse line %r" % (comp, title, ln[:60]))
                    continue
                if who == "R":
                    full, sec = resolve(raphael, hm.group(1), "%s %s (Raphael)" % (comp, short))
                    seq.append({"speaker": 0, "line": full, "length_s": sec})
                else:
                    full, sec = resolve(lines, hm.group(1), "%s %s (%s)" % (comp, short, comp))
                    seq.append({"speaker": 1, "line": full, "length_s": sec})
            if len(seq) < 2 or len({s["speaker"] for s in seq}) != 2:
                ERR.append("%s %r: not a two-sided exchange" % (comp, title))
            out["banters"].append({"name": "RJTP_PB_%s_%s" % (comp.capitalize(), short), "companion": comp,
                                   "origin": guid, "title": title.split(". ", 1)[-1],
                                   "gate": head.group(1) if head else "", "where": head.group(2) if head else "",
                                   "lines": seq})
    for e in ERR:
        print("  ERROR " + e)
    if not ERR:
        with open(OUT, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(out, indent=1) + "\n")
    print("gen_banter_content: %d barks, %d banters, %d error(s)" % (len(out["barks"]), len(out["banters"]), len(ERR)))
    for b in out["banters"]:
        print("   %-40s %s  gate: %s" % (b["name"], "".join("R" if s["speaker"] == 0 else b["companion"][0] for s in b["lines"]),
                                         b["gate"][:60]))
    return 1 if ERR else 0


if __name__ == "__main__":
    sys.exit(main())
