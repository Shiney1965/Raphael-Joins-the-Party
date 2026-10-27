"""
Gives RJTP_CAMP_Raphael a cinematic timeline WITHOUT the Toolkit (plan PLAN_v0_3a_banter_2026-10-06.md, part C).

Technique (precedent: the installed mod CBR_MOXI_Scene_Library; see HAARLEP_SCENE_FEASIBILITY_2026-10-05.md): the
timeline is an UNMODIFIED copy of a vanilla, Toolkit-generated generic timeline (the donor, CAMP_Volo). A timeline
binds phases to dialog nodes by node UUID and actors to speaker slots by SpeakerMappingId, and holds no text or
audio id. So the mod's dialog takes the donor's node UUIDs and SpeakerMappingIds, and each of our lines plays in the
phase of the donor node whose UUID it carries.

This tool
  1. reads the donor (_vanilla_ref/timeline_donor/CAMP_Volo.lsj + CAMP_Volo.lsf.lsx) and lists the usable donor nodes:
     speaker 0, one text variant, the only node of its phase, exactly one TLVoice;
  2. assigns every NPC node of the dialog (src/dialogs_spec.json) to a distinct usable donor node whose TLVoice window
     (EndTime - StartTime) is at least the line's length + MARGIN; root nodes may only take donor TagGreeting phases
     (TLShowWeapon / TLPhysics exist only there); longest lines first, smallest window that fits. The assignment is
     kept in src/timeline_donor_map.json and reused on later runs while it still fits;
  3. copies the donor timeline byte for byte to src/Public/<mod>/Timeline/Generated/<Name>.lsf, and writes the scene
     file <Name>_Scene.lsf from the donor scene with a NEW Identifier (as the precedent does);
  4. writes the TimelineBank row (src/Public/<mod>/Content/Generated/[PAK]_GeneratedDialogTimelines/RJTP_TimelineBank.lsx).

Run BEFORE tools/gen_dialogs.py (which reads the map). Exit 1 on any error.
"""
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
SRC = os.path.join(PROJ, "src")
REF = os.path.join(PROJ, "_vanilla_ref")
DONOR_DIR = os.path.join(REF, "timeline_donor")
IDS = os.path.join(SRC, "ids.json")
SPEC = os.path.join(SRC, "dialogs_spec.json")
MAP = os.path.join(SRC, "timeline_donor_map.json")
DIVINE = r"C:\bg3-sidecar-work\Tools\Divine.exe"
MARGIN = 0.15            # seconds of slack required after the line inside the donor's voice window
DONOR = "CAMP_Volo"
DONOR_NPC = "2af25a85-5b9a-4794-85d3-0bd4c4d262fa"   # S_GLO_Volo, slot 0 of the donor dialog
DONOR_SHA256 = "c9b7929eb95ccfd6585b"               # first 20 hex of CAMP_Volo.lsf as extracted from Gustav.pak
DIALOG = "RJTP_CAMP_Raphael"
ORIGINAL_FILE_VERSION = "144537400540922156"         # the donor TimelineBank row's _OriginalFileVersion_

ERR = []


def err(m):
    ERR.append(m)


def val(o, k, d=None):
    x = o.get(k)
    return x["value"] if isinstance(x, dict) and "value" in x else (d if x is None else x)


def attrs(n):
    return {a.get("id"): a.get("value") for a in n.findall("attribute")}


def divine(src, dst):
    r = subprocess.run([DIVINE, "-g", "bg3", "-a", "convert-resource", "-s", src, "-d", dst], capture_output=True, text=True)
    if r.returncode or not os.path.exists(dst):
        err("Divine failed %s -> %s: %s %s" % (src, dst, r.stdout.strip()[-200:], r.stderr.strip()[-200:]))
        return False
    return True


