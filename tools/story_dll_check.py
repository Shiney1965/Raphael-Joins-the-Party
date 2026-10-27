"""Merge RJTP goal files into a captured game story (.div) and compile it with the real
Osiris.dll from the BG3 Toolkit (via osiris_dll_compile.py). Error lines are mapped back
to <goal file>:<line>.

    python story_dll_check.py <base.div> <goals dir> <work dir> [goal names to include...]

<base.div>: a story_generated.div the game wrote for the author's load order WITHOUT RJTP
(captured 2026-10-01 by SE LogCompile; JUNK lines are stripped here).
Goals are inserted where the game would put them (case-insensitive title order) and
every later goal is renumbered, including the Goal(n).SubGoal(m) edges.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def parse_goal(path):
    lines = open(path, encoding="utf-8-sig").read().splitlines()
    idx = {k: None for k in ("INITSECTION", "KBSECTION", "EXITSECTION", "ENDEXITSECTION")}
    for i, l in enumerate(lines):
        if l.strip() in idx and idx[l.strip()] is None:
            idx[l.strip()] = i
    if None in idx.values():
        raise SystemExit("%s: missing a section marker" % path)
    sec = lambda a, b: list(range(idx[a] + 1, idx[b]))
    return lines, sec("INITSECTION", "KBSECTION"), sec("KBSECTION", "EXITSECTION"), sec("EXITSECTION", "ENDEXITSECTION")


def render_goal(gid, title, path, out, linemap):
    lines, init, kb, exit_ = parse_goal(path)

    def emit(s, src=None):
        out.append(s)
        if src is not None:
            linemap[len(out)] = (os.path.basename(path), src + 1)

    emit('Goal(%d).Title("%s");' % (gid, title))
    emit("Goal(%d)" % gid)
    emit("{")
    for name, rows in (("INIT", init), ("KB", kb), ("EXIT", exit_)):
        emit("\t" + name)
        emit("\t{")
        for r in rows:
            emit("\t\t" + lines[r], r)
        emit("\t}")
    emit("}")


def main():
    base, goals_dir, work = sys.argv[1:4]
    only = set(sys.argv[4:])
    os.makedirs(work, exist_ok=True)
    src = [l.rstrip("\r\n") for l in open(base, encoding="utf-8", errors="replace")]
    src = [l for l in src if not l.startswith("JUNK JUNK")]

    goals = sorted(f[:-4] for f in os.listdir(goals_dir) if f.endswith(".txt"))
    if only:
        goals = [g for g in goals if g in only]

    title_re = re.compile(r'^Goal\((\d+)\)\.Title\("([^"]*)"\);$')
    titles = [(i, int(m.group(1)), m.group(2)) for i, l in enumerate(src) for m in [title_re.match(l)] if m]
    # Insert point for each new goal: before the first existing title that sorts after it.
    out, linemap = [], {}
    new_ids, shift = {}, 0
    pending = sorted(goals, key=str.lower)
    remap = {}
    new_lines = set()
    ti = 0
    for i, l in enumerate(src):
        if ti < len(titles) and titles[ti][0] == i:
            _, oldid, t = titles[ti]
            while pending and pending[0].lower() < t.lower():
                g = pending.pop(0)
                new_ids[g] = oldid + shift
                shift += 1
                start = len(out)
                render_goal(new_ids[g], g, os.path.join(goals_dir, g + ".txt"), out, linemap)
                new_lines.update(range(start, len(out)))
            remap[oldid] = oldid + shift
            ti += 1
        out.append(l)
    if pending:  # would sort after every existing goal
        raise SystemExit("goals sorting last are not supported yet: %s" % pending)

    # Renumber existing goals (Title / block header / SubGoal edges / SubGoals lines) in ONE
    # pass, so the child id inside SubGoal(n) is remapped exactly once (review 2026-10-02).
    def fix(m):
        return "%s(%d)" % (m.group(1), remap.get(int(m.group(2)), int(m.group(2))))
    for i, l in enumerate(out):
        if l.startswith("Goal(") and i not in new_lines:
            out[i] = re.sub(r"\b(Goal|SubGoal)\((\d+)\)", fix, l)
    div = os.path.join(work, "merged.div")
    with open(div, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(out) + "\n")
    print("inserted:", new_ids)
    log = os.path.join(work, "merged.log")
    r = subprocess.run([sys.executable, os.path.join(HERE, "osiris_dll_compile.py"), div, log],
                       capture_output=True, text=True)
    text = open(log, encoding="utf-8", errors="replace").read() if os.path.exists(log) else r.stdout + r.stderr
    for l in text.splitlines():
        m = re.match(r"line (\d+): (.*)", l.strip())
        if m and int(m.group(1)) in linemap:
            fn, ln = linemap[int(m.group(1))]
            print("%s:%d: %s" % (fn, ln, m.group(2)))
        elif l.strip():
            print(l)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
