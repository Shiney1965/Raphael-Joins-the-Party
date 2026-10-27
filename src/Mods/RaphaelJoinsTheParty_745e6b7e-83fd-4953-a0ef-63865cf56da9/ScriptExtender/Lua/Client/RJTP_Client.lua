-- RJTP SE layer, CLIENT: MCM button/hotkeys, the custom "Raphael's forms" MCM tab, and the no-MCM hotkey fallback.
-- MCM events and key input arrive on the client, but Osi.* exists only on the server (review 17 m8), so every
-- action is a request on the RJTP_Form net channel; the server calls the Osiris proc.
--
-- Hotkeys:
--   * MCM present: keybinding_v2 settings (unbound by default) with MCM.Keybinding.SetCallback. MCM's own
--     handler is an Ext.Events.KeyInput subscriber; the blueprint sets PreventAction=false (no suppression),
--     ShouldTriggerOnKeyDown=true, ShouldTriggerOnRepeat=false.
--   * MCM absent or unusable: our own Ext.Events.KeyInput subscriber, key-down only, never suppresses, ignored
--     until a level is running. It is only subscribed when the player has bound at least one key with the
--     CLIENT console command !rjtp_hotkey (unbound by default), and is dropped once MCM's callbacks register.
-- No Tick, no polling. Detection runs only when the tab is opened (first time per session) or Rescan is pressed.

RJTP = RJTP or {}
local CL = {}
RJTP.Client = CL

local function log(m) Ext.Utils.Print("[RJTP] " .. tostring(m)) end

-- ---------------------------------------------------------------- requests
function CL.Request(payload, done)
    if not RJTP.Chan then
        if done then pcall(done, { ok = false, note = "Script Extender net channel unavailable." }) end
        return
    end
    local ok, err = pcall(function()
        RJTP.Chan:RequestToServer(payload, function(res)
            if type(res) ~= "table" then res = { ok = false, note = "No reply from the server." } end
            if done then
                local okD, errD = pcall(done, res)
                if not okD then log("WARNING: reply handler failed: " .. tostring(errD)) end
            end
        end)
    end)
    if not ok then
        if done then pcall(done, { ok = false, note = "Request failed: " .. tostring(err) }) end
    end
end

-- Hotkey / button feedback: MCM's notification when available, else one console line (refusals and the
-- cycle result only; never per frame).
local function feedback(res, always)
    if not res then return end
    if res.ok and not always then return end
    local msg = tostring(res.note or (res.ok and "Done." or "Refused."))
    local shown = false
    if NotificationManager ~= nil then
        shown = pcall(function()
            if res.ok then
                NotificationManager.ShowInfo("rjtp_feedback", "Raphael", msg)
            else
                NotificationManager.ShowWarning("rjtp_feedback", "Raphael", msg)
            end
        end)
    end
    if not shown then log(msg) end
end

local ACTIONS = {
    cycle    = function() CL.Request({ op = "cycle" }, function(r) feedback(r, true) CL.OnState(r) end) end,
    wardrobe = function() CL.Request({ op = "look", form = "Wardrobe" }, function(r) feedback(r) CL.OnState(r) end) end,
    ascend   = function() CL.Request({ op = "ascend" }, function(r) feedback(r) CL.OnState(r) end) end,
}

-- ---------------------------------------------------------------- custom MCM tab (IMGUI)
-- MCM 1.40.1 has no MCM.Enum.SetChoices, so the modded-form picker is this tab (MCM.InsertModMenuTab,
-- table-argument form; its callback fires ONCE when the tab is created - it is not a draw loop).
local W = {}
local S = { list = nil, scanned = false, busy = false }

local function yesno(v) if v == true then return "yes" elseif v == false then return "no" end return "?" end

