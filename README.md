# Raphael Joins the Party

**Author:** Serpentine (NexusMods: SerpentineShel)
**Version:** 1.0.0
**Game:** Baldur's Gate 3, Patch 8 or later (tested on game version 4.1.1.7631656)

Made a deal with Raphael and kept your side of it? Then on your way out of the House of Hope he may decide to protect
his investment in person. Invite him into your party, and he travels with you for the rest of Act 3: suit, devil form,
infernal fire, sarcasm and all.

---

## What it does

- **Recruit Raphael at the House of Hope.** He offers to join when you try to leave through the exit portal. This
  needs: you made the deal with him, you have not destroyed or stolen your contract, you have not killed him, and the
  base game's own confrontation with him at the portal has not already happened.
- **Your choices matter.**
  - **Took something from the Archive?** He demands it back before he will travel with you.
  - **Freed Hope?** He still offers. Hope stays free in her House.
  - **Refused him?** He will not let you walk away. You choose: fight him (the base game's House of Hope battle), or
    yield your soul (the base game's ending).
- **He arrives as he does in the base game,** with his own infernal teleport, next to the portal.
- **A full party companion.** You build his class on recruitment (a respec). He keeps a sliver of his true nature,
  **Infernal Heritage**:
  - **Igniting Spark:** a fire cantrip that scales with level and sets the target Burning.
  - **Flames of Avernus:** a cone of infernal fire. It uses his **Infernal Charge**, which comes back on a long rest.
  - **Infernal Guise:** change his look; see below.
  - **Fire resistance** and **Heavy Armour proficiency.**

  He also has **Devil's Sight**.
- **Optional traits** from his base-game stat block, each switched on in the settings menu (all off by default):
  - **Soul Reaper:** once per short rest, a killing blow on an enemy (not undead or a construct) gives back his
    Infernal Charge.
  - **Inevitable Resolve:** once per short rest, in combat, when he is held, dominated, incapacitated, restrained,
    turned, planar-bound or forced to dance, the effect ends after 1 turn.
  - **Fiendish Blessing:** the base game's effect, +2 Armour Class.
  - **Magic Resistance:** the base game's effect, Advantage on saving throws against spells.
- **His looks.**
  - **Wardrobe:** his own clothes, and any armour you give him.
  - **Signature:** his base-game suit; appearance mods for Raphael show here.
  - **Devil form.**
  - **Fiendish Ascension:** the Ascended Fiend, in combat only; appearance only.
  - He starts in his suit, and you can equip him with the Helldusk Armour.
- **He talks.** Every spoken Raphael line in the mod is one of Raphael's **own recorded lines** from the base game:
  - combat barks;
  - **party banter** with Karlach, Astarion, Gale, Lae'zel and Wyll, played when the game plays party banter;
  - **his own conversation:** click him, as you would any companion. From it you can talk, send him to wait at camp,
    bring him back, or dismiss him for good.
- **He leaves when his story needs him.** At the Astral Plane, and at the end of the game, he steps aside so the base
  game's own Raphael scenes play unchanged. Destroy your contract while he travels with you, and he leaves for good.
- **The rest of the story is untouched.** The companion is a separate character, so the base game's Raphael keeps
  every scene, fight and ending.

## Why the recruitment scene is written, not voiced

The House of Hope offer is shown as on-screen text with **written** player replies, not as a voiced cutscene. That is
a deliberate choice.

- **Only Raphael's actor can say new words for Raphael.** In a real game conversation, Raphael speaks only lines that
  his actor recorded for Baldur's Gate 3. A new recruitment scene would need new lines, and the only ways to make them
  "speak" are an imitation or an AI clone of the actor's voice.
- **Larian does not use AI voices in its games.** Larian's CEO, Swen Vincke, has said the studio does not use
  generative AI to create the art, voices or writing in its games (reported by
  [PC Gamer, 16 December 2025](https://www.pcgamer.com/games/rpg/baldurs-gate-3-developer-larian-defends-itself-as-fans-react-to-generative-ai-use-im-not-entirely-sure-we-are-the-ideal-target-for-the-level-of-scorn/)).
  The voices in Baldur's Gate 3 are human performances, and this mod keeps it that way.
- **The cast has objected.** Baldur's Gate 3's actors, including the game's narrator, Amelia Tyler, have objected
  publicly to AI clones of their voices being used without their consent
  ([report](https://sg.news.yahoo.com/baldurs-gate-3-actors-tear-191952145.html)).
- **Nexus Mods advises the same.** Its policy asks modders to avoid AI tools unless they have explicit permission for
  every asset, and says this is "particularly true for AI-generated voice acting"
  ([Nexus Mods: AI-Generated Content in Modding](https://www.nexusmods.com/news/14850)).

So this mod never clones or imitates a voice. Raphael's spoken lines (barks, banter, his conversation) are all his
real recorded lines, re-used. Where new words were needed, as in the recruitment offer, they appear as text.

## Requirements

- **Baldur's Gate 3**, Patch 8 or later.
- **Optional:** [BG3 Script Extender](https://github.com/Norbyte/bg3se) and
  [Mod Configuration Menu (MCM)](https://www.nexusmods.com/baldursgate3/mods/9162). With them you get the settings
  menu below: "Recruit anytime" mode, the optional traits, the banter switch, hotkeys for his looks, other mods'
  Raphael forms, and the "Prepare to uninstall" button.

  Without them the mod still works, in Story mode, with banter on and the optional traits off.

## Settings (MCM)

**Recruitment tab**
- **Recruitment mode.** **Story** (the default): he can join only through his House of Hope offer. **Recruit
  anytime**: the "Recruit Raphael now" button also works, at any point of the game.
- **Recruit Raphael now** (Recruit anytime mode only; host only; outside combat and dialogue).
- **Prepare to uninstall:** see "Uninstalling" below.

**Look tab**
- **Party banter:** on by default. Untick it to stop his banter.
- **Out-of-combat look:** Wardrobe, Signature or Devil.
- **Auto-ascend in combat**, and an **Ascend now** button.
- **Form from another mod:** use a Raphael form from another installed mod (also on the "Raphael's forms" tab).
- **Hotkeys** (unbound by default): cycle his look; back to Wardrobe; Ascend now. Set them on MCM's own **Hotkeys**
  page, which lists the hotkeys of every mod.

**Traits tab**
- The four optional traits above, each off by default. They apply to every save while he is in your company.

## Installation

See [`docs/INSTALL.md`](docs/INSTALL.md) for the step-by-step guide. In short:
1. Copy `RaphaelJoinsTheParty.pak` into your Mods folder (`%LocalAppData%\Larian Studios\Baldur's Gate 3\Mods`).
2. Activate it in BG3 Mod Manager (or the in-game mod manager). If you use MCM, keep MCM above this mod.
3. Load your save. The mod can be added to a game already in progress; he becomes available at the House of Hope in
   Act 3.

## Uninstalling

**With MCM:** in a loaded save, outside combat, the host opens MCM → Raphael Joins the Party → Recruitment →
**Prepare to uninstall**, and confirms. He returns to his own clothes and leaves the party. His own clothes are
removed, and any items you gave him go to one of your characters. A message confirms it, and the House of Hope will
not offer him again in that save. Then save, quit, and remove the mod.

**Without MCM:** click him, choose to dismiss him for good (his items are handled the same way), then save, quit and
remove the mod. Dismissing him leaves the House of Hope as it is. If he never joined you, remove the mod only while
you are outside the House of Hope.

## Compatibility

- **House of Hope:** the offer uses the base game's House of Hope exit portal and Raphael's own arrival. Mods that
  replace that portal or his ambush have not been tested with it.
- **Raphael appearance mods:** these show in his Signature look.
- **Multiplayer:** the offer goes to the player who uses the portal, and the host runs the settings menu. Multiplayer
  has not been tested yet, so reports are welcome.

## Known limitations

- The recruitment offer uses the game's message boxes, so the buttons say **Yes** and **No**. Your character's reply
  for each is written in the box.
- The base game's cinematic camera for Raphael's arrival is not used; the boxes appear over the normal view.

## Credits

- **Larian Studios** for Baldur's Gate 3, and **Andrew Wincott** for Raphael's performance. Every Raphael voice line in
  this mod is his original recording from the base game.
- **Norbyte** (BG3 Script Extender, LSLib/Divine). **AtilioA and contributors** (Mod Configuration Menu).
  **LaughingLeader** (BG3 Mod Manager). **ShinyHobo** (BG3 Modders Multitool).
- Studied for technique, with no files copied:
  [Alfira Joins The Party](https://www.nexusmods.com/baldursgate3/mods/12257),
  [Mizora Joins the Party](https://www.nexusmods.com/baldursgate3/mods/24675) and
  [Aylin and Isobel Join the Party](https://www.nexusmods.com/baldursgate3/mods/23665) (the last two by WorldWalker42).

## AI disclosure

This mod's scripts, data and documentation were written with the help of an AI coding assistant, Claude by Anthropic,
under the author's direction and testing. **No AI-generated voice, image, model or texture is used.** All voice lines
are Larian's original recordings, and the written dialogue was approved by the author.

## Download

Get the ready-to-install zip from the [Releases](https://github.com/Shiney1965/Raphael-Joins-the-Party/releases) page.
Installation steps are in [`docs/INSTALL.md`](docs/INSTALL.md); the history is in [`CHANGELOG.md`](CHANGELOG.md).

## Building from source

This repository holds the mod's own source: the Osiris story goals, dialog specs, stats, Lua and the generator
scripts. It does **not** include extracted Baldur's Gate 3 game files, and two kinds of file the build makes from them
are left out too: his voice bank (`src/Mods/*/Localization/English/Soundbanks/`, written by `tools/gen_data.py` from
the game's voice metadata) and his camp timeline (`src/Public/*/Timeline/Generated/`, copied by
`tools/gen_timelines.py` from a game timeline). The build regenerates both.

The build needs, on Windows:
- **`_vanilla_ref/`**, extracts from the game: Raphael's dialogs and voice metadata, `dumps/` (line tables used by
  `tools/gen_banter_content.py` and `tools/gen_timelines.py`), `timeline_donor/` (the donor camp timeline and scene),
  `stats/`, `roottemplates/`, `english.xml` and `story_header.div`. Each script names the files it reads at its top.
- **`_vanilla_story/`**, the game's extracted story goals, indexed by `tools/osiris_lint.py`.
- **`build/story_base_noRJTP_20261001.div`**, a compiled base story, for `tools/story_dll_check.py`.
- **[LSLib's Divine.exe](https://github.com/Norbyte/lslib)** and **StoryCompiler.exe**, and the **BG3 Toolkit's
  `Osiris.dll`** (loaded by `tools/osiris_dll_compile.py`). Their paths are set at the top of `build_v0_2.ps1`,
  `tools/gen_timelines.py`, `tools/gen_dialogs.py`, `tools/story_compile_check.py` and
  `tools/osiris_dll_compile.py`.
- **Python 3** on the `PATH`.

Then run `build_v0_2.ps1` in PowerShell. It regenerates the data, runs the Osiris, stats and LSX checks, and packs
`dist/RaphaelJoinsTheParty.pak`.

## Licence

The mod's own code and documentation are released under the MIT License (see [`LICENSE`](LICENSE)). Baldur's Gate 3,
its characters and its recorded performances belong to Larian Studios; see
[`LICENSE-THIRD-PARTY.md`](LICENSE-THIRD-PARTY.md).
