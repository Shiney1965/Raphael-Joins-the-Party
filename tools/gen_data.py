"""
Generates every non-Osiris source file of Raphael Joins the Party (v0.2) into src/ from src/ids.json.
Re-runnable: overwrites generated files only (goal .txt files, ScriptExtender, MCM blueprint and dialog files are
written by hand or by other tools and are not touched).
v0.2 adds (plan PLAN_v0_2.md sections 4, 7, 9, 10): form statuses, the Change Form spell container, suit armour,
the shapeshift Rulebook, the Wardrobe CharacterVisual, form/suit root templates, debug shouts, new loca, and the
optional merge of src/dialog_loca.json.
"""
import copy, json, os, re, uuid, html
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REF = os.path.join(PROJ, "_vanilla_ref")
SRC = os.path.join(PROJ, "src")
ids = json.load(open(os.path.join(SRC, "ids.json")))
MODFOLDER = "RaphaelJoinsTheParty_" + ids["MOD"]
MODS = os.path.join(SRC, "Mods", MODFOLDER)
PUB = os.path.join(SRC, "Public", MODFOLDER)
COMP = ids["COMPANION"]


def version64(major, minor, revision, build):
    # same packing as the v0.1.1 value (1<<47)|(1<<31): major<<55 | minor<<47 | revision<<31 | build
    return str((major << 55) | (minor << 47) | (revision << 31) | build)


assert version64(0, 1, 1, 0) == str((1 << 47) | (1 << 31))   # the v0.1.1.0 value this generator used before
VERSION64 = version64(1, 0, 0, 0)  # 1.0.0.0 (release)

HUMAN_RACE = "0eb594cb-8820-4be6-a58d-8be7a1a98fba"      # Origins.lsx Hireling_Rogue (Human)
WARLOCK = "b4225a4b-4bbe-4d97-9e3c-4719dbd1487c"          # Origins.lsx Hireling_Warlock ClassUUID
WARLOCK_SUB = "e1e4a21f-9405-46ec-81a0-ccc8d58d9736"      # Origins.lsx Hireling_Warlock SubClassUUID
BACKGROUND = "76925f0b-3ec8-4f42-86a9-cd4f745af2ac"        # Origins.lsx Hireling_Warlock BackgroundUUID
# The companion has his OWN voice table with one untagged row, as every vanilla dedicated origin does (Lae'zel:
# table 46069209, row SpeakerUUID = her GUID). Until 2026-10-04 he used Hireling_Cleric's table 5099a882; the
# engine then gave him that table's generic "male voice 5" row (speaker 4df6dba0), so every Raphael line was
# looked up in the wrong speaker's bank and stayed silent (SE log voice-diag, 2026-10-04).
VOICE_TABLE = ids["VOICE_TABLE"]
# The row's SpeakerUUID is VANILLA Raphael's speaker id (S_GLO_Monitor), so every line is looked up in Larian's own
# bank f65becd6....lsf and plays Larian's .wem files in place: nothing is copied or re-keyed. Proven in game on
# 2026-10-04 (console `!rjtp_speaker raphael`, then both voice tests spoke the right line). What did NOT work:
# his own speaker id with a re-keyed bank in the vanilla Soundbanks folder (silent); a re-keyed bank in the mod's
# own folder works only with a COPY of each .wem beside it. Shared speaker ids are vanilla-normal (the generic
# voice 4df6dba0 is shared by hirelings and player voice tables).
VOICE_SPEAKER = "f65becd6-5cd7-4c88-b85e-6dd06b60f7b8"
RAPHAEL_NAME_HANDLE = "h1ea7aa50g70c6g4ce4g85b2geedd37622b36"
HERO_FACTION = "a1542c81-6895-929e-4522-10ce218bb360"
GOOD_FACTION = "b37bfd4c-baed-08f4-9866-290f8bb39e62"
EVIL_FACTION = "4be9261a-e481-8d9d-3528-f36956a19b17"
# v0.2 vanilla references (each verified in _vanilla_ref; file:line in the comment)
RAPHAEL_VISUAL = "dc5589d3-5f3b-0ac4-ef9d-88c34dd85f9c"   # S_GLO_Monitor CharacterVisual, forms/gustav/Public/Gustav/Content/[PAK]_CharacterVisuals/_merged.lsx:164721
RAPHAEL_ICON = RAPHAEL_VISUAL + "-EQP_Unarmed_(Icon_Raphael_Human)"   # the v0.1 global's Icon value (unchanged)
HUMAN_MALE_RACE_EQ = "7d73f501-f65e-46af-a13b-2cacf3985d05"   # EquipmentRace of BASE_Humans_Male, roottemplates/Shared_RT.lsx:502141
BASE_HUMANS_MALE = "acd7060a-43bd-4dc9-b050-9d9b2cf7b7df"     # BASE_Humans_Male MapKey, roottemplates/Shared_RT.lsx:502146
DEVIL_FORM_TPL = "1f9da419-8224-42e8-894a-8907cb978360"       # QUEST_Monitor_DevilForm, roottemplates/Shared_RT.lsx:85136
ASCENDED_TPL = "f5e9cb22-70c4-46ba-bff8-ed9fe8dfb1c8"         # LOW_Raphael_MonsterForm, stats GustavDev Status_POLYMORPHED.txt:708
BEAST_X2_TPL = "001b64f6-4918-4045-8197-878cf263e893"         # QUEST_Monitor_BeastForm (devil, Scale 2), roottemplates/GustavDev_RT.lsx:9-12
SUIT_PANTS = "3a35f3b1-d0e6-d619-7cc5-cbeaa310de84"           # dc5589d3 Slot Body  (_merged.lsx:165008)
SUIT_BOOTS = "a9656a45-a817-f584-858f-ace0d272c54f"           # dc5589d3 Slot Footwear (_merged.lsx:165013)
SUIT_DOUBLET = "40e03b09-467b-fb02-368e-54f030eb49cf"         # dc5589d3 Slot Body  (_merged.lsx:165018)
MODESTY_LEAF = "04649972-9e6b-1511-337e-74977ed693b0"         # Humans_Male_Player visual 40b6c0b8, forms/shared/.../[PAK]_CharacterVisuals/_merged.lsx:32161
PRIVATE_PARTS = "6236e77f-6127-5de9-d390-72b0ed12d1fd"        # same visual, _merged.lsx:32171


def handle(name):
    u = uuid.uuid5(uuid.UUID(ids["MOD"]), name)
    return "h" + str(u).replace("-", "g")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


LOCA = {}
LOCA_VER = {}


def loca(key_or_handle, text, version=1):
    LOCA[key_or_handle] = text
    LOCA_VER[key_or_handle] = version
    return key_or_handle


# ---------------------------------------------------------------- strings
H_VOICE = loca(handle("voice_name"), "Raphael")
H_PASSIVE_NAME = loca(handle("passive_name"), "Infernal Heritage")
H_PASSIVE_DESC = loca(handle("passive_desc"),
    "Raphael keeps a sliver of his true nature: Igniting Spark, Flames of Avernus, Infernal Guise, Resistance to "
    "Fire damage and proficiency with Heavy Armour. Flames of Avernus uses an Infernal Charge, regained on a Long "
    "Rest.")
# v0.4a (PLAN_v0_4a_traits_2026-10-17.md): the Infernal Charge and four optional traits (MCM)
H_CHARGE_NAME = loca(handle("charge_name"), "Infernal Charge")
H_CHARGE_DESC = loca(handle("charge_desc"),
    "Fuels Raphael's Flames of Avernus. Regained on a Long Rest, or by Soul Reaper.")
H_T_REAPER = loca(handle("trait_reaper_name"), "Soul Reaper")
H_T_REAPER_D = loca(handle("trait_reaper_desc"),
    "Once per Short Rest, when Raphael lands the killing blow on an enemy, he severs its soul and regains his "
    "Infernal Charge for Flames of Avernus.")
H_T_RESOLVE = loca(handle("trait_resolve_name"), "Inevitable Resolve")
H_T_RESOLVE_D = loca(handle("trait_resolve_desc"),
    "Once per Short Rest, in combat: when Raphael is Held, Dominated, Incapacitated, Restrained, Turned, Planar "
    "Bound or forced to dance, the effect ends after 1 turn.")
H_T_FIENDISH = loca(handle("trait_fiendish_name"), "Fiendish Blessing")
H_T_FIENDISH_D = loca(handle("trait_fiendish_desc"), "Raphael's infernal nature grants him +2 Armour Class.")
H_SPARK_DESC = loca(handle("spark_desc"),
    "Launch a mote of infernal flame at a target. On a hit it deals Fire damage that grows with your level, "
    "and sets the target Burning.")
H_AVERNUS_DESC = loca(handle("avernus_desc"),
    "Loose a searing wave of infernal fire from your palms. Uses an Infernal Charge (regained on a Long Rest).")
H_DBG_RECRUIT = loca(handle("dbg_recruit"), "RJTP TEST: Recruit Raphael here")
H_DBG_SUMMON = loca(handle("dbg_summon"), "RJTP TEST: Summon Raphael here (10 s)")
H_DBG_STATUS = loca(handle("dbg_status"), "RJTP TEST: Show mod state")