function CL.OnState(res)
    if not res or not W.state then return end
    local s = res.state
    pcall(function()
        if s then
            local look = tostring(s.form)
            if look == "Modded" then
                if s.modded then
                    look = "modded form " .. tostring(s.modded)
                    if S.list then
                        for _, c in ipairs(S.list) do if c.id == s.modded then look = c.label break end end
                    end
                else
                    look = "modded form (being applied)"
                end
            end
            W.state.Label = ("In this save: look = %s | auto-ascend = %s | ascended now = %s | in party = %s%s")
                :format(look, tostring(s.autoAscend), yesno(s.ascended), yesno(s.recruited),
                    s.heard == false and "  (the story did not report its state; see !rjtp_se)" or "")
        end
        if res.note and W.status then W.status.Label = tostring(res.note) end
    end)
end

local function renderList()
    if not W.host then return end
    if W.body then pcall(function() W.body:Destroy() end) W.body = nil end
    local body = W.host:AddGroup("RJTP_FormsBody")
    W.body = body
    if not S.list then
        body:AddText(S.busy and "Scanning..." or "Not scanned yet.")
        return
    end
    if #S.list == 0 then
        body:AddText("No Raphael forms from other mods were found in your load order.")
        return
    end
    for i, c in ipairs(S.list) do
        local btn = body:AddButton("Apply")
        btn.IDContext = "RJTP_apply_" .. tostring(i)
        btn.OnClick = function()
            if W.status then W.status.Label = "Applying " .. tostring(c.label) .. "..." end
            CL.Request({ op = "modded", tpl = c.id }, function(r) CL.OnState(r) end)
        end
        local txt = body:AddText(("%s   (%s skeleton)"):format(tostring(c.label), tostring(c.skel)))
        txt.SameLine = true
    end
end

function CL.Scan(force)
    if S.busy then return end
    S.busy = true
    pcall(renderList)
    CL.Request({ op = "scan", force = force == true }, function(r)
        S.busy = false
        S.scanned = true
        S.list = r.list or {}
        if W.scanInfo then
            pcall(function()
                local st = r.stats or {}
                W.scanInfo.Label = ("%d found (%s ms; %s DEMON-skeleton forms excluded)%s")
                    :format(#S.list, tostring(math.floor((tonumber(r.ms) or 0) + 0.5)), tostring(st.demon or 0),
                        r.error and ("  ERROR: " .. tostring(r.error)) or "")
            end)
        end
        pcall(renderList)
        CL.OnState(r)
    end)
end

function CL.BuildTab(tab)
    local ok, err = pcall(function()
        tab:AddText("Raphael's look. Every change here goes through the mod's Osiris story and is saved in")
        tab:AddText("your savegame; MCM profiles never change his look by themselves.")
        W.state = tab:AddText("Open this tab in a loaded game to see his current look.")
        W.status = tab:AddText("")

        tab:AddSeparatorText("Out of combat")
        local first = true
        for _, form in ipairs(RJTP.LOOKS) do
            local b = tab:AddButton(form)
            b.IDContext = "RJTP_look_" .. form
            if not first then b.SameLine = true end
            first = false
            b.OnClick = function()
                CL.Request({ op = "look", form = form }, function(r) CL.OnState(r) end)
            end
        end

        tab:AddSeparatorText("In combat")
        local asc = tab:AddButton("Ascend now")
        asc.IDContext = "RJTP_ascend"
        asc.OnClick = function() CL.Request({ op = "ascend" }, function(r) CL.OnState(r) end) end
        local ascNote = tab:AddText("Casts his Ascend spell: needs combat, his action and the spell's cooldown.")
        ascNote.SameLine = true

        tab:AddSeparatorText("Forms from other mods")
        tab:AddText("Raphael-based characters added by other mods (human or Cambion skeleton). Forms on a")
        tab:AddText("different skeleton (e.g. a mod's Ascended Fiend) are left out: they break his animations.")
        tab:AddText("Switch him back to Wardrobe before you remove the mod that provides a form.")
        local rescan = tab:AddButton("Rescan")
        rescan.IDContext = "RJTP_rescan"
        rescan.OnClick = function() CL.Scan(true) end
        W.scanInfo = tab:AddText("")
        W.scanInfo.SameLine = true
        W.host = tab:AddGroup("RJTP_FormsHost")
        renderList()
    end)
    if not ok then log("WARNING: could not build the MCM tab: " .. tostring(err)) end
