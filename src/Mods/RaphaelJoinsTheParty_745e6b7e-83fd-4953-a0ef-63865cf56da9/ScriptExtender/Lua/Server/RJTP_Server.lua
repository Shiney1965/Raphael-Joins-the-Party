-- RJTP SE layer, SERVER: net requests from the client, MCM setting events, the uninstall guard, console.
-- Rules (plan v0.2 section 5; the author's R1-R6): no Tick or per-frame work; detection only on demand; a profile
-- switch never applies a form; every change is an Osiris call; minimal logging.

RJTP = RJTP or {}
local O = RJTP.Osi
local D = RJTP.Detect

RJTP.sessionLoaded = false
RJTP.profileSwitchAt = -1e12     -- MonotonicTime of the last MCM profile switch
RJTP.enumWriteAt = -1e12         -- MonotonicTime of our last MCM.Enum.SetChoices
RJTP.enumMap = {}                -- dynamic-enum label -> template id
RJTP.lastCycleKey = nil          -- fallback when the current look cannot be read
local QUIET_MS = 3000            -- MCM events this soon after a profile switch / our own enum write are ignored

local function log(m) Ext.Utils.Print("[RJTP] " .. tostring(m)) end

-- ---------------------------------------------------------------- host check (multiplayer)
-- Same pattern as MIR (Server/Browser.lua): 65537 = the host's user id; otherwise match the sender's
-- ClientControl entity against Osi.GetHostCharacter() (bare 36-char suffix).
local HOST_USER = 65537
local function isHostUser(user)
    if user == nil or user == HOST_USER then return true end
    local ok, result = pcall(function()
        local host = tostring(Osi.GetHostCharacter() or ""):sub(-36)
        for _, entity in pairs(Ext.Entity.GetAllEntitiesWithComponent("ClientControl") or {}) do
            local uid = entity.UserReservedFor and entity.UserReservedFor.UserID or nil
            if uid == user then
                return entity.Uuid and entity.Uuid.EntityUuid == host
            end
        end
        return false
    end)
    return ok and result or false
end

-- ---------------------------------------------------------------- modded-form list
local function publicList(cache)
    local out = {}
    for i, c in ipairs(cache.list) do
        out[i] = { id = c.id, name = c.name, mod = c.mod, skel = c.skel, label = c.label }
    end
    return out
end

-- On MCM builds that have MCM.Enum.SetChoices (1.41+; not in the author's 1.40.1), fill the dynamic enum too.
local function pushEnumChoices(cache)
    local mcm = RJTP.Mcm()
    if not (mcm and mcm.Enum and mcm.Enum.SetChoices) then return end
    local choices, map = { RJTP.MODDED_NONE }, {}
    for _, c in ipairs(cache.list) do
        choices[#choices + 1] = c.label
        map[c.label] = c.id
    end
    RJTP.enumMap = map
    RJTP.enumWriteAt = RJTP.Now()
    local ok, err = pcall(function() mcm.Enum.SetChoices(RJTP.S.MODDED_ENUM, choices, ModuleUUID) end)
    if not ok then log("WARNING: MCM.Enum.SetChoices failed: " .. tostring(err)) end
end

local function scan(force)
    local cache = D.Get(force)
    if force or not RJTP.enumPushed then
        RJTP.enumPushed = true
        pushEnumChoices(cache)
    end
    return cache
end

local function applyModded(tpl)
    local okV, res = D.Validate(tpl)
    if not okV then return { ok = false, note = res } end
    local r = O.ApplyModded(res)
    if r.ok then RJTP.lastCycleKey = "Modded:" .. res end
    return r
end

-- ---------------------------------------------------------------- cycle (hotkey)
local function cycle()
    local order = {}
    for _, f in ipairs(RJTP.LOOKS) do order[#order + 1] = f end
    local cache = scan(false)
    for _, c in ipairs(cache.list) do order[#order + 1] = "Modded:" .. c.id end
    local cur = O.CurrentLookKey() or RJTP.lastCycleKey
    local idx = 0
    for i, k in ipairs(order) do if k == cur then idx = i break end end
    local nextKey = order[(idx % #order) + 1]
    local label = nextKey
    local r
    if string.sub(nextKey, 1, 7) == "Modded:" then
        local c = cache.byId[string.sub(nextKey, 8)]
        label = c and c.label or nextKey
        r = applyModded(string.sub(nextKey, 8))
    else
        r = O.SetLook(nextKey)
        if r.ok then RJTP.lastCycleKey = nextKey end
    end
    -- keep the action's own note (e.g. "look chosen; his Ascended form ends now") - review M4
    r.note = "Look: " .. label .. " - " .. tostring(r.note or "")
    return r
end

-- ---------------------------------------------------------------- net requests
local WRITE_OPS = { look = true, ascend = true, modded = true, cycle = true, recruit = true, uninstall = true }

local function handle(data, user)
    data = type(data) == "table" and data or {}
    local op = data.op
    if WRITE_OPS[op] and not isHostUser(user) then
        return { ok = false, note = "Only the host can do that." }
    end
    local reply
    if op == "state" then
        reply = { ok = true }
    elseif op == "scan" then
        local cache = scan(data.force == true)
        reply = { ok = true, list = publicList(cache), ms = cache.ms, stats = cache.stats, error = cache.error }
    elseif op == "look" then
        reply = O.SetLook(tostring(data.form))
        if reply.ok then RJTP.lastCycleKey = tostring(data.form) end
    elseif op == "ascend" then
        reply = O.Ascend()
    elseif op == "modded" then
        reply = applyModded(data.tpl)
    elseif op == "cycle" then
        reply = cycle()
    elseif op == "recruit" then
        reply = O.RecruitAnytime()
    elseif op == "uninstall" then
        reply = O.Uninstall()
    else
        reply = { ok = false, note = "Unknown request." }
    end
    if O.GameRunning() then reply.state = O.State() end
    return reply
end

if RJTP.Chan then
    RJTP.Chan:SetRequestHandler(function(data, user)
        local ok, res = pcall(handle, data, user)
        if ok then return res end
        log("WARNING: request failed: " .. tostring(res))
        return { ok = false, note = "Internal error (see the SE log)." }
    end)
end

-- ---------------------------------------------------------------- MCM (server side)
-- Subscribed at SessionLoaded, never at bootstrap (review S5): without a meta.lsx dependency MCM may load after
-- this mod, and touching Ext.ModEvents.BG3MCM when MCM is not loaded makes SE log warnings (T16).
local function quiet(since) return (RJTP.Now() - since) < QUIET_MS end

-- A value changed in MCM (by the player, or by a per-setting Reset, which MCM 1.40.1 routes through the same
-- SetSettingValue -> MCM_Setting_Saved path) applies it. A profile switch never does (review 16 M6).
local function onSettingSaved(p)
    if type(p) ~= "table" or p.modUUID ~= ModuleUUID then return end
    local id, v = p.settingId, p.value
    if quiet(RJTP.profileSwitchAt) or not O.GameRunning() then return end
    local r
    if id == RJTP.S.LOOK then
        if RJTP.LOOK_SET[v] then r = O.SetLook(v) end
    elseif id == RJTP.S.AUTO_ASCEND then
        if type(v) == "boolean" then r = O.SetAutoAscend(v) end
    elseif id == RJTP.S.BANTER then
        if type(v) == "boolean" then r = O.SetBanter(v) end
    elseif RJTP.TRAITS[id] then
        if type(v) == "boolean" then r = O.SetTrait(RJTP.TRAITS[id], v) end
    elseif id == RJTP.S.MODDED_ENUM then
        if quiet(RJTP.enumWriteAt) or v == RJTP.MODDED_NONE then return end
        local tpl = RJTP.enumMap[v]
        if tpl then r = applyModded(tpl) end
    end
    if r and not r.ok then log(r.note) end
end

local mcmSubscribed = false
local function subscribeMcm()
    if mcmSubscribed or not RJTP.McmLoaded() then return end
    mcmSubscribed = true
    pcall(function() Ext.ModEvents.BG3MCM["MCM_Setting_Saved"]:Subscribe(function(p)
        local ok, err = pcall(onSettingSaved, p)
        if not ok then log("WARNING: MCM setting handler failed: " .. tostring(err)) end
    end) end)
    pcall(function() Ext.ModEvents.BG3MCM["MCM_Profile_Activated"]:Subscribe(function()
        RJTP.profileSwitchAt = RJTP.Now()
    end) end)
end

-- ---------------------------------------------------------------- session + uninstall guard (plan 5.3)
Ext.Events.SessionLoaded:Subscribe(function()
    RJTP.sessionLoaded = true
    subscribeMcm()
end)
-- A console `reset` reloads Lua inside a running session without a new SessionLoaded.
pcall(function()
    Ext.Events.ResetCompleted:Subscribe(function()
        RJTP.sessionLoaded = true
        subscribeMcm()
    end)
end)

-- Osiris SavegameLoaded (after Osiris's own load rules), then a short game-clock delay so the story's
-- SavegameLoaded rules and its 300 ms two-phase timers have run. Fires only on save loads, never per frame.
pcall(function()
    Ext.Osiris.RegisterListener("SavegameLoaded", 0, "after", function()
        pcall(function()
            Ext.Timer.WaitFor(2000, function()
                local ok, res = pcall(O.UninstallGuard)
                RJTP.guardResult = ok and res or ("error: " .. tostring(res))
                pcall(RJTP.FixVoice, "load", RJTP.testSpeaker)
            end)
        end)
    end)
end)

-- v0.4a: push the trait checkboxes into the story at every level start (covers loaded saves and a new game, which
-- has no SavegameLoaded), after the story's own load rules. Level starts are rare; never per frame.
pcall(function()
    Ext.Osiris.RegisterListener("LevelGameplayStarted", 2, "after", function()
        pcall(function()
            Ext.Timer.WaitFor(2000, function()
                if RJTP.McmLoaded() then
                    local ok, err = pcall(O.PushTraits)
                    if not ok then log("WARNING: trait push failed: " .. tostring(err)) end
                end
            end)
        end)
    end)
end)

-- ---------------------------------------------------------------- voice identity patch (saves made before 2026-10-04)
-- The Speaker / Voice components are baked into the save when he is registered as an Origin. Saves made with
-- earlier test builds carry the generic speaker 4df6dba0 ("male voice 5") or his own GUID; Raphael's lines are
-- silent under both. This sets the speaker to vanilla Raphael's id (RJTP.VOICE_SPEAKER) and the Voice row to the
-- mod's, on the server, and asks every client to do the same (audio plays on the client). Proven to take effect
-- at runtime on 2026-10-04 (console test).
function RJTP.FixVoice(reason, speakerOverride)
    local okE, e = pcall(function() return Ext.Entity.Get(RJTP.COMPANION) end)
    if not okE or e == nil then return end
    local want = speakerOverride or RJTP.VOICE_SPEAKER
    local sp0, vo0 = RJTP.ReadVoice(e)
    if RJTP.WriteVoice(e, want, RJTP.VOICE_ROW) then
        pcall(function() e:Replicate("Speaker") end)
        pcall(function() e:Replicate("Voice") end)
        local sp1, vo1 = RJTP.ReadVoice(e)
        log(("voice-fix (%s) server: Speaker %s -> %s, Voice %s -> %s"):format(tostring(reason), sp0, sp1, vo0, vo1))
    end
    if RJTP.Chan then
        pcall(function()
            RJTP.Chan:Broadcast({ op = "voicefix", speaker = want, voice = RJTP.VOICE_ROW, reason = tostring(reason) })
        end)
    end
end

-- Private scene (v0.3c): Osiris asks for Haarlep's speaker id while the scene's Haarlep lines play, and for his own
-- again when the dialog ends (RJTP_Private.txt). Event-driven: one write per request, nothing is polled. A load
-- resets the speaker through the SavegameLoaded FixVoice above, which never uses the scene speaker.
pcall(function()
    Ext.Osiris.RegisterListener("PROC_RJTP_VoiceRequest", 1, "after", function(who)
        local w = tostring(who)
        local speaker = RJTP.testSpeaker
        RJTP.sceneToken = (RJTP.sceneToken or 0) + 1
        if w == "haarlep" then
            speaker = RJTP.HAARLEP_SPEAKER
            -- Safety net: if the switch back never comes (no DialogEnded), restore his own voice after five
            -- minutes. One timer per scene; it does nothing when a later request has already been handled.
            local token = RJTP.sceneToken
            pcall(function()
                Ext.Timer.WaitFor(300000, function()
                    if RJTP.sceneToken == token then
                        RJTP.sceneToken = token + 1
                        pcall(RJTP.FixVoice, "scene timeout", RJTP.testSpeaker)
                    end
                end)
            end)
        end
        local ok, err = pcall(RJTP.FixVoice, "scene " .. w, speaker)
        if not ok then log("voice request failed: " .. tostring(err)) end
    end)
end)

-- ---------------------------------------------------------------- voice diagnostic (test spells only)
-- When a voice test spell is cast, log what the game's file system and the companion entity look like, so a
-- silent test can be explained from the SE log. Runs once per cast; nothing here runs otherwise.
local VOICE_FILES = {
    "Mods/Gustav/Localization/English/Soundbanks/f65becd65cd74c88b85e6dd06b60f7b8.lsf",
    "Mods/Gustav/Localization/English/Soundbanks/vf65becd65cd74c88b85e6dd06b60f7b8_ha15db615gad06g4578g98d7gb3e1843491e1.wem",
}
local function dumpEntity(label, guid)
    local okE, e = pcall(function() return Ext.Entity.Get(guid) end)
    if not okE or e == nil then log("voice-diag " .. label .. ": no entity") return end
    local names = {}
    pcall(function()
        for _, n in pairs(e:GetAllComponentNames()) do
            local s = tostring(n)
            if s:find("Voice") or s:find("Speaker") or s:find("Origin") or s:find("Sound") or s:find("Dialog") then
                names[#names + 1] = s
            end
        end
    end)
    table.sort(names)
    log("voice-diag " .. label .. " components: " .. table.concat(names, ", "))
    for _, n in ipairs({ "Voice", "VoiceTag", "Speaker", "ServerSpeaker", "Origin", "ServerOriginalIdentity" }) do
        local okC, js = pcall(function()
            local c = e[n]
            if c == nil then return nil end
            return Ext.Json.Stringify(c, { Beautify = false, StringifyInternalTypes = true, IterateUserdata = true,
                                           AvoidRecursion = true, MaxDepth = 4 })
        end)
        if okC and js then log("voice-diag " .. label .. "." .. n .. " = " .. string.sub(tostring(js), 1, 400)) end
    end
end
local function voiceDiag(tag)
    RJTP.FixVoice("voice test " .. tostring(tag), RJTP.testSpeaker)
    log("voice-diag start (" .. tostring(tag) .. ", build " .. tostring(RJTP.BUILD) .. ")")
    for _, path in ipairs(VOICE_FILES) do
        local ok, data = pcall(function() return Ext.IO.LoadFile(path, "data") end)
        log("voice-diag file " .. ((ok and data) and (#data .. " bytes  ") or "MISSING      ") .. path)
    end
    dumpEntity("companion", RJTP.COMPANION)
    local okH, host = pcall(function() return Osi.GetHostCharacter() end)
    if okH and host then dumpEntity("host", tostring(host):sub(-36)) end
    dumpEntity("vanillaRaphael", "f65becd6-5cd7-4c88-b85e-6dd06b60f7b8")
end
pcall(function()
    Ext.Osiris.RegisterListener("PROC_RJTP_Dlg_VoiceSpike", 3, "after", function(_, _, tag)
        local ok, err = pcall(voiceDiag, tag)
        if not ok then log("voice-diag failed: " .. tostring(err)) end
    end)
end)

-- ---------------------------------------------------------------- console (server context: type `server` first)
Ext.RegisterConsoleCommand("rjtp_se", function()
    local s = O.State()
    local getOk, getInfo = O.DbGetWorks()
    local mcm = RJTP.Mcm()
    log(("build %s | report heard=%s (%d reports, %d silent) | queries %d, failures %d%s | Osi.DB:Get %s (%s) | in party=%s | form=%s modded=%s | auto-ascend=%s | ascended=%s | guard=%s | MCM loaded=%s api=%s SetChoices=%s")
        :format(RJTP.BUILD, tostring(s.heard), O.diag.reports, O.diag.silentReports, O.diag.queries, O.diag.failures,
            O.diag.firstError and (", first: " .. O.diag.firstError) or "",
            getOk and "works" or "FAILS", tostring(getInfo),
            tostring(s.recruited), tostring(s.form), tostring(s.modded), tostring(s.autoAscend),
            tostring(s.ascended), tostring(RJTP.guardResult), tostring(RJTP.McmLoaded()),
            mcm == nil and "none" or (mcm == MCM and "global" or "Mods.BG3MCM"),
            tostring(mcm ~= nil and mcm.Enum ~= nil and mcm.Enum.SetChoices ~= nil)))
end)

-- Voice test aid. The default is vanilla Raphael's speaker id (the shipped setup). `!rjtp_speaker own` makes him
-- speak under his own GUID (silent: no bank) until the next load; `!rjtp_speaker raphael` goes back at once.
Ext.RegisterConsoleCommand("rjtp_speaker", function(_, which)
    if which == "own" then RJTP.testSpeaker = RJTP.COMPANION
    elseif which == "raphael" or which == nil then RJTP.testSpeaker = nil
    else log("usage: !rjtp_speaker raphael | own") return end
    RJTP.FixVoice("console", RJTP.testSpeaker)
    log("voice test speaker = " .. tostring(RJTP.testSpeaker or RJTP.VOICE_SPEAKER))
end)

-- Spike M0: time the detection pass and list the candidates.
Ext.RegisterConsoleCommand("rjtp_scan", function()
    local cache = scan(true)
    local st = cache.stats
    log(("scan %d ms | templates %d, characters %d, Raphael-based %d, DEMON excluded %d, base-game/RJTP skipped %d, source unknown skipped %d | offered %d%s")
        :format(math.floor((tonumber(cache.ms) or 0) + 0.5), st.templates, st.characters, st.matched, st.demon,
            st.vanilla, st.unattributed or 0, #cache.list, cache.error and (" | ERROR " .. cache.error) or ""))
    for _, c in ipairs(cache.list) do log(("  %s  %s  [%s]  %s"):format(c.id, c.name, c.mod, c.skel)) end
end)

-- Spike M0: dump the fields detection relies on, for one template (e.g. !rjtp_tpl 54a3ae4c-...).
Ext.RegisterConsoleCommand("rjtp_tpl", function(_, id)
    local ok, t = pcall(function() return Ext.Template.GetRootTemplate(id) end)
    if not ok or t == nil then log("no root template " .. tostring(id)) return end
    local function f(n) local o, v = pcall(function() return t[n] end) return o and tostring(v) or "<err>" end
    log(("Id=%s TemplateName=%s Name=%s Type=%s Parent=%s Visual=%s FileName=%s"):format(f("Id"), f("TemplateName"),
        f("Name"), f("TemplateType"), f("ParentTemplateId"), f("CharacterVisualResourceID"), f("FileName")))
end)

-- rjtp_hotkey is a CLIENT command; say so if it is typed in the server context (review M6).
Ext.RegisterConsoleCommand("rjtp_hotkey", function()
    log("rjtp_hotkey is a CLIENT console command: type 'client' first, then !rjtp_hotkey ...")
end)