def donor_nodes():
    """usable donor nodes: [{node, phase, window, greeting}], plus the donor's SpeakerMappingIds and bank id"""
    d = json.load(open(os.path.join(DONOR_DIR, DONOR + ".lsj"), encoding="utf-8-sig"))["save"]["regions"]["dialog"]
    spk = {val(s, "index"): (val(s, "list"), val(s, "SpeakerMappingId")) for sl in d["speakerlist"] for s in sl["speaker"]}
    if spk["0"][0] != DONOR_NPC:
        err("donor slot 0 is %s, expected %s" % (spk["0"][0], DONOR_NPC))
    nodes = {}
    for n in d["nodes"][0]["node"]:
        ntt = sum(1 for tt in n.get("TaggedTexts", []) for t in tt.get("TaggedText", [])
                  for tx in t.get("TagTexts", []) for _ in tx.get("TagText", []))
        nodes[val(n, "UUID")] = (val(n, "constructor"), val(n, "speaker"), ntt)
    root = ET.parse(os.path.join(DONOR_DIR, DONOR + ".lsf.lsx")).getroot()
    tc = root.find("region[@id='TimelineContent']/node")
    eff = [n for n in tc.find("children") if n.get("id") == "Effect"][0]
    ech = eff.find("children").findall("node")
    phases = [attrs(p) for p in [n for n in ech if n.get("id") == "Phases"][0].find("children").findall("node")]
    comps = [attrs(c) for c in [n for n in ech if n.get("id") == "EffectComponents"][0].find("children").findall("node")]
    voices = [c for c in comps if c.get("Type") == "TLVoice"]
    per_node = {}
    for p in phases:
        per_node[p["DialogNodeId"]] = per_node.get(p["DialogNodeId"], 0) + 1
    usable = []
    for i, p in enumerate(phases):
        nid = p["DialogNodeId"]
        n = nodes.get(nid)
        vs = [v for v in voices if int(v.get("PhaseIndex", 0)) == i]
        if not n or n[0] not in ("TagAnswer", "TagGreeting") or n[1] != 0 or n[2] != 1:
            continue
        if per_node[nid] != 1 or len(vs) != 1 or vs[0].get("DialogNodeId") != nid:
            continue
        window = float(vs[0].get("EndTime", 0)) - float(vs[0].get("StartTime", 0))
        usable.append({"node": nid, "phase": i, "window": round(window, 3), "greeting": n[0] == "TagGreeting"})
    return usable, spk, {p["DialogNodeId"] for p in phases}


def raphael_lengths():
    out = {}
    with open(os.path.join(REF, "dumps", "RAPHAEL_VOICED_LINES_611.tsv"), encoding="utf-8-sig", newline="") as f:
        for i, r in enumerate(csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)):
            if i and len(r) >= 5:
                out[r[0].strip()] = float(r[1] or 0)
    # Haarlep's recordings (same actor), used by the private scene: handle, length_s, source_dialog, text
    with open(os.path.join(REF, "dumps", "HAARLEP_VOICED_LINES_60.tsv"), encoding="utf-8", newline="") as f:
        for i, r in enumerate(csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)):
            if i and len(r) >= 2:
                out.setdefault(r[0].strip(), float(r[1] or 0))
    return out


def needed_seconds(node, lengths, key):
    if "line" in node:
        if node["line"] not in lengths:
            err("%s.%s: %s is not a recorded line of Raphael or Haarlep" % (DIALOG, key, node["line"]))
            return 0.0
        return lengths[node["line"]] + MARGIN
    return max(2.5, 0.07 * len(node["text"])) + MARGIN        # unvoiced gap line: reading time


def assign(dlg, usable, lengths):
    old = {}
    if os.path.exists(MAP):
        old = json.load(open(MAP, encoding="utf-8")).get(DIALOG, {}).get("nodes", {})
    by_node = {u["node"]: u for u in usable}
    need = {}
    for k, n in dlg["nodes"].items():
        if n["type"] in ("TagGreeting", "TagAnswer"):
            need[k] = needed_seconds(n, lengths, k)
    roots = set(dlg["roots"])
    result, taken = {}, set()
    # keep earlier assignments that still fit (node UUIDs must stay stable between builds)
    for k, nid in old.items():
        u = by_node.get(nid)
        if k in need and u and nid not in taken and u["window"] >= need[k] and (k not in roots or u["greeting"]):
            result[k] = nid
            taken.add(nid)
    for k in sorted((k for k in need if k not in result), key=lambda k: (k not in roots, -need[k], k)):
        cands = [u for u in usable if u["node"] not in taken and u["window"] >= need[k]
                 and (u["greeting"] if k in roots else True)]
        # a non-root line never takes a greeting phase while a root still needs one
        if k not in roots:
            cands = [u for u in cands if not u["greeting"]] or cands
        if not cands:
            err("%s.%s: no free donor phase with a voice window >= %.2f s%s"
                % (DIALOG, k, need[k], " among the donor's greeting phases" if k in roots else ""))
            continue
        u = min(cands, key=lambda u: (u["window"], u["phase"]))
        result[k] = u["node"]
        taken.add(u["node"])
    return result, need, by_node


