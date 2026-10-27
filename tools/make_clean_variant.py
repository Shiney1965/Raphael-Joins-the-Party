"""
Build a VALID bisection pak (2026-09-26): keep the listed goal files from a build stage, drop the rest, then add
stubs (for RJTP PROC/QRY that are called but no longer defined) and placeholder facts (for RJTP DBs that are now read
but never written) until tools/story_compile_check.py reports the variant clean. Copy-only; never deletes.
Usage: python make_clean_variant.py <stage dir> <tag> <keep1.txt> [<keep2.txt> ...]
"""
import datetime, glob, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from osiris_lint import strip_comments, split_args  # noqa: E402

MOD = "RaphaelJoinsTheParty_745e6b7e-83fd-4953-a0ef-63865cf56da9"
GREL = os.path.join("Mods", MOD, "Story", "RawFiles", "Goals")
DIVINE = r"C:\bg3-sidecar-work\Tools\Divine.exe"
NULLG = "NULL_00000000-0000-0000-0000-000000000000"


def check(goals_dir, scratch):
    r = subprocess.run([sys.executable, os.path.join(HERE, "story_compile_check.py"), goals_dir, scratch],
                       capture_output=True, text=True)
    return r.returncode, r.stdout


def dummy_args(name, n, full_text):
    """dummy literal per column, typed from any insert/fact/cast of that DB in the full source"""
    cols = [None] * n
    for m in re.finditer(re.escape(name) + r"\((.*?)\);", full_text):
        args = split_args(m.group(1))
        if len(args) != n:
            continue
        for i, a in enumerate(args):
            a = a.strip()
            if cols[i]:
                continue
            c = re.match(r"^\((\w+)\)", a)
            if c:
                cols[i] = f"({c.group(1)}){NULLG}" if c.group(1) not in ("INTEGER", "STRING", "REAL") else \
                    {"INTEGER": "-999", "STRING": '"__rjtp_none"', "REAL": "-999.0"}[c.group(1)]
            elif re.fullmatch(r"-?\d+", a):
                cols[i] = "-999"
            elif re.fullmatch(r"-?\d+\.\d*", a):
                cols[i] = "-999.0"
            elif a.startswith('"'):
                cols[i] = '"__rjtp_none"'
    return [c or NULLG for c in cols]


def main():
    stage, tag, keep = sys.argv[1], sys.argv[2], sys.argv[3:]
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(PROJ, "build", f"variant_{tag}_{stamp}")
    src_goals = os.path.join(stage, GREL)
    shutil.copytree(stage, dst, ignore=lambda d, names: [n for n in names if os.path.normcase(d) ==
                                                         os.path.normcase(src_goals) and n not in keep])
    g = os.path.join(dst, GREL)
    full = "".join(open(p, encoding="utf-8").read() for p in glob.glob(os.path.join(src_goals, "*.txt")))
    full_s = strip_comments(full)
    heads = {}
    for m in re.finditer(r"(?m)^\s*(PROC|QRY)\s*\n\s*([A-Za-z_]\w*)\s*\((.*)\)\s*$", full_s):
        args = split_args(m.group(3)) if m.group(3).strip() else []
        prev = heads.get(m.group(2))
        if prev is None or sum(a.startswith("(") for a in args) > sum(a.startswith("(") for a in prev[1]):
            heads[m.group(2)] = (m.group(1), args)
    stubs, facts = {}, {}
    scratch = os.path.join(PROJ, "build", "storycheck_variants")
    for rnd in range(6):
        body = "".join(stubs.values())
        init = "".join(facts.values())
        open(os.path.join(g, "RJTP_ZZ_Stubs.txt"), "w", encoding="utf-8", newline="").write(
            f"Version 1\r\nSubGoalCombiner SGC_AND\r\nINITSECTION\r\n// Bisection placeholders (variant {tag})\r\n{init}"
            f"KBSECTION\r\n{body}EXITSECTION\r\n\r\nENDEXITSECTION\r\n")
        code, out = check(g, scratch)
        orph = set(re.findall(r'Database "((?:DB)_RJTP_\w+)\((\d+)\)" is read, but is never written', out))
        unres = set(re.findall(r'Symbol "((?:PROC|QRY|DB)_RJTP_\w+)\((\d+)\)" could not be resolved', out))
        undefined = {(n, a) for n, a in unres if not n.startswith("DB_")}
        # W26: an RJTP PROC/QRY called in an action but defined nowhere becomes a DB write -> stub it too
        for n in set(re.findall(r'Name of database "((?:PROC|QRY)_RJTP_\w+)"', out)):
            if n in heads:
                undefined.add((n, str(len(heads[n][1]))))
        undb = {(n, a) for n, a in unres if n.startswith("DB_")}
        w26 = re.findall(r'Name of database "((?:PROC|QRY)_RJTP_\w+)"', out)
        if code == 0 and not unres and not w26:
            print(f"[{tag}] CLEAN after {rnd} round(s); stubs={sorted(stubs)} placeholders={sorted(facts)}")
            break
        for n, a in undefined:
            kind, args = heads.get(n, ("PROC", ["_x"] * int(a)))
            params = []
            for i, x in enumerate(args):
                c = re.match(r"^\((\w+)\)", x.strip())
                params.append(f"({c.group(1)})_A{i}" if c else ("(STRING)_A%d" % i if x.strip().startswith('"')
                              else "(INTEGER)_A%d" % i if re.fullmatch(r"-?\d+", x.strip()) else f"_A{i}"))
            stubs[n] = f"{kind}\r\n{n}({', '.join(params)})\r\nTHEN\r\nDB_NOOP(1);\r\n\r\n"
        for n, a in orph | undb:
            facts[n] = f"{n}({', '.join(dummy_args(n, int(a), full))});\r\n"
    else:
        print(f"[{tag}] NOT CLEAN - see {scratch}\\story_compile_last.txt")
        print("\n".join(l for l in out.splitlines() if "RJTP" in l)[:3000])
        sys.exit(1)
    os.makedirs(os.path.join(PROJ, "dist", "bisect"), exist_ok=True)
    pak = os.path.join(PROJ, "dist", "bisect", f"RJTP_variant_{tag}.pak")
    subprocess.run([DIVINE, "-g", "bg3", "-a", "create-package", "-s", dst, "-d", pak], check=True, capture_output=True)
    print(f"[{tag}] {pak} ({os.path.getsize(pak)} B); goals: {sorted(os.listdir(g))}")


if __name__ == "__main__":
    main()
