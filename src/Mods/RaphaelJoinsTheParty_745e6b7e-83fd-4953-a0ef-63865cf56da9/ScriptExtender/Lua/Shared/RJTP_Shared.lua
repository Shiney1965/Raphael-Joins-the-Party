-- Raphael Joins the Party - optional Script Extender layer, SHARED (loaded by both bootstraps).
-- Plan v0.2 section 5. Lua never owns state: every change goes through an Osiris proc on the server.
-- This file only holds constants and creates the net channel (Ext.Net.CreateChannel ERRORS on a
-- duplicate name, so it is created exactly once per context, here).

RJTP = RJTP or {}

RJTP.BUILD = "1.0.0"            -- bump per build; printed in the one load banner
RJTP.MCM_UUID = "755a8a72-407f-4f0d-9a33-274ac0f0b53d"

-- The companion (DB_RJTP_Companion). Bare UUID: Osiris accepts it for CHARACTER/GUIDSTRING parameters.
RJTP.COMPANION = "95a854c9-17cc-4774-83f0-ce6bf93924e2"
-- His own Voice row (Public/.../Voices/Voices.lsx, ids.json VOICE) and vanilla Raphael (S_GLO_Monitor)
RJTP.VOICE_ROW = "4bd305a8-e3a4-4400-8faf-a823fc1869d8"
RJTP.VANILLA_RAPHAEL = "f65becd6-5cd7-4c88-b85e-6dd06b60f7b8"
-- The speaker id he speaks under: vanilla Raphael's, so the game uses Larian's own voice bank and audio
-- (proven in game 2026-10-04; matches SpeakerUUID in Voices.lsx).
RJTP.VOICE_SPEAKER = RJTP.VANILLA_RAPHAEL
-- Haarlep's speaker id (vanilla voice bank 3947e0e23b4c4a39ac53454e95665b26.lsf, 60 lines, same actor). The private
-- scene borrows it while the dialog runs (RJTP_Private.txt -> PROC_RJTP_VoiceRequest -> RJTP_Server.lua).
RJTP.HAARLEP_SPEAKER = "3947e0e2-3b4c-4a39-ac53-454e95665b26"

-- Voice identity of an entity: Speaker = set of speaker ids (bg3se SpeakerComponent.field_0, FixedStrings),
-- Voice = Voices.lsx row (VoiceComponent.Voice). Returns "a,b" and the row, or "?" when unreadable.
-- The third result is the FIRST speaker id (the one that is compared and written).
function RJTP.ReadVoice(e)
    local sp, vo, first = "?", "?", "?"
    pcall(function()
        local t = {}
        for _, v in pairs(e.Speaker.field_0) do t[#t + 1] = tostring(v) end
        sp = table.concat(t, ",")
        if t[1] then first = t[1] end
    end)
    pcall(function() vo = tostring(e.Voice.Voice) end)
    return sp, vo, first
end

-- Writes the voice identity in place. Returns true only when the READ-BACK shows a change, so an entity without
-- these components (or a write the engine refused) never reports a write, and nothing repeats on every load
-- (diff review 2026-10-04).
function RJTP.WriteVoice(e, speaker, voiceRow)
    local _, vo0, first0 = RJTP.ReadVoice(e)
    if first0 == speaker and vo0 == voiceRow then return false end
    if first0 ~= "?" and first0 ~= speaker then pcall(function() e.Speaker.field_0[1] = speaker end) end
    if vo0 ~= "?" and vo0 ~= voiceRow then pcall(function() e.Voice.Voice = voiceRow end) end
    local _, vo1, first1 = RJTP.ReadVoice(e)
    return first1 ~= first0 or vo1 ~= vo0
end

-- Player-choice looks that PROC_RJTP_SetForm accepts from Lua (RJTP_Forms.txt:39-165)
RJTP.LOOKS = { "Wardrobe", "Signature", "Devil" }
RJTP.LOOK_SET = { Wardrobe = true, Signature = true, Devil = true }

-- The Ascend spell. "Ascend now" casts it through the engine so cost, cooldown and every Osiris
-- guard apply exactly as for the spell bar (review 16 M5); Osiris CastedSpell then runs PROC_RJTP_Ascend.
RJTP.ASCEND_SPELL = "Shout_RJTP_Form_Ascended"

-- MCM setting ids (MCM_blueprint.json)
RJTP.S = {
    LOOK        = "rjtp_look",
    AUTO_ASCEND = "rjtp_auto_ascend",
    BTN_ASCEND  = "rjtp_btn_ascend",
    MODDED_ENUM = "rjtp_modded_form",
    KEY_CYCLE   = "rjtp_key_cycle",
    KEY_WARDROBE = "rjtp_key_wardrobe",
    KEY_ASCEND  = "rjtp_key_ascend",
    MODE        = "rjtp_mode",
    BTN_RECRUIT = "rjtp_btn_recruit",
    BANTER      = "rjtp_banter",
    BTN_UNINSTALL = "rjtp_btn_uninstall",
}
-- v0.4a optional traits: MCM checkbox id -> the trait name Osiris knows (RJTP_Traits.txt DB_RJTP_TraitPassive)
RJTP.TRAITS = {
    rjtp_trait_soulreaper = "SoulReaper",
    rjtp_trait_resolve    = "InevitableResolve",
    rjtp_trait_fiendish   = "FiendishBlessing",
    rjtp_trait_magicres   = "MagicResistance",
}
-- Recruit modes (PLAN_modes_2026-10-03.md). Story is the default; an unreadable setting counts as Story.
RJTP.MODE_ANYTIME = "Recruit anytime"
RJTP.MODDED_NONE = "None"
RJTP.TAB_NAME = "Raphael's forms"

-- Net channel (NetChannel API: added to bg3se in commit 7510bb9a, 2024-12-05, when the DLL major
-- version was 22; RequiredVersion 29 therefore guarantees it).
if RJTP.Chan == nil then
    local ok, ch = pcall(function() return Ext.Net.CreateChannel(ModuleUUID, "RJTP_Form") end)
    if ok and ch then
        RJTP.Chan = ch
    else
        RJTP.Chan = false
        Ext.Utils.Print("[RJTP] WARNING: net channel RJTP_Form could not be created: " .. tostring(ch))
    end
end

-- MCM present? The pak in the load order is authoritative; the MCM global may be injected later.
function RJTP.McmLoaded()
    if MCM ~= nil then return true end
    local ok, loaded = pcall(function() return Ext.Mod.IsModLoaded(RJTP.MCM_UUID) end)
    return ok and loaded == true
end

-- The MCM API table (review S5). Without a meta.lsx dependency MCM may load AFTER this mod, so the injected
-- `MCM` global can be nil. MCM 1.40.1 also copies its API into Mods.BG3MCM (TableInjector.lua:
-- exposeMCMInGlobals), where the functions default to MCM's own UUID - so EVERY call made through RJTP.Mcm()
-- must pass modUUID = ModuleUUID explicitly (table-argument form, or the positional modUUID parameter).
function RJTP.Mcm()
    if MCM ~= nil then return MCM end
    local m = nil
    pcall(function() m = Mods and Mods.BG3MCM end)
    if type(m) == "table" and (m.Get ~= nil or m.InsertModMenuTab ~= nil) then return m end
    return nil
end

function RJTP.Now()
    local ok, t = pcall(function() return Ext.Timer.MonotonicTime() end)
    return ok and tonumber(t) or 0
end