Y_ = "<br><br><b>Yes:</b> "
N_ = "<br><br><b>No:</b> "
MSG = {
    # v0.3g: the author's player phrases on every choice (HOH_OFFER_SCRIPT_DRAFT_2026-10-17.md). Buttons stay Yes / No.
    "RJTP_Msg_Offer":
        "Raphael steps out of the shadows beside the portal.<br><br>\"Leaving so soon? You walked my halls, "
        "you gazed upon our contract, and you left it whole. How refreshingly... honest.<br><br>"
        "The road to the Crown runs through dangerous country. Perhaps I should see our investment protected "
        "personally.\"" + Y_ + "\"OK Raphael, if you are so nervous about it, why don't you join us, so long as you "
        "help and don't just make snarky jokes.\"" + N_ + "\"Raphael, I think I would feel safer with you looking "
        "over us from Avernus. But I look forward to seeing you again.\"",
    "RJTP_Msg_TheftDemand":
        "Raphael steps out of the smoke, holding up a hand to still his servants.<br><br>\"You have something "
        "that belongs to my Archive. Return it, and this unpleasantness is forgotten. Keep it... and our "
        "contract permits me a great many things.\"" + Y_ + "\"Well, Raphael, since you asked so nicely, here you "
        "go.\"" + N_ + "\"Raphael, I have had enough of your bossing. You stole the item, and now I stole it from "
        "you. Seems fair to me.\"",
    "RJTP_Msg_ConfirmRefuse":
        "\"Think very carefully.\"" + Y_ + "\"I have thought about it. It stays with me.\"" + N_ +
        "\"Fine, fine. Take your trinket back, before you sulk.\"<br><br>(Keeping it means Raphael will not let "
        "you leave: you will have to fight him, or yield your soul.)",
    "RJTP_Msg_ItemGone":
        "Raphael's smile does not reach his eyes.<br><br>\"Gone? Then there is nothing left to return but "
        "what the contract promises me.\"",
    "RJTP_Msg_OfferAfterReturn":
        "The treasure returns to its place.<br><br>\"There. Was that so hard? Consider the matter closed.<br>"
        "Now - the road to the Crown is long, and you are clearly in need of supervision.\"" + Y_ +
        "\"I don't need your supervision, Raphael, but if you are willing to help and not just make snarky jokes, "
        "then by all means join us.\"" + N_ + "\"The last thing I need is supervision by a sarcastic devil. I think "
        "we are better off using our own best judgment.\"",
    "RJTP_Msg_OfferNothingToReturn":
        "\"You rummaged where you should not have, but nothing of mine left the room. I shall be generous.<br>"
        "The road to the Crown is long, and you are clearly in need of supervision.\"" + Y_ + "\"Generous? From "
        "you? Fine, Raphael, join us, but help, and keep the snarky jokes to a minimum.\"" + N_ + "\"Thank you for "
        "your generosity, Raphael, but we will manage just fine without supervision from a sarcastic devil.\"",
    "RJTP_Msg_Declined":
        "\"As you wish. Our contract stands. Do try not to die before you deliver.\"<br>Raphael vanishes.",
    "RJTP_Msg_DeclinedAfterReturn":
        "\"As you wish. The debt is settled - this time.\"<br>Raphael vanishes.",
    "RJTP_Msg_Joined": "Raphael has joined your party.",
    "RJTP_Msg_PartyFull": "Your party is full. Raphael will wait for you in camp.",
    "RJTP_Msg_InCombat": "Finish the fight before you leave the House of Hope.",
    "RJTP_Msg_Betrayal":
        "Raphael's form flickers with hellfire.<br><br>\"You break faith with ME? Then our association is "
        "at an end.\"<br>Raphael has left the party.",
    "RJTP_Msg_Dismissed": "Raphael has left your company for good.",
    "RJTP_Msg_Farewell":
        "Raphael adjusts his cuffs.<br><br>\"Our business together is nearly concluded. I shall await my "
        "prize where it will be delivered. Do not keep me waiting.\"<br>Raphael has left the party.",
    "RJTP_Msg_AstralWithdraw":
        "Raphael watches the Astral Plane with open hunger.<br><br>\"This is where I leave you. I have "
        "business to attend to before the end.\"<br>Raphael has left the party for good. His belongings "
        "were handed to you.",
    "RJTP_Msg_ConfirmDecline":
        "\"Are you quite certain? Offers from me are... rarely repeated. And no one refuses me and simply walks "
        "out of my House.\"" + Y_ + "\"Well, on second thought, only because you are such a handsome devil, OK.\"" + N_ +
        "\"Well, on second thought... the answer is still No. I don't feel that you would be a good fit for our "
        "team.\"<br><br>(If you still refuse, he will not let you leave in peace.)",
    "RJTP_Msg_OfferHope":
        "Raphael steps out beside the portal, and the air still smells of Hope's broken chains.<br><br>"
        "\"You set my little prisoner free. Our contract gives me every right to your soul for that, here and "
        "now. And yet... one soul is such a small thing beside a crown. Let her keep her freedom, and her "
        "House. You shall have me instead.\"" + Y_ + "\"Hope keeps her freedom and her House, and you keep your "
        "snarky jokes to yourself. Then we have a deal. Join us.\"" + N_ + "\"Hope is free, and so are we. We "
        "will manage without you, Raphael.\"<br><br>(Hope stays behind in the House.)",
    "RJTP_Msg_Reckoning":
        "Raphael's smile thins into something far older.<br><br>\"Then we come to the part of our contract you "
        "only skimmed.\"" + Y_ + "\"Then let's skip the fine print. Come and take it, devil.\" (The battle for "
        "the House of Hope begins.)" + N_ + "\"...Fine. Take what you are owed.\" (Yield your soul; you will be "
        "asked to confirm.)",
    "RJTP_Msg_ConfirmYield":
        "\"Wise. It hurts so much less this way.\"" + Y_ + "\"Get it over with.\" (This ends the game.)" + N_ +
        "\"Not yet. Let me choose again.\" (Back to the choice.)",
    # v0.3e: shown only if the game ever returns an answer other than Yes (1) or No (0)
    "RJTP_Msg_BadAnswer":
        "Raphael Joins the Party: the game returned an unreadable answer to that box, so nothing was done. "
        "Repeat what you were doing (at the House of Hope: use the portal again).",
    # v0.3f test spell (RJTP_TestTheft.txt)
    "RJTP_Msg_TestTheft_NotAtPortal":
        "RJTP TEST: cast this in the House of Hope foyer, next to the exit portal, with the whole party in the "
        "foyer (the spell \"Go to the House of Hope\" puts you there).",
    "RJTP_Msg_TestTheft_AlarmUp":
        "RJTP TEST: the House of Hope alarm is already up in this save. Load a save from before the alarm.",
    "RJTP_Msg_TestTheft_NoOffer":
        "RJTP TEST: the offer is not available in this save (no deal, contract gone, Raphael already met or "
        "answered). Cast \"Show mod state\" to see why.",
    "RJTP_Msg_TestTheft_NoItem":
        "RJTP TEST: neither Archive treasure (gauntlets, amulet) is left to take in this save.",
    "RJTP_Msg_TestTheft_Go":
        "RJTP TEST: theft staged. An Archive treasure is in your inventory and the house alarm is up. Use the "
        "exit portal now (the debtors gather in the hall, not here).",
    # v0.3d test spell (RJTP_TestHoH.txt)
    "RJTP_Msg_TestHoH_Level":
        "RJTP TEST: go to the Lower City first (fast-travel anywhere in it), then cast this again.",
    "RJTP_Msg_TestHoH_Recruited":
        "RJTP TEST: in this save Raphael has already joined, left or been answered, or his offer is open right "
        "now (answer it first), so the House of Hope offer cannot be made. Otherwise load a save from before he "
        "joined.",
    "RJTP_Msg_TestHoH_Story":
        "RJTP TEST: in this save Raphael is dead or has already appeared in the House of Hope, or the contract "
        "is gone. The offer cannot be made here.",
    "RJTP_Msg_TestHoH_VisitedNoDeal":
        "RJTP TEST: this save has already been to the House of Hope without the deal, so the house is set up "
        "for that run. Use a save from before the first visit.",
    "RJTP_Msg_TestHoH_Alarm":
        "RJTP TEST: the House of Hope alarm is already up for a reason other than theft or freeing Hope, so the "
        "base game plays out. Use another save.",
    "RJTP_Msg_TestHoH_Busy": "RJTP TEST: finish the fight or conversation first.",
    "RJTP_Msg_TestHoH_Go":
        "RJTP TEST: taking the party into the House of Hope. Once there, gather the whole party at the exit "
        "portal and use it.",
    "RJTP_Msg_TestHoH_GoDeal":
        "RJTP TEST: the deal with Raphael was set for testing (the Orphic Hammer is in your inventory).<br><br>"
        "Taking the party into the House of Hope. Once there, gather the whole party at the exit portal and use "
        "it.",
    "RJTP_Msg_TestHoH_ConfirmDeal":
        "RJTP TEST: this save has no deal with Raphael. The test sets the deal (as the base game's own debug "
        "shortcut does) and gives you the Orphic Hammer. <b>This permanently alters this save's story</b> - use "
        "a throwaway save.<br><br><b>Set the deal and go to the House of Hope?</b>",
    "RJTP_Msg_DebugState": "RJTP test build loaded. Debug spells are in your spellbook.",
    "RJTP_Msg_Dismissed_Gear": "His belongings were handed to you.",
    # v0.2 (RJTP_Forms.txt PROC_RJTP_Uninstall)
    "RJTP_Msg_Uninstalled":
        "Raphael Joins the Party: companion forms cleared and Raphael withdrawn. You can now save and remove the mod.",
}
for k, v in MSG.items():
    loca(k, v)

# ---------------------------------------------------------------- meta.lsx
write(os.path.join(MODS, "meta.lsx"), f"""<?xml version="1.0" encoding="UTF-8"?>
<save>
    <version major="4" minor="8" revision="0" build="500"/>
    <region id="Config">
        <node id="root">
            <children>
                <node id="Conflicts"/>
                <node id="Dependencies">
                    <children>
                        <node id="ModuleShortDesc">
                            <attribute id="Folder" type="LSString" value="GustavX"/>
                            <attribute id="MD5" type="LSString" value="ef3fcba3f3684b3088ad1f9874d4957c"/>
                            <attribute id="Name" type="LSString" value="GustavX"/>
                            <attribute id="PublishHandle" type="uint64" value="0"/>
                            <attribute id="UUID" type="guid" value="cb555efe-2d9e-131f-8195-a89329d218ea"/>
                            <attribute id="Version64" type="int64" value="145241946983074840"/>
                        </node>
                    </children>
                </node>
                <node id="ModuleInfo">
                    <attribute id="Author" type="LSString" value="Serpentine (NexusMods: SerpentineShel)"/>
                    <attribute id="CharacterCreationLevelName" type="FixedString" value=""/>
                    <attribute id="Description" type="LSString" value="Made the deal with Raphael and kept the contract? Invite him into your party at the House of Hope exit portal. Refuse him, and you must fight him or yield your soul. Adds his looks, signature powers, optional traits, banter and his own camp conversation."/>
                    <attribute id="Folder" type="LSString" value="{MODFOLDER}"/>
                    <attribute id="LobbyLevelName" type="FixedString" value=""/>
                    <attribute id="MD5" type="LSString" value=""/>
                    <attribute id="MenuLevelName" type="FixedString" value=""/>
                    <attribute id="Name" type="LSString" value="Raphael Joins the Party"/>
                    <attribute id="NumPlayers" type="uint8" value="4"/>
                    <attribute id="PhotoBooth" type="FixedString" value=""/>
                    <attribute id="PublishHandle" type="uint64" value="0"/>
                    <attribute id="StartupLevelName" type="FixedString" value=""/>
                    <attribute id="UUID" type="FixedString" value="{ids['MOD']}"/>
                    <attribute id="Version64" type="int64" value="{VERSION64}"/>
                    <children>
                        <node id="PublishVersion">
                            <attribute id="Version64" type="int64" value="{VERSION64}"/>
                        </node>
                    </children>
                </node>
            </children>
        </node>
    </region>
</save>
""")

