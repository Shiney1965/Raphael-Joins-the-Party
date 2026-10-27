"""
Static linter for BG3 Osiris goal files (Raphael Joins the Party).

What it checks, per mod goal file:
  * file structure: Version 1 / SubGoalCombiner / INITSECTION / KBSECTION / EXITSECTION / ENDEXITSECTION
  * balanced parentheses and /* */ comments; every rule has IF|PROC|QRY ... THEN ... with ';'-terminated actions
  * every called name exists with a matching arity in: story_header.div builtins, vanilla PROC/QRY/DB usage,
    or the mod's own definitions (PROC_RJTP_*, QRY_RJTP_*, DB_RJTP_*)
  * every Name_GUID constant whose GUID is known in vanilla uses the vanilla name (typo guard), and every
    GUID constant is either known in vanilla or declared in src/ids.json / the allow-list
  * mod DBs are used with one consistent arity

Usage: python osiris_lint.py <goals_dir> <report_path>
Exit code 0 = no errors (warnings allowed), 1 = errors.
"""
import json, os, re, sys, glob, pickle, collections

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REF = os.path.join(PROJ, "_vanilla_ref")
STORY = os.path.join(PROJ, "_vanilla_story", "Mods")
HEADER = os.path.join(REF, "story_header.div")
CACHE = os.path.join(HERE, "_lint_vanilla_index_v2.pkl")  # bump the suffix whenever indexing logic changes

GUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
CONST_RX = re.compile(r"\b([A-Za-z][A-Za-z0-9_]*?)_(" + GUID + r")\b")
CALL_RX = re.compile(r"(?<![A-Za-z0-9_])(NOT\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def strip_comments(text):
    # mask string literal contents first (parentheses/commas inside messages are not code)
    text = re.sub(r'"[^"\n]*"', lambda m: '"' + "x" * (len(m.group(0)) - 2) + '"', text)
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def split_args(s):
    """split top-level comma args of the text inside the outer parens; returns list of arg strings"""
    args, depth, cur, instr = [], 0, "", False
    for ch in s:
        if ch == '"' :
            instr = not instr
        if not instr:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                args.append(cur.strip()); cur = ""; continue
        cur += ch
    if cur.strip():
        args.append(cur.strip())
    return args


def find_calls(text):
    """yield (name, arity, pos, negated) for every Name( ... ) in text (comments already stripped)"""
    for m in CALL_RX.finditer(text):
        name = m.group(2)
        if name in ("IF", "AND", "THEN", "NOT", "PROC", "QRY"):
            continue
        # skip typed casts like (CHARACTER)
        start = m.end()  # position after '('
        depth, i, instr = 1, start, False
        while i < len(text) and depth:
            c = text[i]
            if c == '"':
                instr = not instr
            elif not instr:
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
            i += 1
        inner = text[start:i - 1]
        # remove type casts inside args for counting
        args = split_args(inner) if inner.strip() else []
        yield name, len(args), m.start(), bool(m.group(1)), inner


def build_vanilla_index():
    if os.path.exists(CACHE):
        return pickle.load(open(CACHE, "rb"))
    builtins = collections.defaultdict(set)
    for line in open(HEADER, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*(call|query|event|sysquery|syscall)\s+([A-Za-z_][A-Za-z0-9_]*)\((.*)\)\s*\(", line)
        if m:
            inner = m.group(3).strip()
            n = len([a for a in inner.split(",") if a.strip()]) if inner else 0
            builtins[m.group(2)].add(n)
    used = collections.defaultdict(set)      # any name(...) usage in vanilla goals -> arities
    defined = collections.defaultdict(set)   # PROC/QRY heads
    guidnames = {}
    for f in glob.glob(os.path.join(STORY, "*", "Story", "RawFiles", "Goals", "*.txt")):
        raw = open(f, encoding="utf-8", errors="replace").read()
        t = strip_comments(raw)
        for name, n, _, _, _ in find_calls(t):
            used[name].add(n)
        for m in re.finditer(r"^\s*(PROC|QRY)\s*\n\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(", t, re.M):
            pass
        for m in CONST_RX.finditer(raw):
            guidnames.setdefault(m.group(2), set()).add(m.group(1))
    idx = {"builtins": dict(builtins), "used": dict(used), "guidnames": guidnames}
    pickle.dump(idx, open(CACHE, "wb"))
    return idx


def lint_file(path, idx, mod_defs, mod_db_arity, allowed_guids, report):
    raw = open(path, encoding="utf-8").read()
    errors, warns = [], []
    fn = os.path.basename(path)
    # structure
    lines = [l.strip() for l in raw.splitlines()]
    head = [l for l in lines if l]
    if not head or head[0] != "Version 1":
        errors.append("first line must be 'Version 1'")
    if len(head) < 2 or head[1] != "SubGoalCombiner SGC_AND":
        errors.append("second line must be 'SubGoalCombiner SGC_AND'")
    for sec in ("INITSECTION", "KBSECTION", "EXITSECTION", "ENDEXITSECTION"):
        if sec not in lines:
            errors.append(f"missing {sec}")
    if raw.count("/*") != raw.count("*/"):
        errors.append("unbalanced /* */")
    t = strip_comments(raw)
    if t.count("(") != t.count(")"):
        errors.append(f"unbalanced parentheses: {t.count('(')} '(' vs {t.count(')')} ')'")
    # rule shape in KB section: every IF/PROC/QRY block must contain THEN and end its actions with ';'
    kb = t.split("KBSECTION", 1)[1].split("EXITSECTION", 1)[0] if "KBSECTION" in t else ""
    blocks = re.split(r"(?m)^\s*(?=IF\s*$|PROC\s*$|QRY\s*$)", kb)
    for b in blocks:
        bs = b.strip()
        if not bs:
            continue
        if not re.match(r"^(IF|PROC|QRY)\s", bs):
            errors.append(f"text outside a rule in KB: {bs[:80]!r}")
            continue
        if "THEN" not in bs:
            errors.append(f"rule without THEN: {bs[:100]!r}")
            continue
        cond, act = bs.split("THEN", 1)
        # conditions: lines joined by AND, none should end with ';'
        if ";" in cond:
            errors.append(f"';' inside conditions: {cond.strip()[:100]!r}")
        acts = [a.strip() for a in act.strip().split("\n") if a.strip()]
        joined = " ".join(acts)
        if joined and not joined.rstrip().endswith(";"):
            errors.append(f"actions not terminated with ';': {joined[-100:]!r}")
        # every complete statement (parentheses balanced at end of line) must end with ';'
        depth = 0
        for a in acts:
            depth += a.count("(") - a.count(")")
            if depth == 0 and not a.endswith(";"):
                errors.append(f"action statement missing ';': {a[:100]!r}")
        # each condition line after first must be preceded by AND
        clines = [c.strip() for c in cond.split("\n") if c.strip()]
        for i, c in enumerate(clines[1:], 1):
            if c in ("AND",):
                continue
            if clines[i - 1] not in ("AND", "IF", "PROC", "QRY"):
                errors.append(f"missing AND before condition {c[:80]!r}")
    # INIT section facts must end with ';'
    init = t.split("INITSECTION", 1)[1].split("KBSECTION", 1)[0] if "INITSECTION" in t else ""
    for stmt in [s for s in re.split(r";", init)][:-1]:
        if stmt.strip() and not re.match(r"^\s*[A-Za-z_]", stmt.strip()):
            errors.append(f"odd INIT statement {stmt.strip()[:60]!r}")
    # calls
    b = idx["builtins"]; u = idx["used"]
    for name, n, pos, neg, inner in find_calls(t):
        if name.startswith(("DB_RJTP_",)):
            mod_db_arity[name].add(n)
            continue
        if name in mod_defs:
            if n not in mod_defs[name]:
                errors.append(f"{name}: arity {n}, mod definition has {sorted(mod_defs[name])}")
            continue
        known = set(b.get(name, set())) | set(u.get(name, set()))
        if not known:
            (warns if name.startswith("DB_") else errors).append(f"unknown name {name}/{n}")
        elif n not in known:
            errors.append(f"{name}: arity {n} not in known arities {sorted(known)}")
    # GUID constants
    for m in CONST_RX.finditer(raw):
        nm, g = m.group(1), m.group(2)
        vn = idx["guidnames"].get(g)
        if vn:
            if nm not in vn:
                errors.append(f"constant {nm}_{g}: vanilla calls this GUID {sorted(vn)}")
        elif g not in allowed_guids:
            errors.append(f"constant {nm}_{g}: GUID not in vanilla goals nor ids.json/allow-list")
    report.append(f"== {fn}: {len(errors)} error(s), {len(warns)} warning(s)")
    report += ["  ERROR " + e for e in errors] + ["  warn  " + w for w in warns]
    return len(errors)


def main():
    goals_dir, out = sys.argv[1], sys.argv[2]
    idx = build_vanilla_index()
    ids = json.load(open(os.path.join(PROJ, "src", "ids.json")))
    allowed = set(ids.values())
    allow_file = os.path.join(PROJ, "src", "lint_allowed_guids.txt")
    if os.path.exists(allow_file):
        for line in open(allow_file, encoding="utf-8"):
            m = re.search(GUID, line)
            if m:
                allowed.add(m.group(0))
    files = sorted(glob.glob(os.path.join(goals_dir, "*.txt")))
    # collect mod PROC/QRY definitions (name -> arities)
    mod_defs = collections.defaultdict(set)
    for f in files:
        t = strip_comments(open(f, encoding="utf-8").read())
        for m in re.finditer(r"(?m)^\s*(PROC|QRY)\s*\n\s*([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)", t):
            name = m.group(2)
            if name.startswith(("PROC_RJTP_", "QRY_RJTP_")):
                # arity from head line (single line heads only)
                head = m.group(3)
                depth, i = 1, 0
                while i < len(head) and depth:
                    if head[i] == "(":
                        depth += 1
                    elif head[i] == ")":
                        depth -= 1
                    i += 1
                inner = head[:i - 1]
                mod_defs[name].add(len(split_args(inner)) if inner.strip() else 0)
    report, total = [], 0
    mod_db_arity = collections.defaultdict(set)
    for f in files:
        total += lint_file(f, idx, mod_defs, mod_db_arity, allowed, report)
    for db, ar in sorted(mod_db_arity.items()):
        if len(ar) > 1:
            report.append(f"  ERROR mod DB {db} used with several arities {sorted(ar)}")
            total += 1
    # mod PROC/QRY called but never defined
    for f in files:
        t = strip_comments(open(f, encoding="utf-8").read())
        for name, n, _, _, _ in find_calls(t):
            if name.startswith(("PROC_RJTP_", "QRY_RJTP_")) and name not in mod_defs:
                report.append(f"  ERROR {os.path.basename(f)}: {name} called but never defined")
                total += 1
    report.insert(0, f"Osiris lint: {len(files)} file(s), {total} error(s)")
    open(out, "w", encoding="utf-8").write("\n".join(report) + "\n")
    print("\n".join(report))
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
