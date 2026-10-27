"""
Offline Osiris story compile check with LSLib's StoryCompiler (added 2026-09-26, after v0.2a failed to compile in game
with "1 error(s)" and no message).

The StoryCompiler bundled with Divine predates BG3's newer story header features, so this script builds a LOOSE copy:
  * story header: enum_type -> alias of INTEGER, and ITEMROOT/CHARACTERROOT re-based on GUIDSTRING
  * vanilla goals (_vanilla_story: Shared, SharedDev, Gustav, GustavDev, GustavX) + the mod goals, with enum literals
    (ARMOURSET.Vanity) replaced by their integer values
then runs StoryCompiler --no-packages --check-only and prints only the diagnostics for the mod's files.
Baseline noise is whatever the same run reports for vanilla files; compare mod results across builds, not to zero.

Usage: python story_compile_check.py <mod goals dir> [<scratch dir>]
"""
import glob, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
COMPILER = r"C:\bg3-sidecar-work\Tools\StoryCompiler.exe"
MOD = "RaphaelJoinsTheParty_745e6b7e-83fd-4953-a0ef-63865cf56da9"
VANILLA_MODS = ["Shared", "SharedDev", "Gustav", "GustavDev", "GustavX"]
META = """<?xml version="1.0" encoding="UTF-8"?>
<save>
  <version major="4" minor="0" revision="9" build="330"/>
  <region id="Config">
    <node id="root">
      <children>
        <node id="ModuleInfo">
          <attribute id="Folder" type="LSString" value="{name}"/>
          <attribute id="Name" type="LSString" value="{name}"/>
          <attribute id="UUID" type="FixedString" value="{name}"/>
          <attribute id="Version64" type="int64" value="36028797018963968"/>
        </node>
      </children>
    </node>
  </region>
</save>
"""


def main():
    goals = sys.argv[1]
    scratch = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.environ["TEMP"], "rjtp_storycheck")
    run_dir = os.path.join(scratch, "run_%d" % os.getpid())
    os.makedirs(os.path.join(run_dir, "Localization"), exist_ok=True)
    enums, hdr = {}, []
    for l in open(os.path.join(PROJ, "_vanilla_ref", "story_header.div"), encoding="utf-8").read().splitlines():
        m = re.match(r"enum_type \{(\w+), (\d+), (\d+), (.*)\}\s*$", l)
        if m:
            enums[m.group(1)] = {kv.split("=")[0].strip(): int(kv.split("=")[1]) for kv in m.group(4).split(",")}
            hdr.append(f"alias_type {{{m.group(1)}, {m.group(2)}, 1}}")
        elif re.match(r"alias_type \{(ITEMROOT|CHARACTERROOT), \d+, 19\}", l):
            hdr.append(l.replace(", 19}", ", 5}"))
        else:
            hdr.append(l)
    hdir = os.path.join(run_dir, "Mods", "Shared", "Story", "RawFiles")
    os.makedirs(hdir, exist_ok=True)
    open(os.path.join(hdir, "story_header.div"), "w", encoding="utf-8", newline="").write("\r\n".join(hdr) + "\r\n")
    enum_rx = re.compile(r"\b(" + "|".join(enums) + r")\.([A-Za-z_]\w*)\b")

    def fix(text):
        return enum_rx.sub(lambda m: str(enums[m.group(1)].get(m.group(2), 0)), text)

    sources = [(m, os.path.join(PROJ, "_vanilla_story", "Mods", m, "Story", "RawFiles", "Goals")) for m in VANILLA_MODS]
    sources.append((MOD, goals))
    for mod, src in sources:
        dst = os.path.join(run_dir, "Mods", mod, "Story", "RawFiles", "Goals")
        os.makedirs(dst, exist_ok=True)
        open(os.path.join(run_dir, "Mods", mod, "meta.lsx"), "w", encoding="utf-8").write(META.format(name=mod))
        for f in glob.glob(os.path.join(src, "*.txt")):
            t = open(f, encoding="utf-8", errors="replace").read()
            open(os.path.join(dst, os.path.basename(f)), "w", encoding="utf-8", newline="").write(fix(t))
    args = [COMPILER, "--game", "bg3", "--game-data-path", run_dir, "--no-packages", "--check-only"]
    for mod, _ in sources:
        args += ["--mod", mod]
    r = subprocess.run(args, capture_output=True, text=True, errors="replace")
    out = r.stdout + "\n" + r.stderr
    open(os.path.join(scratch, "story_compile_last.txt"), "w", encoding="utf-8").write(out)
    lines = [l for l in out.splitlines() if MOD in l or "RJTP" in l]
    print(f"StoryCompiler: {len(lines)} diagnostic line(s) mention the mod (full log: {scratch}\\story_compile_last.txt)")
    seen = set()
    for l in lines:
        if l not in seen:
            seen.add(l)
            print("  " + l.replace(f"Mods/{MOD}/Story/RawFiles/Goals/", ""))
    # Hard failures (the game's compiler rejects these; learned 2026-09-26): orphan DBs of the mod
    orphans = [l for l in seen if re.search(r'Database "(DB|QRY)_RJTP_\w+\(\d+\)" is read, but is never written', l)]
    parse = [l for l in seen if "[X00]" in l]
    if orphans or parse:
        print("FAIL: orphan read-only DB(s) or unparsable goal(s) in the mod - the game will refuse to load the save")
        sys.exit(1)


if __name__ == "__main__":
    main()