# ---------------------------------------------------------------- global character (clone of S_GLO_Monitor, reworked)
def guid_node(nid, vals):
    return "".join(f"""
								<node id="{nid}">
									<attribute id="Object" type="guid" value="{v}" />
								</node>""" for v in vals)

tags = ["7fbed0d4-cabc-4a9d-804e-12ca6088a0a8",  # HUMANOID (WW_MJP comment)
        "2a4f9fcc-5891-4150-bf3f-a219e69a7f33",  # DONOTUSE_COMPANION (WW_MJP comment)
        ids["TAG_ORIGIN"]]
speaker_groups = ["02cdc15e-1dc3-5eb4-f73c-9458b4f90b9f",  # GROUP_PartyMembers
                  "e0d1ff71-04a8-4340-ae64-9684d846eb83",  # GROUP_Players
                  "ae20615c-be4a-5278-2db7-10b3feade3e1",  # Hireling.lsj speaker slot 0 group (review 08 S6)
                  "6e51f2eb-9fdf-4f95-a66b-7043e700795b",  # from S_GLO_Monitor
                  "4e16d397-c917-841a-a715-7a9969b8ddf3"]  # from S_GLO_Monitor
# Voice spike S1b build variant (plan v0.2 section 6.3; research 20): the companion joins GROUP_MonitorHumanForm, whose
# OverwriteSpeakerUuid is vanilla Raphael, and the re-keyed bank is left out of the pak (build_v0_2.ps1 -Variant S1b).
VARIANT = os.environ.get("RJTP_VARIANT", "")
if VARIANT == "S1b":
    speaker_groups.append("ed2660af-c4e2-0ce0-43e8-29dd7c0ab23a")  # GROUP_MonitorHumanForm
# v0.2: base visual = the Wardrobe visual (research 15 section 1.5), so equipment shows.
#  * PortraitVisualResourceID = vanilla dc5589d3 keeps his suited portrait. The field exists on vanilla globals
#    (globals/Gustav_Globals_WLD_Main_A.lsx:9913) and WW Aylin's global uses it the same way (AylinGlobal.lsx:28).
#    Whether the party portrait follows it or the pre-rendered Icon/GeneratePortrait is UNKNOWN (test W5).
#  * EquipmentRace stated explicitly (Human Male, as inherited from BASE_Humans_Male, Shared_RT.lsx:502141), as WW
#    Aylin's global does (AylinGlobal.lsx:14).
#  * Equipment stays EQP_Unarmed: PROC_RJTP_Dress creates the suit items (review 17 N6).
write(os.path.join(MODS, "Globals", "WLD_Main_A", "Characters", "RJTP_Raphael.lsx"), f"""<?xml version="1.0" encoding="utf-8"?>
<save>
	<version major="4" minor="0" revision="9" build="328" />
	<region id="Templates">
		<node id="Templates">
			<children>
				<node id="GameObjects">
					<attribute id="Archetype" type="FixedString" value="mage" />
					<attribute id="CharacterVisualResourceID" type="FixedString" value="{ids['VISUAL_WARDROBE']}" />
					<attribute id="DisplayName" type="TranslatedString" handle="{RAPHAEL_NAME_HANDLE}" version="1" />
					<attribute id="Equipment" type="FixedString" value="EQP_Unarmed" />
					<attribute id="EquipmentRace" type="guid" value="{HUMAN_MALE_RACE_EQ}" />
					<attribute id="Faction" type="guid" value="{ids['FACTION_NPC']}" />
					<attribute id="Flag" type="int32" value="1" />
					<attribute id="GeneratePortrait" type="LSString" value="Icon_Raphael_Human" />
					<attribute id="Icon" type="FixedString" value="{RAPHAEL_ICON}" />
					<attribute id="IsGlobal" type="bool" value="True" />
					<attribute id="IsLootable" type="bool" value="False" />
					<attribute id="LevelName" type="FixedString" value="WLD_Main_A" />
					<attribute id="MapKey" type="FixedString" value="{COMP}" />
					<attribute id="Name" type="LSString" value="S_RJTP_Raphael" />
					<attribute id="PortraitVisualResourceID" type="FixedString" value="{RAPHAEL_VISUAL}" />
					<attribute id="Race" type="guid" value="{HUMAN_RACE}" />
					<attribute id="SoftBodyCollisionTemplate" type="FixedString" value="e96eed75-850b-4497-b077-a8f62f731bf3" />
					<attribute id="SpellSet" type="FixedString" value="CommonPlayerActions" />
					<attribute id="Stats" type="FixedString" value="RJTP_Raphael" />
					<attribute id="TemplateName" type="FixedString" value="acd7060a-43bd-4dc9-b050-9d9b2cf7b7df" />
					<attribute id="Type" type="FixedString" value="character" />
					<attribute id="_OriginalFileVersion_" type="int64" value="144537400540922056" />
					<children>
						<node id="LayerList">
							<children>
								<node id="Layers">
									<children>
										<node id="Object">
											<attribute id="MapKey" type="FixedString" value="WLD_Main_A" />
											<children>{guid_node("Layer", ["303db700-f9db-a9ea-293a-3af3066f58b1", "28b53b44-9a9b-974d-0876-6d29aab9d9c9"])}
											</children>
										</node>
									</children>
								</node>
							</children>
						</node>
						<node id="LocomotionParams" />
						<node id="SpeakerGroupList">
							<children>{guid_node("SpeakerGroup", speaker_groups)}
							</children>
						</node>
						<node id="Tags">
							<children>{guid_node("Tag", tags)}
							</children>
						</node>
						<node id="Transform">
							<attribute id="Position" type="fvec3" value="-298.43454 24.10363 120.92958" />
							<attribute id="RotationQuat" type="fvec4" value="0 -0.8170171 0 0.5766135" />
							<attribute id="Scale" type="float" value="1" />
						</node>
					</children>
				</node>
			</children>
		</node>
	</region>
</save>
""")

# ---------------------------------------------------------------- voice metadata: Raphael's, re-keyed to the companion
src_vm = open(os.path.join(REF, "voicemeta", "raphael_f65becd6.lsx"), encoding="utf-8").read()
assert src_vm.count('value="f65becd6-5cd7-4c88-b85e-6dd06b60f7b8"') == 1
vm = src_vm.replace('value="f65becd6-5cd7-4c88-b85e-6dd06b60f7b8"', f'value="{COMP}"')
write(os.path.join(MODS, "Localization", "English", "Soundbanks", COMP.replace("-", "") + ".lsx"), vm)

# ---------------------------------------------------------------- Origins / Voices
write(os.path.join(PUB, "Origins", "Origins.lsx"), f"""<?xml version="1.0" encoding="utf-8"?>
<save>
  <version major="4" minor="0" revision="9" build="328" />
  <region id="Origins">
    <node id="root">
      <children>
        <node id="Origin">
          <attribute id="AppearanceLocked" type="bool" value="true" />
          <attribute id="AvailableInCharacterCreation" type="uint8" value="2" />
          <attribute id="BackgroundUUID" type="guid" value="{BACKGROUND}" />
          <attribute id="BodyShape" type="uint8" value="0" />
          <attribute id="BodyType" type="uint8" value="0" />
          <attribute id="ClassUUID" type="guid" value="{WARLOCK}" />
          <attribute id="DisplayName" type="TranslatedString" handle="{RAPHAEL_NAME_HANDLE}" version="1" />
          <attribute id="GlobalTemplate" type="guid" value="{COMP}" />
          <attribute id="Identity" type="uint8" value="1" />
          <attribute id="LockClass" type="bool" value="false" />
          <attribute id="LockRace" type="bool" value="true" />
          <attribute id="Name" type="FixedString" value="RJTP_Raphael" />
          <attribute id="Passives" type="LSString" value="DeathSavingThrows" />
          <attribute id="RaceUUID" type="guid" value="{HUMAN_RACE}" />
          <attribute id="SubClassUUID" type="guid" value="{WARLOCK_SUB}" />
          <attribute id="UUID" type="guid" value="{ids['ORIGIN']}" />
          <attribute id="Unique" type="bool" value="true" />
          <attribute id="VoiceTableUUID" type="guid" value="{VOICE_TABLE}" />
          <children>
            <node id="ReallyTags">
              <attribute id="Object" type="guid" value="{ids['TAG_REALLY']}" />
            </node>
          </children>
        </node>
      </children>
    </node>
  </region>
</save>
""")
write(os.path.join(PUB, "Voices", "Voices.lsx"), f"""<?xml version="1.0" encoding="UTF-8"?>
<save>
    <version major="4" minor="8" revision="0" build="500"/>
    <region id="Voices">
        <node id="root">
            <children>
                <node id="Voice">
                    <attribute id="BodyType" type="uint8" value="0"/>
                    <attribute id="DisplayName" type="TranslatedString" handle="{H_VOICE}" version="1"/>
                    <attribute id="SpeakerUUID" type="guid" value="{VOICE_SPEAKER}"/>
                    <attribute id="TableUUID" type="guid" value="{VOICE_TABLE}"/>
                    <attribute id="UUID" type="guid" value="{ids['VOICE']}"/>
                </node>
            </children>
        </node>
    </region>
</save>
""")

