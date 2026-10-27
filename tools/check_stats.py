"""
Static checks for RJTP stats + localization.
  * every 'using' parent exists (mod or vanilla stats)
  * every passive in a Character 'Passives' list exists
  * every UnlockSpell(...) target exists
  * every DisplayName/Description handle resolves in the mod english.xml or vanilla english.xml
  * every OpenMessageBox/OpenMessageBoxYesNo key used by the goals exists in the mod english.xml
  v0.2:
  * every RJTP_FORM_* status and every *_RJTP_* spell the goals name exists as a mod stats entry
  * form statuses: POLYMORPHED, StackId RJTP_FORM_VISUAL, one StackPriority, StackType Overwrite, no StatusGroups,
    Rules = a mod shapeshift rule, TemplateID = a mod or vanilla root template; Ascended ones are combat-only
  * spell containers: every child exists and points back (SpellContainerID); form children have no SpellProperties
  * suit armour: slot as planned, RootTemplate is the mod root template of the same name carrying these Stats
  * every TranslatedString handle in the mod LSX files resolves
  * every Name_GUID constant in the goals whose GUID is a mod id is defined by a mod resource with that name
Usage: python check_stats.py <report_path>   (exit 1 on errors)
"""
import glob, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REF = os.path.join(PROJ, "_vanilla_ref")


def parse_stats(files):
    E = {}
    for f in files:
        t = open(f, encoding="utf-8", errors="replace").read()
        for m in re.finditer(r'new entry "([^"]+)"\n(.*?)(?=\nnew entry|\Z)', t, re.S):
            body = m.group(2)
            E[m.group(1)] = {
                "file": f,
                "type": (re.search(r'type "([^"]+)"', body) or [None, None])[1],
                "using": (re.search(r'using "([^"]+)"', body) or [None, None])[1],
                "data": dict(re.findall(r'data "([^"]+)" "([^"]*)"', body)),
            }
    return E


def resolved(ALL, name, field):
    """a stats field, following 'using' inheritance"""
    seen = set()
    while name and name in ALL and name not in seen:
        seen.add(name)
        if field in ALL[name]["data"]:
            return ALL[name]["data"][field]
        name = ALL[name]["using"]
    return None


GUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def mod_lsx_objects(proj):
    """GUID -> set of names, from every mod LSX (MapKey/UUID/ID + Name/RuleName/Faction of the same node)"""
    import xml.etree.ElementTree as ET
    out, files = {}, []
    for f in glob.glob(os.path.join(proj, "src", "**", "*.lsx"), recursive=True):
        files.append(f)
        root = ET.parse(f).getroot()
        for n in root.iter("node"):
            a = {x.get("id"): x.get("value") for x in n.findall("attribute")}
            for k in ("MapKey", "UUID", "ID"):
                g = a.get(k)
                if g and re.fullmatch(GUID, g):
                    nm = a.get("Name") or a.get("RuleName") or a.get("Faction") or ""
                    out.setdefault(g, set()).add(nm)
    return out, files


