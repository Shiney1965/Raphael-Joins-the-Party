"""
Osiris TYPE checker for the RJTP goals (added 2026-09-26 after the v0.2a story failed to compile in game with
"1 error(s)" and no message; osiris_lint.py checks names and arity only).

Model (calibrated against the vanilla goals, which are known to compile - run with --vanilla):
  * builtin signatures come from story_header.div (param direction + type)
  * PROC/QRY/DB signatures come from typed heads/facts (casts, literals) in the mod goals, plus vanilla goals
  * each rule binds variables left to right: head params, the event, positive DB/query conditions
  * a value passed to a parameter must have the same type, or be an alias passed to GUIDSTRING (upcast);
    a GUIDSTRING (or another alias) passed to an alias parameter needs an explicit cast at that site
  * --narrow: treat a cast in a condition as re-typing the variable for the rest of the rule

Usage: python osiris_typecheck.py <goals_dir> [--narrow] | --vanilla [--narrow]
"""
import collections, glob, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
HEADER = os.path.join(PROJ, "_vanilla_ref", "story_header.div")
STORY = os.path.join(PROJ, "_vanilla_story", "Mods")
BASIC = {"INTEGER", "INTEGER64", "REAL", "STRING"}
NARROW = "--narrow" in sys.argv
LITERAL_ANY = True

sys.path.insert(0, HERE)
from osiris_lint import strip_comments, split_args  # noqa: E402