# ---------------------------------------------------------------- factions
write(os.path.join(PUB, "Factions", "Factions.lsx"), f"""<?xml version="1.0" encoding="UTF-8"?>
<save>
    <version major="4" minor="7" revision="1" build="3"/>
    <region id="FactionContainer">
        <node id="root">
            <children>
                <node id="Faction">
                    <attribute id="Faction" type="FixedString" value="RJTP_RaphaelNPC"/>
                    <attribute id="ParentGuid" type="guid" value="00000000-0000-0000-0000-000000000000"/>
                    <attribute id="UUID" type="guid" value="{ids['FACTION_NPC']}"/>
                </node>
                <node id="Faction">
                    <attribute id="Faction" type="FixedString" value="RJTP_RaphaelCompanion"/>
                    <attribute id="ParentGuid" type="guid" value="{HERO_FACTION}"/>
                    <attribute id="UUID" type="guid" value="{ids['FACTION']}"/>
                </node>
            </children>
        </node>
    </region>
</save>
""")
rel = "".join(f"""
                        <node id="Relation">
                            <attribute id="Source" type="guid" value="{ids['FACTION_NPC']}"/>
                            <attribute id="Target" type="guid" value="{t}"/>
                            <attribute id="Value" type="int32" value="{v}"/>
                        </node>""" for t, v in ((EVIL_FACTION, 50), (GOOD_FACTION, 50), (HERO_FACTION, 50)))
write(os.path.join(PUB, "Factions", "Relations.lsx"), f"""<?xml version="1.0" encoding="UTF-8"?>
<save>
    <version major="4" minor="7" revision="1" build="3"/>
    <region id="FactionManager">
        <node id="root">
            <children>
                <node id="Relations">
                    <children>{rel}
                    </children>
                </node>
            </children>
        </node>
    </region>
</save>
""")

# ---------------------------------------------------------------- flags and tags
FLAGS = [  # (id key, Name, Usage, description)   Usage 5 = global, 4 = object (matches WW_AIJP equivalents)
    ("FLAG_IsInParty", "RJTP_ORI_Raphael_State_IsInParty", 5, "Raphael (RJTP) is in the party."),
    ("FLAG_PartOfTheTeam", "RJTP_GLO_Origin_PartOfTheTeam_Raphael", 5, "Raphael (RJTP) is part of the team."),
    ("FLAG_Avatar", "RJTP_GLO_Origin_Avatar_Raphael", 5, "Raphael (RJTP) is an avatar (never used)."),
    ("FLAG_ControlledByUser", "RJTP_ORI_Raphael_ControlledByUser", 4, "Raphael (RJTP) is controlled by a user."),
    ("FLAG_KickCompanion", "RJTP_ORI_Raphael_Event_KickCompanion", 5, "Kick Raphael (RJTP) from the party."),
    ("FLAG_CanBeKicked", "RJTP_ORI_Raphael_State_CanBeKicked", 4, "Raphael (RJTP) can be kicked."),
    ("FLAG_CampNPC", "RJTP_RAPHAEL", 5, "Camp flag for Raphael (RJTP)."),
    ("FLAG_CampAvatar", "RJTP_RAPHAELAVATAR", 5, "Camp flag for Raphael (RJTP) as avatar."),
    ("FLAG_CampCompanion", "RJTP_RAPHAELCOMPANION", 5, "Camp flag for Raphael (RJTP) as companion."),
    ("FLAG_CampParty", "RJTP_RAPHAELPARTY", 5, "Camp flag for Raphael (RJTP) in party."),
    ("FLAG_CampCamp", "RJTP_RAPHAELCAMP", 5, "Camp flag for Raphael (RJTP) in camp."),
    ("FLAG_JergalCanRes", "RJTP_CAMP_Jergal_State_CanResurrectRaphael", 5, "Withers can resurrect Raphael (RJTP)."),
    ("FLAG_JergalWillRes", "RJTP_CAMP_Jergal_State_WillResurrectRaphael", 5, "Withers will resurrect Raphael (RJTP)."),
    ("FLAG_InclusionStart", "RJTP_ORI_Inclusion_Raphael", 4, "Inclusion flag for Raphael (RJTP)."),
    ("FLAG_InclusionEnd", "RJTP_ORI_Inclusion_End_Raphael", 4, "Inclusion end flag for Raphael (RJTP)."),
]
for key, name, usage, desc in FLAGS:
    write(os.path.join(PUB, "Flags", ids[key] + ".lsx"), f"""<?xml version="1.0" encoding="utf-8"?>
<save>
	<version major="4" minor="8" revision="0" build="500" />
	<region id="Flags">
		<node id="Flags">
			<attribute id="UUID" type="guid" value="{ids[key]}" />
			<attribute id="Name" type="FixedString" value="{name}" />
			<attribute id="Description" type="LSString" value="{html.escape(desc)}" />
			<attribute id="Usage" type="uint8" value="{usage}" />
		</node>
	</region>
</save>
""")
json.dump({ids[k]: n for k, n, _, _ in FLAGS}, open(os.path.join(SRC, "flag_names.json"), "w"), indent=1)

def tag_file(uid, name, cats, disp):
    catx = "".join(f"""
						<node id="Category">
							<attribute id="Name" type="LSString" value="{c}" />
						</node>""" for c in cats)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<save>
	<version major="4" minor="8" revision="0" build="500" />
	<region id="Tags">
		<node id="Tags">
			<attribute id="UUID" type="guid" value="{uid}" />
			<attribute id="Name" type="FixedString" value="{name}" />
			<attribute id="DisplayName" type="TranslatedString" handle="{disp}" version="1" />
			<attribute id="DisplayDescription" type="TranslatedString" handle="ls::TranslatedStringRepository::s_HandleUnknown" version="0" />
			<attribute id="Icon" type="FixedString" value="" />
			<attribute id="Description" type="LSString" value="" />
			<children>
				<node id="Categories">
					<children>{catx}
					</children>
				</node>
				<node id="Properties" />
			</children>
		</node>
	</region>
