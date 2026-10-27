"""
Osiris STRUCTURE checker (added 2026-09-26, v0.2a failed story compile). Checks that osiris_lint.py does not:
  B1 variable used in an action but never bound by the head / a positive condition
  B2 named variable in a NOT condition or comparison that is not bound earlier in the rule
  E1 an event used anywhere but as the first condition of an IF rule
  E2 an IF rule whose first condition is not an event or a DB
  Q1 a builtin query or a user QRY used as an action;  C1 a builtin call or a user PROC used as a condition
  D1 a DB that is read in some condition but never written (no INIT fact, no insert in any action)
Calibrate with --vanilla (the vanilla goals compile, so every hit there is a checker false positive).
Usage: python osiris_structcheck.py <goals_dir> | --vanilla
"""
import collections, glob, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from osiris_lint import strip_comments, split_args  # noqa: E402
from osiris_typecheck import parse_header, parse_blocks, call_parts  # noqa: E402

STORY = os.path.join(PROJ, "_vanilla_story", "Mods")
VAR_RX = re.compile(r"(?<![A-Za-z0-9_])(_[A-Za-z][A-Za-z0-9_]*)")


def vars_in(args):
    out = []
    for a in args:
        a = re.sub(r'"[^"]*"', '""', a)
        out += VAR_RX.findall(a)
    return out


def analyse(files, dbfiles):
    hdr = parse_header()
    kinds = {n: k for n, (k, _) in hdr.items()}
    outs = {n: [p[0] == "out" for p in ps] for n, (k, ps) in hdr.items()}
    user_proc, user_qry = set(), set()
    db_written, db_read = set(), collections.defaultdict(list)
    parsed = {}
    for f in dbfiles:
        rules, facts = parse_blocks(strip_comments(open(f, encoding="utf-8", errors="replace").read()))
        parsed[f] = rules
        for fact in facts:
            p = call_parts(fact)
            if p and p[1].startswith("DB_"):
                db_written.add(p[1])
        for kind, conds, acts in rules:
            if kind in ("PROC", "QRY") and conds and call_parts(conds[0]):
                (user_proc if kind == "PROC" else user_qry).add(call_parts(conds[0])[1])
            for a in acts:
                p = call_parts(a)
                if p and p[1].startswith("DB_") and not p[0]:
                    db_written.add(p[1])
    errs = []
    for f in files:
        rules = parsed.get(f) or parse_blocks(strip_comments(open(f, encoding="utf-8", errors="replace").read()))[0]
        for i, (kind, conds, acts) in enumerate(rules):
            where = f"{os.path.basename(f)} rule#{i + 1}"
            bound = set()
            for ci, c in enumerate(conds):
                cmp_ = re.match(r"^(_\w+)\s*(==|!=|<=|>=|<|>)\s*(.+)$", c)
                if cmp_:
                    for v in [cmp_.group(1)] + VAR_RX.findall(cmp_.group(3)):
                        if v not in bound:
                            errs.append(f"B2 {where}: comparison uses unbound {v}")
                    continue
                p = call_parts(c)
                if not p:
                    errs.append(f"?? {where}: unparsed condition {c[:60]!r}")
                    continue
                neg, name, args = p
                k = kinds.get(name)
                if k == "event" and not (kind == "IF" and ci == 0):
                    errs.append(f"E1 {where}: event {name} not first condition")
                if kind == "IF" and ci == 0 and k != "event" and not name.startswith("DB_"):
                    errs.append(f"E2 {where}: IF rule starts with {name}")
                if (k == "call" or name in user_proc) and not (kind in ("PROC", "QRY") and ci == 0):
                    errs.append(f"C1 {where}: call/PROC {name} used as a condition")
                if name.startswith("DB_") and not (kind in ("PROC", "QRY") and ci == 0):
                    db_read[name].append(where)
                vs = vars_in(args)
                if neg:
                    for v in vs:
                        if v not in bound and not re.fullmatch(r"_", v):
                            errs.append(f"B2 {where}: NOT {name} uses unbound {v}")
                else:
                    if k in ("query", "sysquery"):
                        o = outs.get(name, [])
                        for ai, a in enumerate(args):
                            for v in vars_in([a]):
                                if ai < len(o) and o[ai]:
                                    bound.add(v)
                                elif v not in bound:
                                    errs.append(f"B2 {where}: query {name} input {v} unbound")
                    else:
                        bound.update(vs)
            for a in acts:
                p = call_parts(a)
                if not p:
                    errs.append(f"?? {where}: unparsed action {a[:60]!r}")
                    continue
                neg, name, args = p
                k = kinds.get(name)
                if k in ("query", "sysquery", "event") or name in user_qry:
                    errs.append(f"Q1 {where}: {k or 'QRY'} {name} used as an action")
                for v in vars_in(args):
                    if v not in bound:
                        errs.append(f"B1 {where}: action {name} uses unbound {v}")
    for db, wh in db_read.items():
        if db not in db_written:
            errs.append(f"D1 {db} read ({wh[0]}...) but never written")
    return errs


def main():
    vanilla = sorted(glob.glob(os.path.join(STORY, "*", "Story", "RawFiles", "Goals", "*.txt")))
    if "--vanilla" in sys.argv:
        errs = analyse(vanilla, vanilla)
        c = collections.Counter(e.split()[0] for e in errs)
        print(f"vanilla: {len(errs)} hit(s): {dict(c)}")
        for code in c:
            for e in [x for x in errs if x.startswith(code)][:4]:
                print("   ", e)
        return
    goals = sorted(glob.glob(os.path.join(sys.argv[1], "*.txt")))
    errs = [e for e in analyse(goals, vanilla + goals) if "rule#" not in e or any(os.path.basename(g) in e for g in goals)]
    errs = [e for e in errs if not e.startswith("D1") or "RJTP" in e]
    print(f"mod: {len(errs)} hit(s)")
    for e in errs:
        print("  ", e)


if __name__ == "__main__":
    main()