end


-- ---------------------------------------------------------------- SE-only hotkeys (fallback)
-- Used when MCM is absent OR unusable (review S5): bindings live in Script Extender\RJTP\hotkeys.json
-- (Ext.IO sandbox), unbound by default, set with the CLIENT console command !rjtp_hotkey. Switched off as
-- soon as MCM's own keybinding callbacks are registered, so one key never fires twice.
local HOTKEY_FILE = "RJTP/hotkeys.json"
local MODBITS = { Shift = 1 | 2, Ctrl = 64 | 128, Alt = 256 | 512 }
local MODNAMES = { Shift = { "LShift", "RShift" }, Ctrl = { "LCtrl", "RCtrl" }, Alt = { "LAlt", "RAlt" } }
local binds = {}
local keySub = nil
local reg = { tab = false, button = false, keys = false }

local function modOn(mods, name)
    if type(mods) == "number" then return (mods & MODBITS[name]) ~= 0 end
    if mods ~= nil then
        for _, n in ipairs(MODNAMES[name]) do
            local v; pcall(function() v = mods[n] end)
            if v == true then return true end
        end
    end
    return false
end

local function loadBinds()
    binds = {}
    local ok, text = pcall(function() return Ext.IO.LoadFile(HOTKEY_FILE) end)
    if not ok or type(text) ~= "string" or text == "" then return end
    local okP, t = pcall(function() return Ext.Json.Parse(text) end)
    if okP and type(t) == "table" then
        for action, b in pairs(t) do
            if ACTIONS[action] and type(b) == "table" and type(b.Key) == "string" and b.Key ~= "" then
                binds[action] = { Key = string.upper(b.Key), Mods = type(b.Mods) == "table" and b.Mods or {} }
            end
        end
    end
end

local function anyBind() return next(binds) ~= nil end

-- Review M3: ignore keys until a level is running (main menu, loading screens).
local function levelRunning()
    local ok, running = pcall(function()
        return Ext.Utils.GetGameState() == Ext.Enums.ClientGameState["Running"]
    end)
    return ok and running == true
end

local function onKey(e)
    local down, rep, key, mods
    pcall(function() down = (tostring(e.Event) == "KeyDown") end)
    if not down then return end
    pcall(function() rep = e.Repeat end)
    if rep then return end
    pcall(function() key = string.upper(tostring(e.Key)) end)
    for action, b in pairs(binds) do
        if b.Key == key then
            if not levelRunning() then return end
            pcall(function() mods = e.Modifiers end)
            local want = {}
            for _, m in ipairs(b.Mods) do want[m] = true end
            local match = true
            for name in pairs(MODBITS) do
                if (want[name] == true) ~= modOn(mods, name) then match = false break end
            end
            if match then ACTIONS[action]() end -- no e:PreventAction(): the key still reaches the game
        end
    end
end

local function stopKeySub()
    if keySub == nil then return end
    pcall(function() Ext.Events.KeyInput:Unsubscribe(keySub) end)
    keySub = nil
end

local function ensureKeySub()
    if keySub or reg.keys or not anyBind() then return end
    local ok, id = pcall(function() return Ext.Events.KeyInput:Subscribe(onKey) end)
    if ok and id ~= nil then keySub = id end
end