def write_scene(mod_pub, scene_id):
    """donor scene with a new Identifier (the precedent mod changed only that and the version header)"""
    # Start from Divine's own reading of the donor .lsf, NOT from Larian's shipped _Scene.lsx: that file names its
    # region "TLScene" and its node "root", and a Divine round trip of it comes back as region "root" (2026-10-06).
    tmp = tempfile.mkdtemp(prefix="rjtp_scene_")
    donor_back = os.path.join(tmp, "donor_back.lsx")
    if not divine(os.path.join(DONOR_DIR, DONOR + "_Scene.lsf"), donor_back):
        return
    x = open(donor_back, encoding="utf-8-sig").read()
    if '<region id="TLScene">' not in x:
        err("donor scene: region TLScene not found")
        return
    m = re.findall(r'<attribute id="Identifier" type="guid" value="([0-9a-f-]{36})"\s*/>', x)
    if len(m) != 1:
        err("donor scene: expected exactly one Identifier attribute, found %d" % len(m))
        return
    lsx = os.path.join(tmp, DIALOG + "_Scene.lsx")
    with open(lsx, "w", encoding="utf-8-sig", newline="") as f:
        f.write(x.replace(m[0], scene_id))
    dst = os.path.join(mod_pub, "Timeline", "Generated", DIALOG + "_Scene.lsf")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    back = os.path.join(tmp, "back.lsx")
    if not (divine(lsx, dst) and divine(dst, back)):
        return
    # our scene, read back, must equal the donor scene read back the same way, except for the Identifier
    a = open(back, encoding="utf-8-sig").read()
    if scene_id not in a or a.replace(scene_id, "ID") != x.replace(m[0], "ID"):
        err("scene round trip differs from the donor scene by more than the Identifier")


def bank_lsx(ids, mod_folder, donor_bank_id):
    row = open(os.path.join(DONOR_DIR, DONOR + "_TimelineBank_row.lsx.txt"), encoding="utf-8").read()
    deps = re.findall(r'<node id="DependencyCache">\s*<attribute id="Object" type="guid" value="([0-9a-f-]{36})"', row)
    if donor_bank_id not in deps or DONOR_NPC not in deps:
        err("donor TimelineBank row: dialog id or NPC GUID not among its DependencyCache entries")
    deps = [ids["DLG_CAMP_BANK"] if d == donor_bank_id else ids["COMPANION"] if d == DONOR_NPC else d for d in deps]
    kids = "".join("""
						<node id="DependencyCache">
							<attribute id="Object" type="guid" value="%s" />
						</node>""" % d for d in deps)
    return ("""<?xml version="1.0" encoding="utf-8"?>
<save>
	<version major="4" minor="0" revision="9" build="0" lslib_meta="v1,bswap_guids,lsf_adjacency" />
	<region id="TimelineBank">
		<node id="TimelineBank">
			<children>
				<node id="Resource">
					<attribute id="BodyPartMocap" type="int32" value="1" />
					<attribute id="DialogResourceId" type="guid" value="%(bank)s" />
					<attribute id="EditorSourceFile" type="LSString" value="Editor/Mods/%(mod)s/Timeline/Generated/%(name)s.tml" />
					<attribute id="EditorTimelineType" type="int32" value="0" />
					<attribute id="FadeOutDuration" type="float" value="0" />
					<attribute id="FadeOutOnEnd" type="bool" value="False" />
					<attribute id="ID" type="FixedString" value="%(tl)s" />
					<attribute id="IsGenerated" type="bool" value="True" />
					<attribute id="Name" type="LSString" value="%(name)s" />
					<attribute id="SourceFile" type="LSString" value="Public/%(mod)s/Timeline/Generated/%(name)s.lsf" />
					<attribute id="_OriginalFileVersion_" type="int64" value="%(ofv)s" />
					<children>%(kids)s
					</children>
				</node>
			</children>
		</node>
	</region>
</save>
""" % {"bank": ids["DLG_CAMP_BANK"], "mod": mod_folder, "name": DIALOG, "tl": ids["TL_CAMP"],
       "ofv": ORIGINAL_FILE_VERSION, "kids": kids})


