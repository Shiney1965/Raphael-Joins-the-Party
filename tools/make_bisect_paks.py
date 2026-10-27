"""
Build bisection paks (added 2026-09-26: v0.2a failed the in-game Osiris compile with "1 error(s)" and no message).
Each pak = the given build stage minus ONE goal file, plus RJTP_ZZ_Stubs.txt holding no-op definitions of every
PROC/QRY that the removed file defined and the remaining files still call. Only one pak loading => that file has the error.
Never deletes: copies the stage to build\bisect_<tag>_<stamp> and writes dist\bisect\RJTP_bisect_<tag>.pak.
Usage: python make_bisect_paks.py <stage dir> <goal file>...
"""
import datetime, glob, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from osiris_lint import strip_comments, split_args  # noqa: E402

DIVINE = r"C:\bg3-sidecar-work\Tools\Divine.exe"
MOD = "RaphaelJoinsTheParty_745e6b7e-83fd-4953-a0ef-63865cf56da9"
GOALS_REL = os.path.join("Mods", MOD, "Story", "RawFiles", "Goals")


def heads(text):
    """name -> (kind, first typed head args) for PROC/QRY definitions"""
    out = {}
    t = strip_comments(text)
    for m in re.finditer(r"(?m)^\s*(PROC|QRY)\s*\n\s*([A-Za-z_]\w*)\s*\((.*)\)\s*$", t):
        kind, name, inner = m.group(1), m.group(2), m.group(3)
        args = split_args(inner) if inner.strip() else []
        prev = out.get(name)
        typed = sum(1 for a in args if a.startswith("("))
        if prev is None or typed > prev[2]:
            out[name] = (kind, args, typed)
    return out


def main():
    stage, drop = sys.argv[1], sys.argv[2:]
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(os.path.join(PROJ, "dist", "bisect"), exist_ok=True)
    for group in drop:
        files = group.split("+")
        tag = "_".join(os.path.splitext(f)[0].replace("RJTP_", "") for f in files)
        dst = os.path.join(PROJ, "build", f"bisect_{tag}_{stamp}")
        shutil.copytree(stage, dst)
        gdir = os.path.join(dst, GOALS_REL)
        removed = ""
        os.makedirs(os.path.join(dst, "_removed_from_pak"), exist_ok=True)
        for f in files:
            removed += open(os.path.join(gdir, f), encoding="utf-8").read()
            # moved out of the pak tree inside this fresh copy (kept for reference, never deleted)
            shutil.copy2(os.path.join(gdir, f), os.path.join(dst, "_removed_from_pak", f))
            open(os.path.join(gdir, f), "w").close()
        rest = "".join(open(p, encoding="utf-8").read() for p in glob.glob(os.path.join(gdir, "*.txt"))
                       if os.path.basename(p) not in files)
        rest_heads = heads(rest)
        rest_calls = set(re.findall(r"\b((?:PROC|QRY)_RJTP_\w+)\s*\(", strip_comments(rest)))
        stubs = []
        for name, (kind, args, _) in sorted(heads(removed).items()):
            if not name.startswith(("PROC_RJTP_", "QRY_RJTP_")) or name in rest_heads or name not in rest_calls:
                continue
            params = []
            for i, a in enumerate(args):
                m = re.match(r"^\((\w+)\)", a)
                if m:
                    params.append(f"({m.group(1)})_A{i}")
                elif a.startswith('"'):
                    params.append(f"(STRING)_A{i}")
                elif re.fullmatch(r"-?\d+", a):
                    params.append(f"(INTEGER)_A{i}")
                else:
                    params.append(f"_A{i}")
            body = "DB_NOOP(1);"
            if name == "PROC_RJTP_PresentOffer":
                body = "PROC_RJTP_ReopenOffer(_A0);"   # keep the offer working without the dialog layer
            stubs.append(f"{kind}\n{name}({', '.join(params)})\nTHEN\n{body}\n")
        txt = ("Version 1\r\nSubGoalCombiner SGC_AND\r\nINITSECTION\r\n\r\nKBSECTION\r\n// Bisection stubs for the removed goal "
               + f + "\r\n" + "\r\n".join(s.replace("\n", "\r\n") for s in stubs) + "EXITSECTION\r\n\r\nENDEXITSECTION\r\n")
        open(os.path.join(gdir, "RJTP_ZZ_Stubs.txt"), "w", encoding="utf-8", newline="").write(txt)
        pak = os.path.join(PROJ, "dist", "bisect", f"RJTP_bisect_no_{tag}.pak")
        tmp_tree = os.path.join(dst, "_pak_tree")
        shutil.copytree(dst, tmp_tree, ignore=lambda d, names: [n for n in names if n in ("_removed_from_pak", "_pak_tree")
                                                                  or (d.endswith("Goals") and n in files)])
        subprocess.run([DIVINE, "-g", "bg3", "-a", "create-package", "-s", tmp_tree, "-d", pak], check=True,
                       capture_output=True)
        print(f"{pak}  ({os.path.getsize(pak)} B)  stubs: {[s.splitlines()[1].split('(')[0] for s in stubs]}")


if __name__ == "__main__":
    main()