def main():
    out = sys.argv[1]
    errors, notes = [], []
    mod_stats_files = glob.glob(os.path.join(PROJ, "src", "Public", "*", "Stats", "Generated", "Data", "*.txt"))
    vanilla_files = [f for f in glob.glob(os.path.join(REF, "stats", "**", "*.txt"), recursive=True) if "Honour" not in f]
    V = parse_stats(vanilla_files)
    M = parse_stats(mod_stats_files)
    ALL = dict(V); ALL.update(M)
    loca_mod = open(glob.glob(os.path.join(PROJ, "src", "Mods", "*", "Localization", "English", "english.xml"))[0], encoding="utf-8").read()
    mod_keys = set(re.findall(r'contentuid="([^"]+)"', loca_mod))
    van_keys = set(re.findall(r'contentuid="([^"]+)"', open(os.path.join(REF, "english.xml"), encoding="utf-8-sig").read()))
    for name, e in M.items():
        if e["using"] and e["using"] not in ALL:
            errors.append(f"{name}: using '{e['using']}' not found")
        for k in ("DisplayName", "Description"):
            v = e["data"].get(k)
            if v:
                h = v.split(";")[0]
                if h not in mod_keys and h not in van_keys:
                    errors.append(f"{name}: {k} handle {h} not in mod or vanilla loca")
        if "Passives" in e["data"]:
            for p in [x for x in e["data"]["Passives"].split(";") if x]:
                if p not in ALL:
                    errors.append(f"{name}: passive '{p}' not found")
        for b in re.findall(r"UnlockSpell\(([^)]+)\)", e["data"].get("Boosts", "")):
            if b not in ALL:
                errors.append(f"{name}: UnlockSpell target '{b}' not found")
        notes.append(f"ok-checked {name} (using {e['using']})")
    # message keys used by goals
    for g in glob.glob(os.path.join(PROJ, "src", "Mods", "*", "Story", "RawFiles", "Goals", "*.txt")):
        t = open(g, encoding="utf-8").read()
        for key in re.findall(r'(?:OpenMessageBox(?:YesNo)?|PROC_RJTP_Box)\([^,]+,\s*"(RJTP_Msg_[A-Za-z_]+)"', t):
            if key not in mod_keys:
                errors.append(f"{os.path.basename(g)}: message key {key} not in english.xml")
        for key in re.findall(r'(?:MessageBox(?:YesNo)?Closed|PROC_RJTP_BoxAnswered|PROC_RJTP_BoxClosed)\([^,]+,\s*"(RJTP_Msg_[A-Za-z_]+)"', t):
            if key not in mod_keys:
                errors.append(f"{os.path.basename(g)}: answer-handler key {key} not in english.xml")
        # every Yes/No key that is shown must have both a 1 and a 0 handler
        shown = set(re.findall(r'PROC_RJTP_Box\([^,]+,\s*"(RJTP_Msg_[A-Za-z_]+)",\s*1\)', t))
        for key in shown:
            for r in ("1", "0"):
                if not re.search(r'PROC_RJTP_BoxAnswered\(\(CHARACTER\)_Player,\s*"%s",\s*%s\)' % (key, r), t):
                    errors.append(f"{os.path.basename(g)}: Yes/No box {key} has no handler for result {r}")
        for key in re.findall(r'PROC_RJTP_TellAvatars\("(RJTP_Msg_[A-Za-z_]+)"\)', t):
            if key not in mod_keys:
                errors.append(f"{os.path.basename(g)}: TellAvatars key {key} not in english.xml")

    # ------------------------------------------------------------ v0.2 checks
    goals_txt = "\n".join(open(g, encoding="utf-8").read() for g in
                          glob.glob(os.path.join(PROJ, "src", "Mods", "*", "Story", "RawFiles", "Goals", "*.txt")))
    objs, lsx_files = mod_lsx_objects(PROJ)
    van_rt = set()
    for f in glob.glob(os.path.join(REF, "roottemplates", "*_RT.lsx")):
        van_rt |= set(re.findall(r'id="MapKey" type="FixedString" value="(' + GUID + ')"', open(f, encoding="utf-8-sig").read()))
    # (a) every status / spell name the goals use exists as a mod stat entry
    for st in sorted(set(re.findall(r'"(RJTP_FORM_[A-Z0-9_]+)"', goals_txt))):
        if st not in M:
            errors.append(f"goals use status {st}: no stats entry")
    for sp in sorted(set(re.findall(r'"((?:Shout|Projectile|Zone|Target)_RJTP_[A-Za-z0-9_]+)"', goals_txt))):
        if sp not in M:
            errors.append(f"goals use spell {sp}: no stats entry")
    # (b) form statuses: POLYMORPHED, one StackId, equal StackPriority, Overwrite, no StatusGroups, rule + template exist
    forms = {n: e for n, e in M.items() if e["type"] == "StatusData" and n.startswith("RJTP_FORM_")}
    prios = set()
    for n, e in forms.items():
        d = e["data"]
        if d.get("StatusType") != "POLYMORPHED":
            errors.append(f"{n}: StatusType {d.get('StatusType')} (want POLYMORPHED)")
        if d.get("StackId") != "RJTP_FORM_VISUAL":
            errors.append(f"{n}: StackId {d.get('StackId')} (want RJTP_FORM_VISUAL)")
        if d.get("StackType") != "Overwrite":
            errors.append(f"{n}: StackType {d.get('StackType')} (want Overwrite)")
        if d.get("StatusGroups"):
            errors.append(f"{n}: has StatusGroups {d['StatusGroups']} (must have none)")
        prios.add(d.get("StackPriority"))
        rule = d.get("Rules")
        if not rule or not any(nm.startswith("RJTP_Form_Visual") for nm in objs.get(rule, ())):
            errors.append(f"{n}: Rules {rule} is not a mod shapeshift rule")
        tpl = d.get("TemplateID")
        if not tpl or (tpl not in objs and tpl not in van_rt):
            errors.append(f"{n}: TemplateID {tpl} not found in mod or vanilla root templates")
        if n.startswith("RJTP_FORM_ASCENDED"):
            if d.get("RemoveConditions") != "not Combat()" or d.get("RemoveEvents") != "OnApply;OnTurn;OnCombatEnded":
                errors.append(f"{n}: combat-only RemoveConditions/RemoveEvents missing")
        notes.append(f"form status {n}: template {tpl}, rule {rule}")
    if len(prios) > 1:
        errors.append(f"form statuses have different StackPriority values {sorted(prios, key=str)}")
    # (c) spell containers: children exist, point back, container lists them; form children are pure triggers
    for n, e in M.items():
        if e["type"] != "SpellData":
            continue
        kids = [x for x in e["data"].get("ContainerSpells", "").split(";") if x]
        for k in kids:
            if k not in M:
                errors.append(f"{n}: container child {k} missing")
            elif M[k]["data"].get("SpellContainerID") != n:
                errors.append(f"{k}: SpellContainerID {M[k]['data'].get('SpellContainerID')} (want {n})")
        cid = e["data"].get("SpellContainerID")
        if cid:
            if n not in (resolved(ALL, cid, "ContainerSpells") or "").split(";"):
                errors.append(f"{n}: not listed in {cid} ContainerSpells")
            if n.startswith("Shout_RJTP_Form_") and resolved(ALL, n, "SpellProperties"):
                errors.append(f"{n}: form spells must be pure triggers (SpellProperties not empty)")
    # (d) armour: RootTemplate is a mod root template whose Stats names this entry; slot is what the plan needs
    want_slot = {"RJTP_ARM_RaphaelSuit": "Breast", "RJTP_ARM_RaphaelShoes": "Boots",
                 "RJTP_ARM_RaphaelSuit_Camp": "VanityBody", "RJTP_ARM_RaphaelShoes_Camp": "VanityBoots"}
    rt_text = "\n".join(open(f, encoding="utf-8").read() for f in lsx_files if os.sep + "RootTemplates" + os.sep in f)
    for n, slot in want_slot.items():
        if n not in M:
            errors.append(f"armour {n} missing"); continue
        got = resolved(ALL, n, "Slot")
        if got != slot:
            errors.append(f"{n}: Slot {got} (want {slot})")
        rt = M[n]["data"].get("RootTemplate")
        if n not in objs.get(rt, ()):
            errors.append(f"{n}: RootTemplate {rt} is not a mod root template named {n}")
        elif f'<attribute id="Stats" type="FixedString" value="{n}" />' not in rt_text:
            errors.append(f"{n}: no root template carries Stats {n}")
        notes.append(f"armour {n}: slot {got}, AC {resolved(ALL, n, 'ArmorClass')}, RT {rt}")
    # (e) every TranslatedString handle in mod LSX resolves
    for f in lsx_files:
        for h in re.findall(r'type="TranslatedString" handle="([^"]+)"', open(f, encoding="utf-8").read()):
            if h not in mod_keys and h not in van_keys and h != "ls::TranslatedStringRepository::s_HandleUnknown":
                errors.append(f"{os.path.relpath(f, PROJ)}: loca handle {h} missing")
    # (f) every Name_GUID constant in the goals whose GUID is a mod id resolves to a mod resource of that name
    import json
    ids = json.load(open(os.path.join(PROJ, "src", "ids.json")))
    mod_guids = set(ids.values())
    for nm, g in sorted(set(re.findall(r"\b([A-Za-z][A-Za-z0-9_]*?)_(" + GUID + r")\b", goals_txt))):
        if g not in mod_guids:
            continue
        if g not in objs:
            errors.append(f"goal constant {nm}_{g}: GUID not defined by any mod resource")
        elif nm not in objs[g]:
            errors.append(f"goal constant {nm}_{g}: mod resource name is {sorted(objs[g])}")
        else:
            notes.append(f"goal constant {nm}_{g}: ok")
    rep = [f"Stats/loca check: {len(M)} mod entries, {len(errors)} error(s)"] + ["  ERROR " + e for e in errors] + ["  " + n for n in notes]
    open(out, "w", encoding="utf-8").write("\n".join(rep) + "\n")
    print("\n".join(rep))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