CAST_RX = re.compile(r"^\(([A-Z][A-Z0-9_]*)\)\s*(.*)$", re.S)
GUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def parse_header():
    sig = {}
    for line in open(HEADER, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*(call|query|event|sysquery|syscall)\s+([A-Za-z_]\w*)\((.*)\)\s*\(", line)
        if not m:
            continue
        params = []
        for a in [x.strip() for x in m.group(3).split(",") if x.strip()]:
            d = "out" if a.startswith("[out]") else "in"
            t = re.search(r"\(([A-Z0-9_]+)\)", a)
            params.append((d, t.group(1) if t else None))
        sig[m.group(2)] = (m.group(1), params)
    return sig


def is_guid_family(t):
    return t is not None and t not in BASIC


def value_type(arg, vartypes):
    """-> (type or None, var name or None, cast or None)"""
    a = arg.strip()
    cast = None
    m = CAST_RX.match(a)
    if m:
        cast, a = m.group(1), m.group(2).strip()
    if a.startswith("_"):
        return (cast or vartypes.get(a)), a, cast
    if LITERAL_ANY:
        return cast, None, cast   # constants/literals: the compiler adapts them (calibrated on vanilla)
    if a.startswith('"'):
        return (cast or "STRING"), None, cast
    if re.fullmatch(r"-?\d+", a):
        return (cast or "INTEGER"), None, cast
    if re.fullmatch(r"-?\d+\.\d*", a):
        return (cast or "REAL"), None, cast
    if re.fullmatch(r"[A-Z0-9_]+\.[A-Za-z0-9_]+", a):   # enum literal ARMOURSET.Vanity
        return (cast or a.split(".")[0]), None, cast
    if re.search(GUID, a) or a.startswith("NULL_"):
        return (cast or "GUIDSTRING"), None, cast
    return cast, None, cast


def compatible(have, want):
    if have is None or want is None:
        return True
    if have == want:
        return True
    if want == "GUIDSTRING" and is_guid_family(have):
        return True
    return False


def parse_blocks(text):
    kb = text.split("KBSECTION", 1)[1].split("EXITSECTION", 1)[0] if "KBSECTION" in text else ""
    init = text.split("INITSECTION", 1)[1].split("KBSECTION", 1)[0] if "INITSECTION" in text else ""
    rules = []
    for b in re.split(r"(?m)^\s*(?=IF\s*$|PROC\s*$|QRY\s*$)", kb):
        bs = b.strip()
        if not bs or "THEN" not in bs:
            continue
        kind, rest = bs.split(None, 1)
        cond, act = rest.split("THEN", 1)
        conds = [c.strip() for c in re.split(r"(?m)^\s*AND\s*$", cond) if c.strip()]
        acts = [a.strip() for a in act.split(";") if a.strip()]
        rules.append((kind, conds, acts))
    facts = [s.strip() for s in init.split(";") if s.strip()]
    return rules, facts


CALL_RX = re.compile(r"^(NOT\s+)?([A-Za-z_]\w*)\s*\((.*)\)\s*$", re.S)


def call_parts(s):
    m = CALL_RX.match(s.strip())
    if not m:
        return None
    return bool(m.group(1)), m.group(2), split_args(m.group(3)) if m.group(3).strip() else []


class Sigs:
    """user PROC/QRY/DB signatures: name -> list of types (None = unknown)"""
    def __init__(self):
        self.s = {}

    def note(self, name, types):
        cur = self.s.get(name)
        if cur is None or len(cur) != len(types):
            if cur is None:
                self.s[name] = list(types)
            return
        for i, t in enumerate(types):
            if cur[i] is None and t is not None:
                cur[i] = t


def collect_sigs(files, sigs):
    global LITERAL_ANY
    LITERAL_ANY = False
    _collect(files, sigs)
    LITERAL_ANY = True


def _collect(files, sigs):
    for f in files:
        rules, facts = parse_blocks(strip_comments(open(f, encoding="utf-8", errors="replace").read()))
        for fact in facts:
            p = call_parts(fact)
            if p and not p[0]:
                sigs.note(p[1], [value_type(a, {})[0] for a in p[2]])
        for kind, conds, acts in rules:
            if kind in ("PROC", "QRY") and conds:
                p = call_parts(conds[0])
                if p:
                    sigs.note(p[1], [value_type(a, {})[0] if not a.strip().startswith("_") or CAST_RX.match(a.strip()) else None
                                     for a in p[2]])


def check_rule(kind, conds, acts, hdr, sigs, errs, where):
    vt = {}

    def use(name, args, params_types, dirs=None, binding_ok=False, site=""):
        for i, a in enumerate(args):
            want = params_types[i] if i < len(params_types) else None
            d = dirs[i] if dirs and i < len(dirs) else "in"
            t, var, cast = value_type(a, vt)
            if var and var not in vt and var != "_":
                if var.startswith("_") and len(var) > 1 and (binding_ok or d == "out"):
                    vt[var] = cast or want
                continue
            if var == "_" or (var and var.startswith("_") and var not in vt and len(var) == 1):
                continue
            if cast and var and NARROW and site == "cond":
                vt[var] = cast
            if not compatible(t, want):
                errs.append(f"{where}: {name} arg {i + 1} {a.strip()[:60]!r}: have {t}, param wants {want}")

    def sig_of(name, n):
        if name in hdr:
            kind_, params = hdr[name]
            return [p[1] for p in params], [p[0] for p in params], kind_
        s = sigs.s.get(name)
        if s and len(s) == n:
            return s, None, "user"
        return [None] * n, None, "unknown"

    for ci, c in enumerate(conds):
        if re.match(r"^_\w+\s*(==|!=|<=|>=|<|>)", c):
            continue
        p = call_parts(c)
        if not p:
            continue
        neg, name, args = p
        types, dirs, k = sig_of(name, len(args))
        head = ci == 0
        use(name, args, types, dirs, binding_ok=(not neg) and (head or k in ("user", "unknown") or name.startswith("DB_")),
            site="cond")
    for a in acts:
        p = call_parts(a)
        if not p:
            continue
        neg, name, args = p
        types, dirs, k = sig_of(name, len(args))
        use(name, args, types, dirs, binding_ok=False, site="act")


def run(files, sig_files):
    hdr = parse_header()
    sigs = Sigs()
    collect_sigs(sig_files, sigs)
    errs = []
    for f in files:
        rules, _ = parse_blocks(strip_comments(open(f, encoding="utf-8", errors="replace").read()))
        for i, (kind, conds, acts) in enumerate(rules):
            first = call_parts(conds[0])[1] if conds and call_parts(conds[0]) else "?"
            check_rule(kind, conds, acts, hdr, sigs, errs, f"{os.path.basename(f)} rule#{i + 1} ({kind} {first})")
    return errs


def main():
    vanilla = sorted(glob.glob(os.path.join(STORY, "*", "Story", "RawFiles", "Goals", "*.txt")))
    if "--vanilla" in sys.argv:
        errs = run(vanilla, vanilla)
        kinds = collections.Counter(re.sub(r".*have (\S+), param wants (\S+)", r"\1->\2", e) for e in errs)
        print(f"vanilla: {len(errs)} type complaint(s) (narrow={NARROW}) across {len(vanilla)} goals")
        for k, n in kinds.most_common(25):
            print(f"  {n:6d}  {k}")
        for e in errs[:15]:
            print("   ", e)
        return
    goals = sorted(glob.glob(os.path.join(sys.argv[1], "*.txt")))
    errs = run(goals, vanilla + goals)
    print(f"mod: {len(errs)} type complaint(s) (narrow={NARROW})")
    for e in errs:
        print("  ", e)
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