</save>
"""
H_TAG = loca(handle("tag_raphael"), "Raphael")
write(os.path.join(PUB, "Tags", ids["TAG_ORIGIN"] + ".lsx"),
      tag_file(ids["TAG_ORIGIN"], "RJTP_Raphael", ["Code", "Dialog", "Origin", "DialogHidden", "CharacterSheet"], H_TAG))
write(os.path.join(PUB, "Tags", ids["TAG_REALLY"] + ".lsx"),
      tag_file(ids["TAG_REALLY"], "RJTP_REALLY_RAPHAEL", ["Code", "Dialog", "DialogHidden"], H_TAG))

# ================================================================ v0.2 data layer (plan PLAN_v0_2.md 4, 7, 9, 10)
# Plan draft 3.1 supersedes research 12 section 5.1: NO keeper passives, NO _ON BOOST statuses; the form spells are
# pure triggers (empty SpellProperties) and Osiris applies the statuses on CastedSpell (RJTP_Forms.txt).

# ---- loca
H_CF_NAME = loca(handle("changeform_name"), "Infernal Guise")
H_CF_DESC = loca(handle("changeform_desc"),
    "Change Raphael's appearance. His abilities, statistics and equipment stay exactly as they are.")
H_F_WARDROBE = loca(handle("form_wardrobe_name"), "Wardrobe")
H_F_WARDROBE_D = loca(handle("form_wardrobe_desc"),
    "Raphael appears as he is dressed: in his own suit, or in whatever armour and clothing you give him.")
H_F_SIGNATURE = loca(handle("form_signature_name"), "Signature Look")
H_F_SIGNATURE_D = loca(handle("form_signature_desc"),
    "Raphael takes on his signature appearance, immaculate suit and all. His equipment still works but is not shown.")
H_F_DEVIL = loca(handle("form_devil_name"), "Devil Form")
H_F_DEVIL_D = loca(handle("form_devil_desc"),
    "Raphael reveals his true infernal form. His equipment still works but is not shown.")
H_F_ASC = loca(handle("form_ascended_name"), "Fiendish Ascension")
H_F_ASC_D = loca(handle("form_ascended_desc"),
    "Only in combat. Raphael becomes the Ascended Fiend until the fight ends. This form never appears in dialogues "
    "or cutscenes. Appearance only: his abilities do not change.")
H_F_ASCX2 = loca(handle("form_ascendedx2_name"), "Fiendish Ascension (Towering Devil)")
H_F_ASCX2_D = loca(handle("form_ascendedx2_desc"),
    "Only in combat. Raphael's devil form at twice its size, until the fight ends. Appearance only.")
H_S_WARDROBE = loca(handle("status_wardrobe_name"), "Wardrobe Look")
H_S_WARDROBE_D = loca(handle("status_wardrobe_desc"), "Raphael appears as he is dressed.")
H_S_SUIT = loca(handle("status_suit_name"), "Signature Look")
H_S_SUIT_D = loca(handle("status_suit_desc"), "Raphael wears his signature appearance. Equipment is not shown.")
H_S_DEVIL = loca(handle("status_devil_name"), "Devil Form")
H_S_DEVIL_D = loca(handle("status_devil_desc"), "Raphael shows his true infernal form. Equipment is not shown.")
H_S_ASC = loca(handle("status_ascended_name"), "Ascended Fiend")
H_S_ASC_D = loca(handle("status_ascended_desc"), "Raphael towers as the Ascended Fiend. Ends when combat ends.")
H_S_ASCX2 = loca(handle("status_ascendedx2_name"), "Ascended Fiend (Towering Devil)")
H_S_ASCX2_D = loca(handle("status_ascendedx2_desc"), "Raphael towers in devil form. Ends when combat ends.")
H_I_SUIT = loca(handle("item_suit_name"), "Raphael's Suit")
H_I_SUIT_D = loca(handle("item_suit_desc"),
    "An impeccably tailored doublet and trousers. It offers no protection beyond excellent taste.")
H_I_SHOES = loca(handle("item_shoes_name"), "Raphael's Shoes")
H_I_SHOES_D = loca(handle("item_shoes_desc"), "Polished leather, never scuffed, whatever the road.")
H_I_SUITC = loca(handle("item_suit_camp_name"), "Raphael's Suit (Camp Clothes)")
H_I_SUITC_D = loca(handle("item_suit_camp_desc"), "The same immaculate suit, worn at camp and on special occasions.")
H_I_SHOESC = loca(handle("item_shoes_camp_name"), "Raphael's Shoes (Camp Clothes)")
H_I_SHOESC_D = loca(handle("item_shoes_camp_desc"), "The same polished shoes, worn at camp.")
H_DBG_CURE = loca(handle("dbg_cure"), "RJTP TEST: Run the House of Hope alarm cure")
H_DBG_V02 = loca(handle("dbg_v02status"), "RJTP TEST: Show v0.2 state (cure, form, version)")
H_DBG_VANITY = loca(handle("dbg_vanity"), "RJTP TEST: Toggle Raphael's camp clothes")
H_DBG_UNINSTALL = loca(handle("dbg_uninstall"), "RJTP TEST: Uninstall step (clear forms, withdraw Raphael)")
H_DBG_DIALOGS = loca(handle("dbg_dialogs"), "RJTP TEST: Toggle Raphael's own dialogs (spike D0, no timelines yet)")
H_DBG_VOICE1A = loca(handle("dbg_voice_s1a"), "RJTP TEST: Voice test S1a (his own dialog slot)")
H_DBG_VOICE1B = loca(handle("dbg_voice_s1b"), "RJTP TEST: Voice test S1b (speaker-group route; S1b build only)")
# v0.3a (PLAN_v0_3a_banter_2026-10-06.md): barks, two-sided banter, camp conversation experiment
H_DBG_BARK = loca(handle("dbg_bark"), "RJTP TEST: Next bark (his solo lines, one per cast)")
H_DBG_BANTER = loca(handle("dbg_banter"), "RJTP TEST: Next banter (Raphael and a companion in your party)")
H_DBG_NATBANTER = loca(handle("dbg_natural_banter"), "RJTP TEST: Natural banter on/off (only after the banter test works)")
H_DBG_CAMPTALK = loca(handle("dbg_camptalk"), "RJTP TEST: Start his camp conversation (timeline experiment)")
# v0.3d (RJTP_TestHoH.txt)
H_DBG_GOHOH = loca(handle("dbg_gohoh"), "RJTP TEST: Go to the House of Hope (sets up the offer)")
H_DBG_STAGETHEFT = loca(handle("dbg_stagetheft"), "RJTP TEST: Stage an Archive theft (cast at the House of Hope exit portal)")

# ---- spells: container + pure-trigger children, Disguise Self pattern
# Container fields copied from Shout_DisguiseSelf (stats Shared Spell_Shout.txt:758-782) minus its spell costs and
# IsSpell/verbal/somatic flags (a cosmetic, free ability). Children follow Shout_DisguiseSelf_Tiefling_Male
# (:784-794): using the container, SpellContainerID = container, ContainerSpells "". SpellProperties are EMPTY on
# purpose: RJTP_Forms.txt CastedSpell rules (DB_RJTP_FormSpell / DB_RJTP_AscendSpell) do the work.
DISGUISE_ANIM = ("dd86aa43-8189-4d9f-9a5c-454b5fe4a197,,;,,;bcc3b0d9-f04f-4448-aab0-e0ad641167cc,,;"
                 "bf924cc6-8b39-4c3b-b1c0-eda264cf6150,,;cc5b0caf-3ed1-4711-a50d-11dc3f1fdc6a,,;,,;"
                 "1715b877-4512-472e-9bd0-fd568a112e90,,;,,;,,")   # Spell_Shout.txt:775
FORM_CHILDREN = [  # (spell, icon, name, desc, extra lines)
    ("Shout_RJTP_Form_Wardrobe", "Spell_Illusion_DisguiseSelf_Human_Male", H_F_WARDROBE, H_F_WARDROBE_D, []),
    ("Shout_RJTP_Form_Signature", "Spell_Illusion_DisguiseSelf_Human_Male", H_F_SIGNATURE, H_F_SIGNATURE_D, []),
    ("Shout_RJTP_Form_Devil", "Spell_Illusion_DisguiseSelf_Tiefling_Male", H_F_DEVIL, H_F_DEVIL_D, []),
    # Combat only: Requirements "Combat" as Shout_ActionSurge (Shared Spell_Shout.txt:20); a bonus action (research
    # 12 section 5.1); sounds from Shout_LOW_Raphael_Transform (GustavDev Spell_Shout.txt:1486-1487).
    ("Shout_RJTP_Form_Ascended", "Spell_Raphael_FiendishAscension", H_F_ASC, H_F_ASC_D,
     ['data "Requirements" "Combat"', 'data "UseCosts" "BonusActionPoint:1"',
      'data "CastSound" "CrSpell_Cast_Raphael_Transform"', 'data "TargetSound" "CrSpell_Impact_Raphael_Transform"']),
    ("Shout_RJTP_Form_AscendedX2", "Spell_Raphael_FiendishAscension", H_F_ASCX2, H_F_ASCX2_D,
     ['data "Requirements" "Combat"', 'data "UseCosts" "BonusActionPoint:1"',
      'data "CastSound" "CrSpell_Cast_Raphael_Transform"', 'data "TargetSound" "CrSpell_Impact_Raphael_Transform"']),
]
DEBUG_V02 = [("Shout_RJTP_Debug_Cure", H_DBG_CURE), ("Shout_RJTP_Debug_V02Status", H_DBG_V02),
             ("Shout_RJTP_Debug_Uninstall", H_DBG_UNINSTALL),
             ("Shout_RJTP_Debug_Dialogs", H_DBG_DIALOGS), ("Shout_RJTP_Debug_VoiceS1a", H_DBG_VOICE1A),
             ("Shout_RJTP_Debug_VoiceS1b", H_DBG_VOICE1B),
             ("Shout_RJTP_Debug_Bark", H_DBG_BARK), ("Shout_RJTP_Debug_Banter", H_DBG_BANTER),
             ("Shout_RJTP_Debug_NaturalBanter", H_DBG_NATBANTER), ("Shout_RJTP_Debug_CampTalk", H_DBG_CAMPTALK),
             ("Shout_RJTP_Debug_GoHoH", H_DBG_GOHOH), ("Shout_RJTP_Debug_StageTheft", H_DBG_STAGETHEFT)]


def v02_spells():
    out = [f"""
new entry "Shout_RJTP_ChangeForm"
type "SpellData"
data "SpellType" "Shout"
data "ContainerSpells" "{';'.join(c[0] for c in FORM_CHILDREN)}"
data "AIFlags" "CanNotUse"
data "TargetConditions" "Self()"
data "Icon" "Spell_Illusion_DisguiseSelf"
data "DisplayName" "{H_CF_NAME};1"
data "Description" "{H_CF_DESC};1"
data "CastSound" "Spell_Cast_Utility_DisguiseSelf_L1to3"
data "TargetSound" "Spell_Impact_Utility_DisguiseSelf_L1to3"
data "CastTextEvent" "Cast"
data "UseCosts" ""
data "SpellAnimation" "{DISGUISE_ANIM}"
data "VerbalIntent" "Utility"
data "SpellFlags" "IsLinkedSpellContainer"
data "PrepareEffect" "9e7ec23c-4b13-4a88-b3d6-1df1782e4359"
data "CastEffect" "c33c578f-fc5c-4a9d-a961-78b7bfff73d7"
data "HitEffect" "ebcd0860-3695-4762-b9f5-4e441c4bf888"
"""]
    for name, icon, dn, desc, extra in FORM_CHILDREN:
        out.append(f"""
new entry "{name}"
type "SpellData"
data "SpellType" "Shout"
using "Shout_RJTP_ChangeForm"
data "SpellContainerID" "Shout_RJTP_ChangeForm"
data "ContainerSpells" ""
data "SpellProperties" ""
data "Icon" "{icon}"
data "DisplayName" "{dn};1"
data "Description" "{desc};1"
""" + "".join(x + "\n" for x in extra))
    for name, dn in DEBUG_V02:   # same pattern as the v0.1 debug shouts above
        out.append(f"""
new entry "{name}"
type "SpellData"
data "SpellType" "Shout"
data "Icon" "Status_Surrendered"
data "DisplayName" "{dn};1"
data "SpellFlags" "ImmediateCast;Temporary"
""")
    return "".join(out)


# ---- statuses: POLYMORPHED onto a template with the mod's display-only rule (research 12 section 2.4)
# All share StackId RJTP_FORM_VISUAL, equal StackPriority and StackType "Overwrite" (valuelist StatusStackType,
# Structure/Base/ValueLists.txt:943-949; Overwrite in use e.g. Shared Status_BOOST.txt:1379) so a new form replaces
# the old one (plan 4.1 [m3]). No StatusGroups: not SG_Polymorph (camp-night drop, GLO_Camp.txt:844-847), not
# SG_RemoveOnRespec, not SG_DropForNonMutingDialog. Flag names checked against valuelist StatusPropertyFlags.
PERSIST_FLAGS = "IgnoreResting;DisableOverhead;DisableCombatlog;DisablePortraitIndicator"
FORM_STATUSES = [  # (name, template, rule, name handle, desc handle, icon, extra lines)
    ("RJTP_FORM_WARDROBE", ids["TPL_WARDROBEFORM"], ids["RULE_FORM_VISUAL"], H_S_WARDROBE, H_S_WARDROBE_D,
     "Spell_Illusion_DisguiseSelf_Human_Male", [f'data "StatusPropertyFlags" "{PERSIST_FLAGS}"']),
    ("RJTP_FORM_SUIT", ids["TPL_SUITFORM"], ids["RULE_FORM_VISUAL"], H_S_SUIT, H_S_SUIT_D,
     "Spell_Illusion_DisguiseSelf_Human_Male", [f'data "StatusPropertyFlags" "{PERSIST_FLAGS}"']),
    ("RJTP_FORM_DEVIL", DEVIL_FORM_TPL, ids["RULE_FORM_VISUAL"], H_S_DEVIL, H_S_DEVIL_D,
     "Spell_Illusion_DisguiseSelf_Tiefling_Male", [f'data "StatusPropertyFlags" "{PERSIST_FLAGS}"']),
    # Combat-only twins of GASEOUSFORM_BLINK (SharedDev Status_POLYMORPHED.txt:305,308): removed when not in combat,
    # re-checked on apply (research 12 section 5.1). SoundStop from LOW_RAPHAEL_MONSTER_FORM (GustavDev :700).
    ("RJTP_FORM_ASCENDED", ASCENDED_TPL, ids["RULE_FORM_VISUAL"], H_S_ASC, H_S_ASC_D,
     "Spell_Raphael_FiendishAscension",
     ['data "StatusPropertyFlags" "DisableOverhead;DisableCombatlog"', 'data "RemoveConditions" "not Combat()"',
      'data "RemoveEvents" "OnApply;OnTurn;OnCombatEnded"', 'data "SoundStop" "CrSpell_Impact_Raphael_TransformEnd"']),
    ("RJTP_FORM_ASCENDED_X2", BEAST_X2_TPL, ids["RULE_FORM_VISUAL_SCALED"], H_S_ASCX2, H_S_ASCX2_D,
     "Spell_Raphael_FiendishAscension",
     ['data "StatusPropertyFlags" "DisableOverhead;DisableCombatlog"', 'data "RemoveConditions" "not Combat()"',
      'data "RemoveEvents" "OnApply;OnTurn;OnCombatEnded"', 'data "SoundStop" "CrSpell_Impact_Raphael_TransformEnd"']),
]


def v02_statuses():
    out = []
    for name, tpl, rule, dn, desc, icon, extra in FORM_STATUSES:
        out.append(f"""new entry "{name}"