def ensure_ids(keys):
    ids = json.load(open(IDS, encoding="utf-8-sig"))
    missing = [k for k in keys if k not in ids]
    if missing:
        for k in missing:
            ids[k] = str(uuid.uuid4())
        raw = open(IDS, "rb").read()
        nl = "\r\n" if b"\r\n" in raw else "\n"
        text = json.dumps(ids, indent=2).replace("\n", nl)
        if raw.endswith(b"\n"):
            text += nl
        with open(IDS, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        print("  ids.json: added " + ", ".join(missing))
    return ids


def main():
    ids = ensure_ids(["TL_CAMP", "SCENE_CAMP"])
    mod_folder = "RaphaelJoinsTheParty_" + ids["MOD"]
    mod_pub = os.path.join(SRC, "Public", mod_folder)
    spec = json.load(open(SPEC, encoding="utf-8"))
    dlg = next(d for d in spec["dialogs"] if d["name"] == DIALOG)
    donor_lsf = os.path.join(DONOR_DIR, DONOR + ".lsf")
    sha = hashlib.sha256(open(donor_lsf, "rb").read()).hexdigest()
    if not sha.startswith(DONOR_SHA256):
        err("donor timeline hash %s... is not the one this tool was written against" % sha[:20])
    usable, spk, phase_nodes = donor_nodes()
    result, need, by_node = assign(dlg, usable, raphael_lengths())
    donor_dialog = json.load(open(os.path.join(DONOR_DIR, DONOR + ".lsj"), encoding="utf-8-sig"))["save"]["regions"]["dialog"]
    row = open(os.path.join(DONOR_DIR, DONOR + "_TimelineBank_row.lsx.txt"), encoding="utf-8").read()
    donor_bank_id = re.search(r'id="DialogResourceId" type="guid" value="([0-9a-f-]{36})"', row).group(1)
    if re.search(r'id="ID" type="FixedString" value="([0-9a-f-]{36})"', row).group(1) != val(donor_dialog, "TimelineId"):
        err("donor TimelineBank row is not the row of the donor dialog's TimelineId")
    for k, nid in result.items():
        if nid not in phase_nodes:
            err("%s.%s: mapped node %s owns no phase in the donor timeline" % (DIALOG, k, nid))
    if len(set(result.values())) != len(result):
        err("two nodes share a donor node")
    if ERR:
        return finish()
    out = {DIALOG: {"donor": DONOR, "donor_sha256": sha,
                    "speaker_mapping_ids": [spk["0"][1], spk["1"][1]],
                    "timeline_id_key": "TL_CAMP",
                    "nodes": {k: result[k] for k in sorted(result)}}}
    with open(MAP, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(out, indent=1) + "\n")
    dst = os.path.join(mod_pub, "Timeline", "Generated", DIALOG + ".lsf")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(donor_lsf, dst)
    if hashlib.sha256(open(dst, "rb").read()).hexdigest() != sha:
        err("timeline copy is not byte-identical to the donor")
    write_scene(mod_pub, ids["SCENE_CAMP"])
    bank = os.path.join(mod_pub, "Content", "Generated", "[PAK]_GeneratedDialogTimelines", "RJTP_TimelineBank.lsx")
    os.makedirs(os.path.dirname(bank), exist_ok=True)
    with open(bank, "w", encoding="utf-8", newline="\n") as f:
        f.write(bank_lsx(ids, mod_folder, donor_bank_id))
    tmp = tempfile.mkdtemp(prefix="rjtp_tlbank_")
    if divine(bank, os.path.join(tmp, "b.lsf")) and divine(os.path.join(tmp, "b.lsf"), os.path.join(tmp, "b.lsx")):
        back = open(os.path.join(tmp, "b.lsx"), encoding="utf-8-sig").read()
        for g in (ids["TL_CAMP"], ids["DLG_CAMP_BANK"], ids["COMPANION"]):
            if g not in back:
                err("TimelineBank round trip lost %s" % g)
    print("  %s: %d NPC nodes mapped onto %d usable donor phases of %s" % (DIALOG, len(result), len(usable), DONOR))
    for k in sorted(result, key=lambda k: -need[k]):
        u = by_node[result[k]]
        print("    %-18s needs %5.2f s -> phase %2d window %5.2f s (slack %4.2f)%s"
              % (k, need[k], u["phase"], u["window"], u["window"] - need[k], "  [greeting]" if u["greeting"] else ""))
    return finish()


def finish():
    for e in ERR:
        print("  ERROR " + e)
    print("gen_timelines: %d error(s)" % len(ERR))
    sys.exit(1 if ERR else 0)


if __name__ == "__main__":
    main()
