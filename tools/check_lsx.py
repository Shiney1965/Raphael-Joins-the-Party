"""
Parse check for a staged or source tree: every .lsx / .xml must be well-formed XML, every .json must load.
Usage: python check_lsx.py <dir> [<dir> ...]   (exit 1 on any failure)
"""
import glob, json, os, sys
import xml.etree.ElementTree as ET


def main():
    bad, n = [], 0
    for d in sys.argv[1:]:
        for f in glob.glob(os.path.join(d, "**", "*"), recursive=True):
            low = f.lower()
            try:
                if low.endswith((".lsx", ".xml")):
                    ET.parse(f); n += 1
                elif low.endswith(".json"):
                    json.load(open(f, encoding="utf-8-sig")); n += 1
            except Exception as e:  # noqa: BLE001 - report every parse failure
                bad.append(f"{f}: {e}")
    print(f"parse check: {n} file(s) parsed, {len(bad)} failure(s)")
    for b in bad:
        print("  FAIL " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