-- !rjtp_hotkey <cycle|wardrobe|ascend> <Key> [Ctrl] [Shift] [Alt]   |   !rjtp_hotkey <action> none   |   !rjtp_hotkey list
-- CLIENT console command (type `client` first).
Ext.RegisterConsoleCommand("rjtp_hotkey", function(_, action, key, ...)
    loadBinds()
    if action == nil or action == "list" then
        local parts = {}
        for a in pairs(ACTIONS) do
            local b = binds[a]
            parts[#parts + 1] = a .. "=" .. (b and (table.concat(b.Mods, "+") .. (#b.Mods > 0 and "+" or "") .. b.Key) or "unbound")
        end
        table.sort(parts)
        log("hotkeys (fallback, client console): " .. table.concat(parts, ", ") ..
            (reg.keys and "  [MCM hotkeys are active, so this fallback is off: use MCM's Hotkeys page]" or ""))
        return
    end
    if not ACTIONS[action] then log("unknown action; use cycle, wardrobe or ascend") return end
    local all = {}
    for a, b in pairs(binds) do all[a] = b end
    if key == nil or string.lower(key) == "none" then
        all[action] = nil
    else
        local mods = {}
        for _, m in ipairs({ ... }) do
            local n = string.upper(string.sub(m, 1, 1)) .. string.lower(string.sub(m, 2))
            if MODBITS[n] then mods[#mods + 1] = n end
        end
        all[action] = { Key = string.upper(key), Mods = mods }
    end
    local ok = pcall(function() Ext.IO.SaveFile(HOTKEY_FILE, Ext.Json.Stringify(all)) end)
    loadBinds()
    ensureKeySub()
    log(ok and ("saved; " .. action .. " = " .. (all[action] and key or "unbound")) or "could not save the hotkey file")
end)

-- Server commands typed in the client context: say where they live.
for _, c in ipairs({ "rjtp_se", "rjtp_scan", "rjtp_tpl" }) do
    Ext.RegisterConsoleCommand(c, function()
        log(c .. " is a SERVER console command: type 'server' first, then !" .. c)
    end)
end

-- ---------------------------------------------------------------- voice identity (client copy)
-- The server sends "voicefix" on load and on every voice test (RJTP_Server.lua FixVoice). Audio plays on the
-- client, so the client entity must carry the right speaker id too.
if RJTP.Chan then
    pcall(function()
        RJTP.Chan:SetHandler(function(data)
            if type(data) ~= "table" or data.op ~= "voicefix" then return end
            local okE, e = pcall(function() return Ext.Entity.Get(RJTP.COMPANION) end)
            if not okE or e == nil then log("voice-fix client: no entity") return end
            local sp0, vo0 = RJTP.ReadVoice(e)
            local wrote = RJTP.WriteVoice(e, tostring(data.speaker), tostring(data.voice))
            local sp1, vo1 = RJTP.ReadVoice(e)
            if wrote or data.reason ~= "load" then
                log(("voice-fix (%s) client: Speaker %s -> %s, Voice %s -> %s%s"):format(tostring(data.reason), sp0, sp1,
                    vo0, vo1, wrote and "" or " (already right)"))
            end
        end)
    end)
end

-- ---------------------------------------------------------------- MCM wiring
-- Every call passes modUUID = ModuleUUID: RJTP.Mcm() may be Mods.BG3MCM, whose functions default to MCM's own
-- UUID (review S5). All MCM access happens at SessionLoaded or later, never at bootstrap.
local function registerMcm()
    local mcm = RJTP.Mcm()
    if mcm == nil then return end
    if not reg.tab and mcm.InsertModMenuTab then
        reg.tab = pcall(function()
            mcm.InsertModMenuTab({ tabName = RJTP.TAB_NAME, tabCallback = function(tab) CL.BuildTab(tab) end,
                                   modUUID = ModuleUUID })
        end)
    end
    if not reg.button and mcm.EventButton and mcm.EventButton.RegisterCallback then
        local ok, res = pcall(function()
            return mcm.EventButton.RegisterCallback({ buttonId = RJTP.S.BTN_ASCEND, modUUID = ModuleUUID,
                callback = function()
                    CL.Request({ op = "ascend" }, function(r)
                        pcall(function()
                            mcm.EventButton.ShowFeedback({ buttonId = RJTP.S.BTN_ASCEND, message = tostring(r.note or ""),
                                feedbackType = r.ok and "success" or "warning", modUUID = ModuleUUID })
                        end)
                        CL.OnState(r)
                    end)
                end })
        end)
        reg.button = ok and res ~= false -- RegisterCallback returns false without raising (memory note)
    end
    if not reg.recruit and mcm.EventButton and mcm.EventButton.RegisterCallback then
        local ok, res = pcall(function()
            return mcm.EventButton.RegisterCallback({ buttonId = RJTP.S.BTN_RECRUIT, modUUID = ModuleUUID,
                callback = function()
                    CL.Request({ op = "recruit" }, function(r)
                        pcall(function()
                            mcm.EventButton.ShowFeedback({ buttonId = RJTP.S.BTN_RECRUIT, message = tostring(r.note or ""),
                                feedbackType = r.ok and "success" or "warning", modUUID = ModuleUUID })
                        end)
                        CL.OnState(r)
                    end)
                end })
        end)
        reg.recruit = ok and res ~= false
    end
    if not reg.uninstall and mcm.EventButton and mcm.EventButton.RegisterCallback then
        local ok, res = pcall(function()
            return mcm.EventButton.RegisterCallback({ buttonId = RJTP.S.BTN_UNINSTALL, modUUID = ModuleUUID,
                callback = function()
                    CL.Request({ op = "uninstall" }, function(r)
                        pcall(function()
                            mcm.EventButton.ShowFeedback({ buttonId = RJTP.S.BTN_UNINSTALL, message = tostring(r.note or ""),
                                feedbackType = r.ok and "success" or "warning", modUUID = ModuleUUID })
                        end)
                        CL.OnState(r)
                    end)
                end })
        end)
        reg.uninstall = ok and res ~= false
    end
    if not reg.keys and mcm.Keybinding and mcm.Keybinding.SetCallback then
        reg.keys = pcall(function()
            mcm.Keybinding.SetCallback({ settingId = RJTP.S.KEY_CYCLE, callback = function() ACTIONS.cycle() end, modUUID = ModuleUUID })
            mcm.Keybinding.SetCallback({ settingId = RJTP.S.KEY_WARDROBE, callback = function() ACTIONS.wardrobe() end, modUUID = ModuleUUID })
            mcm.Keybinding.SetCallback({ settingId = RJTP.S.KEY_ASCEND, callback = function() ACTIONS.ascend() end, modUUID = ModuleUUID })
        end)
        if reg.keys then stopKeySub() end
    end
end

local mcmSubscribed = false
local function subscribeMcm()
    if mcmSubscribed or not RJTP.McmLoaded() then return end
    mcmSubscribed = true
    pcall(function()
        Ext.ModEvents.BG3MCM["MCM_Window_Ready"]:Subscribe(function() registerMcm() end)
    end)
    -- Detection on demand: the first time our tab is shown in a session (and every Rescan press).
    pcall(function()
        Ext.ModEvents.BG3MCM["MCM_Mod_Subtab_Activated"]:Subscribe(function(p)
            if type(p) ~= "table" or p.modUUID ~= ModuleUUID or p.tabName ~= RJTP.TAB_NAME then return end
            if not S.scanned then CL.Scan(false) else CL.Request({ op = "state" }, function(r) CL.OnState(r) end) end
        end)
    end)
end

-- ---------------------------------------------------------------- startup
-- Bootstrap: only the fallback (no MCM access). It is live only if the player bound a key with !rjtp_hotkey.
loadBinds()
ensureKeySub()

local function onSession()
    if RJTP.McmLoaded() then
        subscribeMcm()
        registerMcm()
    end
    -- MCM absent, or present but its keybinding API unusable: keep the fallback available.
    loadBinds()
    ensureKeySub()
end
Ext.Events.SessionLoaded:Subscribe(onSession)
pcall(function() Ext.Events.ResetCompleted:Subscribe(onSession) end)