type "StatusData"
data "StatusType" "POLYMORPHED"
data "DisplayName" "{dn};1"
data "Description" "{desc};1"
data "Icon" "{icon}"
data "StackId" "RJTP_FORM_VISUAL"
data "StackPriority" "1"
data "StackType" "Overwrite"
""" + "".join(x + "\n" for x in extra) + f"""data "TemplateID" "{tpl}"
data "Rules" "{rule}"
""")
    return "\n".join(out)


# ---- armour: the suit from the three vanilla meshes, as an armour-slot pair and a camp pair (plan 4.2; review 16
# B2; review 17 (d)). Bases (stats Shared Armor.txt): ARM_Robe_Body :203 (Breast via _Body :4, AC 10 = the unarmoured
# baseline, i.e. no armour bonus; ArmorType None), ARM_Shoes :725 (Boots via _Foot :528, ArmorType Cloth),
# ARM_Camp_Body :1661 (VanityBody), ARM_Camp_Shoes :2078 (VanityBoots).
SUIT_ITEMS = [  # (stats/RT name, id key, stats base, RT parent (MapKey, where), name, desc, equipment builder)
    ("RJTP_ARM_RaphaelSuit", "ITEM_SUIT", "ARM_Robe_Body",
     "168b9099-19f5-44e4-b55c-e64ceb60b71f",   # ARM_Robe (Stats ARM_Robe_Body), Shared_RT.lsx:61474
     H_I_SUIT, H_I_SUIT_D, "suit"),
    ("RJTP_ARM_RaphaelShoes", "ITEM_SHOES", "ARM_Shoes",
     "c1f9f7af-cdb2-49f6-8459-521f2b9263cb",   # ARM_Boots_Leather_C (maps a9656a45), SharedDev_RT.lsx:217232-217233
     H_I_SHOES, H_I_SHOES_D, "boots"),
    ("RJTP_ARM_RaphaelSuit_Camp", "ITEM_SUIT_CAMP", "ARM_Camp_Body",
     "f369f4fa-2da7-4693-a147-16cfaf02bca5",   # ARM_Camp_Body, Shared_RT.lsx:705740
     H_I_SUITC, H_I_SUITC_D, "suit"),
    ("RJTP_ARM_RaphaelShoes_Camp", "ITEM_SHOES_CAMP", "ARM_Camp_Shoes",
     "6bb7a595-7646-48a9-9c44-d39f16c1c5cb",   # ARM_Camp_Shoes, Shared_RT.lsx:313301
     H_I_SHOESC, H_I_SHOESC_D, "boots"),
]


def v02_armor():
    return "\n".join(f"""new entry "{name}"
type "Armor"
using "{base}"
data "RootTemplate" "{ids[key]}"
""" for name, key, base, _, _, _, _ in SUIT_ITEMS)


# ---------------------------------------------------------------- stats
STATS = os.path.join(PUB, "Stats", "Generated", "Data")
write(os.path.join(STATS, "Character.txt"), f"""new entry "RJTP_Raphael"
type "Character"
using "POC_Player_Warlock"
data "Passives" "ShortResting;NonLethal;WeaponThrow;Perform;AttackOfOpportunity;DarknessRules;CombatStartAttack;DevilsSight;RJTP_Raphael_Infernal"
""")
write(os.path.join(STATS, "Passive.txt"), f"""new entry "RJTP_Raphael_Infernal"
type "PassiveData"
data "DisplayName" "{H_PASSIVE_NAME};1"
data "Description" "{H_PASSIVE_DESC};1"
data "Icon" "PassiveFeature_DevilsSight"
data "Properties" "Highlighted"
data "Boosts" "UnlockSpell(Projectile_RJTP_IgnitingSpark);UnlockSpell(Zone_RJTP_FlamesOfAvernus);UnlockSpell(Shout_RJTP_ChangeForm);Resistance(Fire,Resistant);Proficiency(HeavyArmor)"

new entry "RJTP_InfernalCharge_Holder"
type "PassiveData"
data "Properties" "IsHidden"
data "Boosts" "ActionResource(RJTP_InfernalCharge,1,0)"

new entry "RJTP_Trait_SoulReaper"
type "PassiveData"
data "DisplayName" "{H_T_REAPER};1"
data "Description" "{H_T_REAPER_D};1"
data "Icon" "statIcons_WildMagic_Memphit"
data "Properties" "Highlighted;OncePerShortRest"
data "StatsFunctorContext" "OnDamage"
data "Conditions" "IsKillingBlow() and Enemy() and not Tagged('UNDEAD') and not Tagged('CONSTRUCT') and not HasActionResource('RJTP_InfernalCharge',1,0,false,false,context.Source)"
data "StatsFunctors" "RestoreResource(SELF,RJTP_InfernalCharge,1,0)"

new entry "RJTP_Trait_InevitableResolve"
type "PassiveData"
data "DisplayName" "{H_T_RESOLVE};1"
data "Description" "{H_T_RESOLVE_D};1"
data "Icon" "Action_Monster_Cambion_FiendishCharm"
data "Properties" "Highlighted;OncePerShortRest"
data "StatsFunctorContext" "OnStatusApplied"
data "Conditions" "(StatusId('PLANAR_BINDING') or StatusId('HOLD_MONSTER') or StatusId('TURN_THE_UNHOLY') or StatusId('TURNED') or StatusId('IRRESISTIBLE_DANCE') or StatusHasStatusGroup(context.StatusId, 'SG_Dominated') or StatusHasStatusGroup(context.StatusId, 'SG_Incapacitated') or StatusHasStatusGroup(context.StatusId, 'SG_Restrained')) and not StatusHasStatusGroup(context.StatusId, 'SG_Unconscious') and HasPassive('RJTP_Trait_InevitableResolve', context.Target) and not HasStatus('LOW_RAPHAEL_WILLPOWER', context.Target) and Combat()"
data "StatsFunctors" "ApplyStatus(SELF,LOW_RAPHAEL_WILLPOWER,100,1)"

new entry "RJTP_Trait_FiendishBlessing"
type "PassiveData"
using "FiendishBlessing"
data "DisplayName" "{H_T_FIENDISH};1"
data "Description" "{H_T_FIENDISH_D};1"
data "Properties" "Highlighted"

new entry "RJTP_Trait_MagicResistance"
type "PassiveData"
using "MagicResistance"
data "Properties" "Highlighted"
""")
write(os.path.join(STATS, "Spell_Projectile.txt"), f"""new entry "Projectile_RJTP_IgnitingSpark"
type "SpellData"
data "SpellType" "Projectile"
using "Projectile_FireBolt"
data "SpellSuccess" "DealDamage(LevelMapValue(D10Cantrip),Fire,Magical);ApplyStatus(BURNING,100,2)"
data "DisplayName" "hd60d072dg1f2fg45baga914g9fe2fc671a15;4"
data "Description" "{H_SPARK_DESC};1"
data "TooltipStatusApply" "ApplyStatus(BURNING,100,2)"
""")
write(os.path.join(STATS, "Spell_Zone.txt"), f"""new entry "Zone_RJTP_FlamesOfAvernus"
type "SpellData"
data "SpellType" "Zone"
using "Zone_LOW_Raphael_LanguishingFire"
data "Level" "1"
data "UseCosts" "ActionPoint:1;RJTP_InfernalCharge:1"
data "Cooldown" "None"
data "SpellRoll" "not SavingThrow(Ability.Dexterity, SourceSpellDC())"
data "SpellSuccess" "DealDamage(4d6,Fire,Magical)"
data "SpellFail" "DealDamage(4d6/2,Fire,Magical)"
data "DescriptionParams" "DealDamage(4d6, Fire)"
data "TooltipDamageList" "DealDamage(4d6, Fire)"
data "RequirementConditions" ""
data "Description" "{H_AVERNUS_DESC};1"
""")
write(os.path.join(STATS, "Spell_Shout.txt"), f"""new entry "Shout_RJTP_Debug_Recruit"
type "SpellData"
data "SpellType" "Shout"
data "Icon" "Status_Surrendered"
data "DisplayName" "{H_DBG_RECRUIT};1"
data "SpellFlags" "ImmediateCast;Temporary"

new entry "Shout_RJTP_Debug_Summon"
type "SpellData"
data "SpellType" "Shout"
data "Icon" "Status_Surrendered"
data "DisplayName" "{H_DBG_SUMMON};1"
data "SpellFlags" "ImmediateCast;Temporary"

