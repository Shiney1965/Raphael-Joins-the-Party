"""Voice diagnostic build helper (LOCAL TEST ONLY; never ship its output).

Question after 2026-10-03/04: the companion's voice test stays silent with his bank in the mod's own Soundbanks
folder (S1a) AND with the bank at the vanilla path Mods/Gustav/Localization/English/Soundbanks (Fallback C).
This build ships BOTH banks, and makes them say DIFFERENT sentences for the test line, so one cast tells which
bank (if any) the engine uses:

  * Gustav-path bank : test line -> the vanilla wem, already in that folder: "Enough! The deal is off the table."
  * mod-folder bank  : test line -> a wem copied INTO the mod folder, holding another Raphael line:
                       "Charmed, I'm sure. In more ways than one..."

Heard "Enough..."  = the Gustav-path bank is used.   Heard "Charmed..." = the mod-folder bank is used (the wiki
recipe: bank and wem together in the mod folder).   Silence = neither; the cause is not the file location.

The copied wem is Larian audio: this pak is a private diagnostic and must not be distributed.

Usage: python make_voice_diag.py <project root>
Writes build/voicediag/bank_modfolder.lsx and build/voicediag/<pattern-named>.wem; prints the wem file name.
"""
import os
import re
import subprocess
import sys

DIVINE = r"C:\bg3-sidecar-work\Tools\Divine.exe"
VOICE_PAK = r"C:\Steam Library\steamapps\common\Baldurs Gate 3\Data\Localization\Voice.pak"
VANILLA_SPK = "f65becd65cd74c88b85e6dd06b60f7b8"
COMP_SPK = "95a854c917cc477483f0ce6bf93924e2"
TEST_HANDLE = "ha15db615gad06g4578g98d7gb3e1843491e1"   # "Enough! The deal is off the table."
OTHER_HANDLE = "h9d54b589g356cg4e62ga249g8932363a24f2"  # "Charmed, I'm sure. In more ways than one..."


def main():
    root = os.path.abspath(sys.argv[1])   # Divine needs absolute paths
    out = os.path.join(root, "build", "voicediag")
    os.makedirs(out, exist_ok=True)
    mod = [d for d in os.listdir(os.path.join(root, "src", "Mods")) if d.startswith("RaphaelJoinsTheParty_")][0]
    src_bank = os.path.join(root, "src", "Mods", mod, "Localization", "English", "Soundbanks", COMP_SPK + ".lsx")
    t = open(src_bank, encoding="utf-8").read()

    def entry(handle):
        m = re.search(r'<node id="VoiceTextMetaData">\s*<attribute id="MapKey" type="FixedString" value="%s" />.*?</node>\s*</children>\s*</node>'
                      % handle, t, re.S)
        if not m:
            raise SystemExit("handle %s is not in the bank" % handle)
        return m

    other = entry(OTHER_HANDLE).group(0)
    other_len = re.search(r'id="Length" type="float" value="([^"]+)"', other).group(1)
    wem_name = "v%s_%s.wem" % (COMP_SPK, TEST_HANDLE)   # the wiki's pattern: v<voicebank id>_<handle>.wem
    m = entry(TEST_HANDLE)
    blk = m.group(0)
    new = re.sub(r'(id="Length" type="float" value=")[^"]+', r'\g<1>' + other_len, blk)
    new = re.sub(r'(id="Source" type="FixedString" value=")[^"]+', r'\g<1>' + wem_name, new)
    assert new != blk
    open(os.path.join(out, "bank_modfolder.lsx"), "w", encoding="utf-8", newline="\n").write(t[:m.start()] + new + t[m.end():])

    wem = os.path.join(out, wem_name)
    if not os.path.exists(wem):
        inner = "Mods/Gustav/Localization/English/Soundbanks/v%s_%s.wem" % (VANILLA_SPK, OTHER_HANDLE)
        r = subprocess.run([DIVINE, "-g", "bg3", "-a", "extract-single-file", "-s", VOICE_PAK, "-f", inner, "-d", wem],
                           capture_output=True, text=True)
        if not os.path.exists(wem) or os.path.getsize(wem) < 1000:
            raise SystemExit("could not extract %s from Voice.pak: %s %s" % (inner, r.stdout[-300:], r.stderr[-300:]))
    print(wem_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
