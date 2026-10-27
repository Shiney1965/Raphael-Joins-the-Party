"""Assemble the five per-companion banter drafts into one document.

Reads  _vanilla_ref\\dumps\\companions\\<NAME>_banter_draft.md  (written by the per-companion line reviews)
Writes BANTER_COMPANIONS_2026-10-05.md in the project root. The "Rejected" lists stay in the drafts.
Then run:  python tools\\render_banter.py BANTER_COMPANIONS_2026-10-05.md
"""
import collections
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "_vanilla_ref", "dumps", "companions")
DST = os.path.join(ROOT, "BANTER_COMPANIONS_2026-10-05.md")
ORDER = [("KARLACH", "Karlach", "K"), ("ASTARION", "Astarion", "A"), ("GALE", "Gale", "G"),
         ("LAEZEL", "Lae'zel", "L"), ("WYLL", "Wyll", "W")]
# lines dropped after checking the exact wording (handle prefix -> reason, for the record)
DROP = {"h0647b32c": "the recorded text is only a sound label, not a line"}
TOKEN = re.compile(r"\{\{(h[0-9a-g]+)\|[^{}]*\}\}")
# Raphael lines reserved for the base game (the author 2026-10-07): an exchange that uses one is left out entirely
RESERVED_PATH = os.path.join(ROOT, "src", "reserved_lines.json")
if not os.path.exists(RESERVED_PATH):
    raise SystemExit("assemble_companion_banter: src/reserved_lines.json is missing")
RESERVED = [r["handle"] for r in json.load(open(RESERVED_PATH, encoding="utf-8"))["lines"]]

HEAD = """# Raphael and the companions — fully voiced banter (2026-10-05)

## TL/DR

Every line below is an existing recording: Raphael's from his 611 lines, the companion's from their own recorded
lines. So these exchanges are voiced on **both** sides. There are %(n_ex)d exchanges across Karlach, Astarion, Gale,
Lae'zel and Wyll (%(n_new)d new ones and %(n_reply)d that answer his existing call-outs), plus a small bank of
all-purpose retorts for each.%(dropped)s Nothing here has been heard in game yet; tone and
delivery are unchecked.

## How to read this file

- Each line is a token in double braces: the line's id, a bar, then what the line says **in other words**. This file
  never quotes a line. For the exact words, run `python tools\\render_banter.py BANTER_COMPANIONS_2026-10-05.md` and
  open `BANTER_COMPANIONS_2026-10-05_reading_copy.md`.
- "gate" says when an exchange is allowed. "none" means any time both are in the party.
- The "Note" under each exchange says why it works and what is imperfect about it.

## How these would fire

The base game lists each party banter in a registry file (`Gossips.lsx`) and the engine picks one when the party
walks into a banter trigger; the trigger then sleeps for 60 seconds, and banter is blocked for 20 seconds after any
overhead line (`GLO_WorldGossip.txt`, lines 26 and 109). Registering these exchanges the same way should give the
same frequency as the game's own companions, with no timer of ours. An installed mod already does exactly this
("Wyllzel Flirty Banter Restored - Polyamory Mod Compatible"); a reference copy of its text files is in
`_vanilla_ref\\precedent\\WyllzelBanterRestored_aec42950\\`. **Not yet tried for this mod.** Exchanges tied to a
moment (combat start, supper, a kill) would be fired by the mod's own script instead.

## Before any of this is built

- **Delivery is unheard.** Fit was judged from the text. Shouted combat lines and spell shouts may not sit well in
  calm banter; each note says where that risk is.
- **Gates need game flags.** "Wyll's pact is known", "before his scars are read", "scene not yet seen" and the like
  are described in words. The matching flags are not yet identified.
- **Some lines repeat base-game moments.** Where a line also plays in one of the game's own scenes or banters, the
  note says so.
- **Rule kept throughout:** no line recorded in the Last Light scenes with Mol (a child) is used in a flirtatious
  exchange. The flirtatious exchanges (all Astarion's) use none.
- **Raphael lines used with more than one companion** (pick one home for each, or accept the repeat):
%(dups)s
- The per-companion drafts, including the pairings that were considered and rejected, are in
  `_vanilla_ref\\dumps\\companions\\<NAME>_banter_draft.md`.

"""


def main():
    out, n_ex, n_reply, dropped = [], 0, 0, []
    raphael_use = collections.defaultdict(set)
    for key, name, short in ORDER:
        text = open(os.path.join(SRC, key + "_banter_draft.md"), encoding="utf-8").read()
        # keep from the first "## Replies" heading up to (not including) "## Rejected"
        a = text.index("## Replies to existing call-outs")
        b = text.index("## Rejected")
        body = text[a:b].rstrip() + "\n"
        # one chunk per heading; an exchange chunk ("### ...") that uses a reserved line is dropped whole
        kept = []
        for chunk in re.split(r"(?m)^(?=#{2,3} )", body):
            if chunk.startswith("### ") and any(h in chunk for h in RESERVED):
                dropped.append("%s: %s" % (name, chunk.splitlines()[0][4:].split(" \u2014 ")[0]))
                continue
            kept.append(chunk)
        body = "".join(kept)
        section = ""
        lines = []
        for ln in body.splitlines():
            if any(("{{" + h) in ln for h in DROP) and ln.lstrip().startswith("- "):
                continue
            if ln.startswith("## "):
                section = ln[3:]
                ln = "###" + ln[2:]                      # section headings one level down
            elif ln.startswith("### "):
                ln = "####" + ln[3:]
                n_ex += 1
                n_reply += section.startswith("Replies")
            m = re.match(r"^- ([A-Z]): (.*)$", ln)
            if m:
                who = "Raphael" if m.group(1) == "R" else name
                ln = "- **%s:** %s" % (who, m.group(2))
                if m.group(1) == "R":
                    for h in TOKEN.findall(m.group(2)):
                        raphael_use[h[:9]].add(name)
            lines.append(ln)
        out.append("## %s\n\n%s\n" % (name, "\n".join(lines)))
    dups = sorted((h, sorted(v)) for h, v in raphael_use.items() if len(v) > 1)
    dup_txt = "\n".join("  - {{%s|shared line}} — %s" % (h, ", ".join(v)) for h, v in dups) or "  - none"
    drop_txt = ""
    if dropped:
        drop_txt = (" Left out because they use a line reserved for the base game (`src\\reserved_lines.json`): "
                    + "; ".join(dropped) + ".")
    doc = HEAD % {"n_ex": n_ex, "n_new": n_ex - n_reply, "n_reply": n_reply, "dups": dup_txt,
                  "dropped": drop_txt} + "\n".join(out)
    open(DST, "w", encoding="utf-8", newline="\n").write(doc)
    print("exchanges:", n_ex, " shared Raphael lines:", len(dups), " ->", DST)


if __name__ == "__main__":
    main()