new entry "Shout_RJTP_Debug_Status"
type "SpellData"
data "SpellType" "Shout"
data "Icon" "Status_Surrendered"
data "DisplayName" "{H_DBG_STATUS};1"
data "SpellFlags" "ImmediateCast;Temporary"
""" + v02_spells())
write(os.path.join(STATS, "Status_POLYMORPHED.txt"), v02_statuses())
write(os.path.join(STATS, "Armor.txt"), v02_armor())

# ---- guard against transcription errors: the copied vanilla values must be verbatim in the vanilla files
VSTATS = os.path.join(REF, "stats", "Shared", "Public", "Shared", "Stats", "Generated", "Data")
_ss = open(os.path.join(VSTATS, "Spell_Shout.txt"), encoding="utf-8").read()
for frag in (f'data "SpellAnimation" "{DISGUISE_ANIM}"', 'data "PrepareEffect" "9e7ec23c-4b13-4a88-b3d6-1df1782e4359"',
             'data "CastEffect" "c33c578f-fc5c-4a9d-a961-78b7bfff73d7"', 'data "HitEffect" "ebcd0860-3695-4762-b9f5-4e441c4bf888"',
             'data "CastSound" "Spell_Cast_Utility_DisguiseSelf_L1to3"', 'data "Requirements" "Combat"'):
    assert frag in _ss, "not verbatim in vanilla Spell_Shout.txt: " + frag


# ---------------------------------------------------------------- LSX helpers (v0.2)
def lsx_node(el, depth):
    """Serialize an ElementTree LSX <node> element with vanilla-style tab indentation."""
    pad = "\t" * depth
    attrs = "".join(f' {k}="{html.escape(v, quote=True)}"' for k, v in el.attrib.items())
    kids = list(el)
    if not kids:
        return f"{pad}<{el.tag}{attrs} />\n"
    s = f"{pad}<{el.tag}{attrs}>\n"
    for k in kids:
        s += lsx_node(k, depth + 1)
    return s + f"{pad}</{el.tag}>\n"


def load_lsx(path):
    return ET.parse(path).getroot()


def attr(el, aid):
    for a in el.findall("attribute"):
        if a.get("id") == aid:
            return a
    return None


def find_by_attr(root, node_id, aid, value):
    for n in root.iter("node"):
        if n.get("id") == node_id:
            a = attr(n, aid)
            if a is not None and a.get("value") == value:
                return n
    raise KeyError(f"{node_id} with {aid}={value} not found")


def save_region(path, region, inner, version='<version major="4" minor="0" revision="9" build="328" />'):
    write(path, f"""<?xml version="1.0" encoding="utf-8"?>
<save>
	{version}
	<region id="{region}">
		<node id="{region}">
			<children>
{inner}			</children>
		</node>
	</region>
</save>
""")


# ---------------------------------------------------------------- Shapeshift Rulebook (research 12 section 2.4)
# Vanilla ships Public/<module>/Shapeshift/Rulebook.lsx as .lsx (gustav_list.txt: Public/GustavDev/Shapeshift/
# Rulebook.lsx); WW Aylin ships Public/<mod>/Shapeshift/Rulebook.lsx the same way. Every attribute name below occurs
# in vanilla rulebooks with type bool (_vanilla_ref/forms/*/Public/*/Shapeshift/Rulebook.lsx). Closest vanilla twin:
# WyllDevil 884b16b1 (GustavDev Rulebook.lsx:1234-1245: ApplyVisual, ApplyVisualInCC, ChangeIcon, FootstepsType,
# Scale 4). Ours: display only; RetainDisplayName + IgnoreCustomLooks as research 12 section 2.4; everything that
# would touch gameplay (race, body type, tags, spells, AI, equipment slots, level-up, AC) is explicitly false and
# there are no AbilityChanges / Hp / Weight nodes. The Scaled variant adds Scale type 4 (take the template's scale),
# the WyllDevil encoding, for QUEST_Monitor_BeastForm (Scale 2).
RULE_TRUE = ["ApplyVisual", "ChangeIcon", "FootstepsType", "IgnoreCustomLooks", "RetainDisplayName"]
RULE_FALSE = ["ApplySpellsFromTemplate", "ApplyTagsFromTemplate", "ApplyVisualInCC", "BaseACOverride", "BlockLevelUp",
              "ChangeAi", "ChangeBodyType", "ChangeRace", "DisableEquipmentSlots", "KillEntityAtZeroHP",
              "MuteEquipmentSound", "RemoveOldTags", "RemovePrevSpells", "UnarmedAbilityFromTemplate",
              "UseShapeshiftIdentity", "UseTemplateEquipmentSet", "WildShapeHotBar"]


def rule_xml(name, uid, scaled):
    flags = {**{k: "true" for k in RULE_TRUE}, **{k: "false" for k in RULE_FALSE}}
    a = "".join(f'\n                    <attribute id="{k}" type="bool" value="{flags[k]}"/>' for k in sorted(flags))
    kids = """
                    <children>
                        <node id="Scale">
                            <attribute id="type" type="uint8" value="4"/>
                        </node>
                    </children>""" if scaled else ""
    return f"""                <node id="Rule">{a}
                    <attribute id="RuleName" type="LSString" value="{name}"/>
                    <attribute id="UUID" type="guid" value="{uid}"/>{kids}
                </node>
"""


write(os.path.join(PUB, "Shapeshift", "Rulebook.lsx"), f"""<?xml version="1.0" encoding="UTF-8"?>
<save>
    <version major="4" minor="8" revision="0" build="500"/>
    <region id="Rulebook">
        <node id="root">
            <children>
{rule_xml("RJTP_Form_Visual", ids["RULE_FORM_VISUAL"], False)}{rule_xml("RJTP_Form_Visual_Scaled", ids["RULE_FORM_VISUAL_SCALED"], True)}            </children>
        </node>
    </region>
</save>
""")

# ---------------------------------------------------------------- CharacterVisual RJTP_Raphael_Wardrobe (research 15 1.5)
# A copy of vanilla dc5589d3 (keeps base fc86cc9a, body set 38cee76d, head, hair and every MaterialOverride), minus the
# three suit slots, plus the player modesty leaf and private parts (as Humans_Male_Player 40b6c0b8 has them),
# with ShowEquipmentVisuals True. Written as one bank file per resource under Content/[PAK]_CharacterVisuals/, as WW
# Mizora ships 5cc8d840 (Public/<mod>/Content/[PAK]_CharacterVisuals/5cc8d840-...lsf); the build converts to .lsf.
_cv = load_lsx(os.path.join(REF, "forms", "gustav", "Public", "Gustav", "Content", "[PAK]_CharacterVisuals", "_merged.lsx"))
wv = copy.deepcopy(find_by_attr(_cv, "Resource", "ID", RAPHAEL_VISUAL))
del _cv
attr(wv, "ID").set("value", ids["VISUAL_WARDROBE"])
attr(wv, "Name").set("value", "RJTP_Raphael_Wardrobe")
attr(wv, "ShowEquipmentVisuals").set("value", "True")
_ofv = attr(wv, "_OriginalFileVersion_")
if _ofv is not None:
    wv.remove(_ofv)
_kids = wv.find("children")
_removed = []
for s in [n for n in _kids if n.get("id") == "Slots"]:
    if attr(s, "VisualResource").get("value") in (SUIT_PANTS, SUIT_BOOTS, SUIT_DOUBLET):
        _removed.append(attr(s, "VisualResource").get("value"))
        _kids.remove(s)
assert sorted(_removed) == sorted([SUIT_PANTS, SUIT_BOOTS, SUIT_DOUBLET]), _removed
_slots_left = [(attr(s, "Slot").get("value"), attr(s, "VisualResource").get("value")) for s in _kids if s.get("id") == "Slots"]
assert _slots_left == [("Head", "925e51a1-4f87-cbac-e9f0-922ff50f7f8d"), ("Hair", "66ed60b2-be63-bb0f-9836-ff301fe3c197")], _slots_left
for slot, res in (("ModestyLeaf", MODESTY_LEAF), ("Private Parts", PRIVATE_PARTS)):
    n = ET.SubElement(_kids, "node", {"id": "Slots"})
    ET.SubElement(n, "attribute", {"id": "Bone", "type": "FixedString", "value": ""})
    ET.SubElement(n, "attribute", {"id": "Slot", "type": "FixedString", "value": slot})
    ET.SubElement(n, "attribute", {"id": "VisualResource", "type": "FixedString", "value": res})
save_region(os.path.join(PUB, "Content", "[PAK]_CharacterVisuals", ids["VISUAL_WARDROBE"] + ".lsx"),
            "CharacterVisualBank", lsx_node(wv, 4))

# ---------------------------------------------------------------- root templates (one _merged file, as WW Mizora's
# Public/<mod>/RootTemplates/_merged.lsf; the build converts it to .lsf)
# Item Equipment nodes follow the vanilla body/boots item shape (child order as LSLib exports it): hair-type nodes,
# ParentRace, Slot, VisualSet (dye), Visuals (EquipmentRace -> visual resources). Examples: ARM_Robe_CultOfAbsolute
# (SharedDev_RT.lsx:138385; Slot Body, maps pants 3a35f3b1 for Human Male at :138487), ARM_Boots_Monk (SharedDev_RT.lsx:51306; Slot Footwear,
# VisualSet "02 Colour"), ARM_Monk (two MapValue children under one race, SharedDev_RT.lsx:8072).
# Dye: dc5589d3 colours the suit with MaterialPreset "02 Colour" = f2bdf2d6 (Gustav CharacterVisuals _merged.lsx:164749-164753),
# which is the item colour preset "ARM_Cult_Absolute_Dark_Blue" (Shared [PAK]_Character_Presets _merged.lsx:45333) that vanilla items use
# in the same shape: ARM_StuddedLeather_CultOfAbsolute, SharedDev_RT.lsx:14006-14010 (ForcePresetValues True).
RAPHAEL_DYE = "f2bdf2d6-c00b-4bff-40a8-bbdc396930e4"
_rt = load_lsx(os.path.join(REF, "roottemplates", "SharedDev_RT.lsx"))


def _equip_child(tpl_name, child_id):
    go = find_by_attr(_rt, "GameObjects", "Name", tpl_name)
    eq = [n for n in go.find("children") if n.get("id") == "Equipment"][0]
    return copy.deepcopy([n for n in eq.find("children") if n.get("id") == child_id][0])


BOOTS_VISUALS = _equip_child("ARM_Boots_Leather_C", "Visuals")        # all races; Human Male = a9656a45
BOOTS_PARENTRACE = _equip_child("ARM_Boots_Leather_C", "ParentRace")
SUIT_PARENTRACE = _equip_child("ARM_Robe_CultOfAbsolute", "ParentRace")
del _rt
_bv = [o for o in BOOTS_VISUALS.find("children") if attr(o, "MapKey").get("value") == HUMAN_MALE_RACE_EQ]
assert len(_bv) == 1 and _bv[0].find("children")[0].find("attribute").get("value") == SUIT_BOOTS


def _suit_visuals():
    v = ET.Element("node", {"id": "Visuals"})
    o = ET.SubElement(ET.SubElement(v, "children"), "node", {"id": "Object"})
    ET.SubElement(o, "attribute", {"id": "MapKey", "type": "guid", "value": HUMAN_MALE_RACE_EQ})
    oc = ET.SubElement(o, "children")
    for res in (SUIT_PANTS, SUIT_DOUBLET):   # dc5589d3 slot order: pants before doublet
        mv = ET.SubElement(oc, "node", {"id": "MapValue"})
        ET.SubElement(mv, "attribute", {"id": "Object", "type": "FixedString", "value": res})
    return v


def _visualset():
    vs = ET.Element("node", {"id": "VisualSet"})
    ET.SubElement(vs, "attribute", {"id": "BodySetVisual", "type": "FixedString", "value": ""})
    ET.SubElement(vs, "attribute", {"id": "ShowEquipmentVisuals", "type": "bool", "value": "False"})
    k = ET.SubElement(vs, "children")
    mo = ET.SubElement(k, "node", {"id": "MaterialOverrides"})
    ET.SubElement(mo, "attribute", {"id": "MaterialResource", "type": "FixedString", "value": ""})
    mp = ET.SubElement(ET.SubElement(mo, "children"), "node", {"id": "MaterialPresets"})
    ob = ET.SubElement(ET.SubElement(mp, "children"), "node", {"id": "Object"})
    for aid, t, val in (("ForcePresetValues", "bool", "True"), ("GroupName", "FixedString", "02 Colour"),
                        ("MapKey", "FixedString", "02 Colour"), ("MaterialPresetResource", "FixedString", RAPHAEL_DYE)):
        ET.SubElement(ob, "attribute", {"id": aid, "type": t, "value": val})
    ET.SubElement(k, "node", {"id": "RealMaterialOverrides"})
    return vs


def equipment(kind):
    eq = ET.Element("node", {"id": "Equipment"})
    ch = ET.SubElement(eq, "children")
    for h in ("AfroLongHair", "AfroShortHair", "CurlyLongHair", "CurlyShortHair", "DreadLongHair", "DreadShortHair",
              "LongHair"):
        ET.SubElement(ch, "node", {"id": h})
    ch.append(copy.deepcopy(BOOTS_PARENTRACE if kind == "boots" else SUIT_PARENTRACE))
    ET.SubElement(ch, "node", {"id": "ShortHair"})
    sl = ET.SubElement(ch, "node", {"id": "Slot"})
    ET.SubElement(sl, "attribute", {"id": "Object", "type": "FixedString", "value": "Footwear" if kind == "boots" else "Body"})
    ch.append(_visualset())
    ch.append(copy.deepcopy(BOOTS_VISUALS) if kind == "boots" else _suit_visuals())
    ET.SubElement(ch, "node", {"id": "WavyLongHair"})
    ET.SubElement(ch, "node", {"id": "WavyShortHair"})
    return eq


def item_rt(name, key, parent, dn, desc, kind):
    eq = lsx_node(equipment(kind), 6)
    return f"""				<node id="GameObjects">
					<attribute id="Description" type="TranslatedString" handle="{desc}" version="1" />
					<attribute id="DisplayName" type="TranslatedString" handle="{dn}" version="1" />
					<attribute id="LevelName" type="FixedString" value="" />
					<attribute id="MapKey" type="FixedString" value="{ids[key]}" />
					<attribute id="Name" type="LSString" value="{name}" />
					<attribute id="ParentTemplateId" type="FixedString" value="{parent}" />
					<attribute id="Stats" type="FixedString" value="{name}" />
					<attribute id="Type" type="FixedString" value="item" />
					<children>
{eq}					</children>
				</node>
