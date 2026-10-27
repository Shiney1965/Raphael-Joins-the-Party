"""Dump the recorded lines of the origin companions, for writing two-sided banter with Raphael.

Inputs (extracted from the user's own game files into a scratch folder):
  <scratch>\\vm5\\...\\Soundbanks\\<speaker uuid, no dashes>.lsx   voice banks (handle, length, priority)
  <scratch>\\dlg5\\**\\*.lsj                                        every dialog (handle -> dialog, node, speaker)
  _vanilla_ref\\loca.pkl                                           handle -> English text

Output, per companion:  _vanilla_ref\\dumps\\companions\\<NAME>_VOICED_LINES.tsv
  handle, length_s, priority, source_dialog, node8, text

Usage:  python tools\\dump_companion_lines.py <scratch dir>
"""
import glob
import json
import os
import pickle
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "_vanilla_ref")
OUT = os.path.join(REF, "dumps", "companions")

COMPANIONS = {
    "KARLACH": "2c76687d-93a2-477b-8b18-8a14b549304c",
    "ASTARION": "c7c13742-bacd-460a-8f65-f864fe41f255",
    "GALE": "ad9af97d-75da-406a-ae13-7071c563f604",
    "LAEZEL": "58a69333-40bf-8358-1d17-fff240d7fb12",
    "WYLL": "c774d764-4a17-48dc-b470-32ace9ce447d",
}

RX_ENTRY = re.compile(
    r'<attribute id="MapKey" type="FixedString" value="(h[0-9a-g]+)" />\s*<children>\s*<node id="MapValue">(.*?)</node>',
    re.S)
RX_LEN = re.compile(r'id="Length" type="float" value="([^"]+)"')
RX_PRIO = re.compile(r'id="Priority" type="FixedString" value="([^"]+)"')


def val(o, k, d=None):
    x = o.get(k)
    if isinstance(x, dict) and "value" in x:
        return x["value"]
    return d if x is None else x


def index_dialogs(scratch):
    """handle -> list of (dialog name, node8, constructor)."""
    idx = {}
    files = glob.glob(os.path.join(scratch, "dlg5", "**", "*.lsj"), recursive=True)
    # later paks were extracted over earlier ones into the same tree, so each path is the final version
    for path in files:
        try:
            d = json.load(open(path, encoding="utf-8-sig"))["save"]["regions"]["dialog"]
        except Exception as e:  # a dialog we cannot parse is reported, not skipped silently
            print("UNREADABLE", path, e)
            continue
        name = os.path.splitext(os.path.basename(path))[0]
        for n in d["nodes"][0].get("node", []):
            uid = val(n, "UUID", "")
            ctor = val(n, "constructor", "")
            for tt in n.get("TaggedTexts", []):
                for t in tt.get("TaggedText", []):
                    for tx in t.get("TagTexts", []):
                        for tt2 in tx.get("TagText", []):
                            h = tt2.get("TagText", {}).get("handle")
                            if h:
                                idx.setdefault(h, []).append((name, uid[:8], ctor))
    return idx, len(files)


def main():
    scratch = sys.argv[1]
    loca = pickle.load(open(os.path.join(REF, "loca.pkl"), "rb"))
    idx, nfiles = index_dialogs(scratch)
    print("dialogs indexed: %d, handles: %d" % (nfiles, len(idx)))
    os.makedirs(OUT, exist_ok=True)
    for name, uuid in COMPANIONS.items():
        bank = glob.glob(os.path.join(scratch, "vm5", "**", uuid.replace("-", "") + ".lsx"), recursive=True)
        if not bank:
            print("NO BANK", name)
            continue
        text = open(bank[0], encoding="utf-8-sig").read()
        rows, nosrc, notext = [], 0, 0
        for h, body in RX_ENTRY.findall(text):
            ln = RX_LEN.search(body)
            pr = RX_PRIO.search(body)
            srcs = idx.get(h)
            if not srcs:
                nosrc += 1
            t = loca.get(h)
            if t is None:
                notext += 1
                continue
            t = re.sub(r"\s+", " ", t).strip()
            s = srcs[0] if srcs else ("?", "", "")
            rows.append((h, "%.2f" % float(ln.group(1)) if ln else "", pr.group(1) if pr else "", s[0], s[1], t))
        rows.sort(key=lambda r: (r[3], r[4]))
        dst = os.path.join(OUT, name + "_VOICED_LINES.tsv")
        with open(dst, "w", encoding="utf-8", newline="\n") as f:
            f.write("handle\tlength_s\tpriority\tsource_dialog\tnode8\ttext\n")
            for r in rows:
                f.write("\t".join(r) + "\n")
        print("%-9s lines %5d  (no dialog source %d, no text %d)  -> %s" % (name, len(rows), nosrc, notext, dst))


if __name__ == "__main__":
    main()