"""


def char_rt(name, key, visual):
    # Minimal polymorph target, as WW Mizora's human-form template 768d13e1 (MapKey, Name, Type, Parent, visual,
    # portrait visual, empty LocomotionParams). Parent BASE_Humans_Male (EquipmentRace Human Male). Icon/DisplayName
    # = the companion's own, so ChangeIcon/RetainDisplayName never show another portrait or name.
    return f"""				<node id="GameObjects">
					<attribute id="CharacterVisualResourceID" type="FixedString" value="{visual}" />
					<attribute id="DisplayName" type="TranslatedString" handle="{RAPHAEL_NAME_HANDLE}" version="1" />
					<attribute id="Icon" type="FixedString" value="{RAPHAEL_ICON}" />
					<attribute id="LevelName" type="FixedString" value="" />
					<attribute id="MapKey" type="FixedString" value="{ids[key]}" />
					<attribute id="Name" type="LSString" value="{name}" />
					<attribute id="ParentTemplateId" type="FixedString" value="{BASE_HUMANS_MALE}" />
					<attribute id="PortraitVisualResourceID" type="FixedString" value="{RAPHAEL_VISUAL}" />
					<attribute id="Type" type="FixedString" value="character" />
					<children>
						<node id="LocomotionParams" />
					</children>
				</node>
"""


_rts = (char_rt("RJTP_Raphael_SuitForm", "TPL_SUITFORM", RAPHAEL_VISUAL)
        + char_rt("RJTP_Raphael_WardrobeForm", "TPL_WARDROBEFORM", ids["VISUAL_WARDROBE"])
        + "".join(item_rt(n, k, p, dn, d, kind) for n, k, _, p, dn, d, kind in SUIT_ITEMS))
write(os.path.join(PUB, "RootTemplates", "_merged.lsx"), f"""<?xml version="1.0" encoding="utf-8"?>
<save>
	<version major="4" minor="0" revision="9" build="328" />
	<region id="Templates">
		<node id="Templates">
			<children>
{_rts}			</children>
		</node>
	</region>
</save>
""")

# ---------------------------------------------------------------- dialog loca (optional; written by the dialog tool)
DLG_LOCA = os.path.join(SRC, "dialog_loca.json")
if os.path.exists(DLG_LOCA):
    _d = json.load(open(DLG_LOCA, encoding="utf-8"))
    _rows = ([(k, 1, v) for k, v in _d.items()] if isinstance(_d, dict)
             else [(r["contentuid"], int(r.get("version", 1)), r["text"]) for r in _d])
    for cuid, ver, text in _rows:
        if cuid in LOCA and LOCA[cuid] != text:
            raise SystemExit(f"dialog_loca.json: {cuid} conflicts with a generated loca entry")
        loca(cuid, text, ver)
    print(f"merged {len(_rows)} dialog loca entries from {DLG_LOCA}")
else:
    print("no src/dialog_loca.json (dialog loca not merged)")

# ---------------------------------------------------------------- action resource (v0.4a)
# Modelled on vanilla FungalInfestationCharge (Public/SharedDev/ActionResourceDefinitions): ReplenishType "Rest" =
# long rest, MaxLevel 0, shown on the action resource panel. Granted by the hidden passive RJTP_InfernalCharge_Holder.
write(os.path.join(PUB, "ActionResourceDefinitions", "ActionResourceDefinitions.lsx"), f"""<?xml version="1.0" encoding="UTF-8"?>
<save>
    <version major="4" minor="0" revision="9" build="326"/>
    <region id="ActionResourceDefinitions">
        <node id="root">
            <children>
                <node id="ActionResourceDefinition">
                    <attribute id="Description" type="TranslatedString" handle="{H_CHARGE_DESC}" version="1"/>
                    <attribute id="DisplayName" type="TranslatedString" handle="{H_CHARGE_NAME}" version="1"/>
                    <attribute id="MaxLevel" type="uint32" value="0"/>
                    <attribute id="Name" type="FixedString" value="RJTP_InfernalCharge"/>
                    <attribute id="ReplenishType" type="FixedString" value="Rest"/>
                    <attribute id="ShowOnActionResourcePanel" type="bool" value="true"/>
                    <attribute id="UUID" type="guid" value="{uuid.uuid5(uuid.UUID(ids["MOD"]), "action_resource_infernal_charge")}"/>
                </node>
            </children>
        </node>
    </region>
</save>
""")

# ---------------------------------------------------------------- localization
body = "\n".join(
    f'  <content contentuid="{k}" version="{LOCA_VER.get(k, 1)}">{html.escape(v, quote=False)}</content>'
    for k, v in LOCA.items())
write(os.path.join(MODS, "Localization", "English", "english.xml"),
      f'<?xml version="1.0" encoding="utf-8"?>\n<contentList>\n{body}\n</contentList>\n')

# ---------------------------------------------------------------- message-box keys (v0.3e crash fix)
# OpenMessageBoxYesNo takes a short KEY, never the text: the v0.3d crash came from passing 346 bytes of resolved text
# (the answer arrived as text bytes 92-95). Vanilla resolves its keys through TranslatedStringKeys files
# (PLA_Message_RemoveStuckElfFromParty is in Mods/GustavDev/Localization/Misc.lsf: UUID = key, Content = handle); this is the same file for the mod's boxes,
# each key pointing at its own contentuid in english.xml. Packed as .lsf (build_v0_2.ps1 Is-ConvertOnly).
key_nodes = "\n".join(f"""				<node id="TranslatedStringKey">
					<attribute id="Content" type="TranslatedString" handle="{k}" version="{LOCA_VER.get(k, 1)}" />
					<attribute id="UUID" type="FixedString" value="{k}" />
					<attribute id="Speaker" type="FixedString" value="" />
					<attribute id="ExtraData" type="LSString" value="" />
					<attribute id="Stub" type="bool" value="True" />
				</node>""" for k in MSG)
write(os.path.join(MODS, "Localization", "RJTP_MessageKeys.lsx"), f"""<?xml version="1.0" encoding="utf-8"?>
<save>
	<version major="4" minor="0" revision="9" build="306" />
	<region id="TranslatedStringKeys">
		<node id="TranslatedStringKeys">
			<children>
{key_nodes}
			</children>
		</node>
	</region>
</save>
""")
print("generated into", SRC)
