-- RJTP SE layer, SERVER: reading Osiris state and calling the Osiris API (plan v0.2 section 5.1).
-- Osi.* exists only on the server (review 17 m8). Lua calls ONLY these, so all state stays in Osiris:
--   PROC_RJTP_SetForm((CHARACTER)_Comp, (STRING)_Form)                  RJTP_Forms.txt (player choice)
--   PROC_RJTP_ApplyModdedForm((CHARACTER)_Comp, (GUIDSTRING)_Template)  two-phase inside Osiris (300 ms)
--   PROC_RJTP_SetAutoAscend((INTEGER)1|0)                                gated on DB_RJTP_Recruited in Osiris
--   UseSpell(...) for "Ascend now" -> Osiris CastedSpell -> PROC_RJTP_Ascend
--
-- READING STATE (SE-layer review B1). `Osi.DB_X:Get` failed inside a mod environment in another of the author's mods
-- (RoahMoonglowRestored, 2026-08-29), so no decision here depends on it. State comes from:
--   * PROC_RJTP_Report(), which calls PROC_RJTP_FormIs(_Form) and PROC_RJTP_ModdedFormIs(_Template); both are
--     no-op procs that this file observes with Ext.Osiris.RegisterListener (API.md: user PROCs can be captured);
--   * Osiris QUERIES (IsPartyMember, IsInCombat, IsDead, HasActiveStatus), which do work in a mod environment.
-- `:Get` is used only as a diagnostic in !rjtp_se.

RJTP = RJTP or {}
local O = {}
RJTP.Osi = O

local C = RJTP.COMPANION
local ASCEND_STATUSES = { "RJTP_FORM_ASCENDED", "RJTP_FORM_ASCENDED_X2" }

O.diag = { queries = 0, failures = 0, firstError = nil, reports = 0, silentReports = 0 }

local function note(err)
    O.diag.failures = O.diag.failures + 1
    if O.diag.firstError == nil then
        O.diag.firstError = tostring(err)
        Ext.Utils.Print("[RJTP] WARNING: an Osiris call failed (" .. tostring(err) .. "); run !rjtp_se for details.")
    end
end

function O.Guid36(s)
    if type(s) ~= "string" then return nil end
    if #s >= 36 then return string.lower(string.sub(s, -36)) end
    return string.lower(s)
end

-- ---------------------------------------------------------------- report hooks (registered at bootstrap)
local rep = nil          -- collector while PROC_RJTP_Report runs
O.autoAscendSeen = nil   -- true/false once DB_RJTP_AutoAscend changed this session; nil = not known

pcall(function()
    Ext.Osiris.RegisterListener("PROC_RJTP_FormIs", 1, "after", function(form)
        if rep then rep.form = tostring(form) end
    end)
end)
pcall(function()
    Ext.Osiris.RegisterListener("PROC_RJTP_ModdedFormIs", 1, "after", function(tpl)
        if rep then rep.modded = O.Guid36(tostring(tpl)) end
    end)
end)
pcall(function()
    Ext.Osiris.RegisterListener("DB_RJTP_AutoAscend", 1, "after", function() O.autoAscendSeen = true end)
end)
-- PROC_RJTP_RecruitAnytime reports exactly one result through this no-op proc (RJTP_Companion.txt).
local anytimeResult = nil
pcall(function()
    Ext.Osiris.RegisterListener("PROC_RJTP_AnytimeResult", 1, "after", function(res) anytimeResult = tostring(res) end)
end)
pcall(function()
    Ext.Osiris.RegisterListener("DB_RJTP_AutoAscend", 1, "afterDelete", function() O.autoAscendSeen = false end)
end)
-- v0.3a: bark / banter log hooks (no-op procs in RJTP_Banter.txt). Event-driven prints only; nothing is polled.
pcall(function()
    Ext.Osiris.RegisterListener("PROC_RJTP_BarkLog", 2, "after", function(group, result)
        Ext.Utils.Print("[RJTP] bark " .. tostring(group) .. ": " .. tostring(result))
    end)
end)
pcall(function()
    Ext.Osiris.RegisterListener("PROC_RJTP_BanterLog", 2, "after", function(index, result)
        Ext.Utils.Print("[RJTP] banter " .. tostring(index) .. ": " .. tostring(result))
    end)
end)

-- Returns { heard = bool, form = string|nil, modded = guid|nil }, or nil if the call itself failed.
-- heard = false means the listeners did not fire (then form/modded are UNKNOWN, not "none").
function O.Report()
    rep = {}
    O.diag.reports = O.diag.reports + 1
    local ok, err = pcall(function() Osi.PROC_RJTP_Report() end)
    local r = rep
    rep = nil
    if not ok then note("PROC_RJTP_Report: " .. tostring(err)) return nil end
    r.heard = (r.form ~= nil)
    if not r.heard then O.diag.silentReports = O.diag.silentReports + 1 end
    return r
end

-- ---------------------------------------------------------------- queries
local function query(label, fn)
    O.diag.queries = O.diag.queries + 1
    local ok, v = pcall(fn)
    if not ok then note(label .. ": " .. tostring(v)) return nil end
    return v
end
local function truthy(v) if v == nil then return nil end return v == 1 or v == true end

function O.InCombat() return truthy(query("IsInCombat", function() return Osi.IsInCombat(C) end)) end
function O.IsDead() return truthy(query("IsDead", function() return Osi.IsDead(C) end)) end

-- In the party. Stricter than DB_RJTP_Recruited (a benched Raphael is refused), never looser.
function O.InParty() return truthy(query("IsPartyMember", function() return Osi.IsPartyMember(C, 0) end)) end

function O.Ascended()
    for _, s in ipairs(ASCEND_STATUSES) do
        local v = truthy(query("HasActiveStatus", function() return Osi.HasActiveStatus(C, s) end))
        if v == nil then return nil end
        if v then return true end
    end
    return false
end

function O.GameRunning()
    if not RJTP.sessionLoaded then return false end
    local ok, host = pcall(function() return Osi.GetHostCharacter() end)
    return ok and host ~= nil and host ~= ""
end

-- Diagnostic only: does Osi.DB_X:Get work in this mod environment?
function O.DbGetWorks()
    local ok, r = pcall(function() return Osi.DB_RJTP_Companion:Get(nil) end)
    if ok and type(r) == "table" then return true, #r end
    return false, tostring(r)
end

-- Snapshot for the UI (strings/booleans only; small).
function O.State()
    local s = {}
    local r = O.Report()
    s.heard = r ~= nil and r.heard or false
    s.form = (r and r.heard) and r.form or "unknown"
    s.modded = r and r.modded or nil
    s.recruited = O.InParty()
    s.ascended = O.Ascended()
    s.inCombat = O.InCombat()
    if O.autoAscendSeen == nil then s.autoAscend = "unchanged this session" else s.autoAscend = O.autoAscendSeen and "on" or "off" end
    return s
end

-- ---------------------------------------------------------------- actions (all return {ok, note})
local function gate()
    if not O.GameRunning() then return false, "Not in a running game." end
    local inParty = O.InParty()
    if inParty == nil then return false, "Could not check whether Raphael is in your party (see !rjtp_se)." end
    if not inParty then return false, "Raphael is not in your active party." end
    if O.IsDead() == true then return false, "Raphael is dead." end
    return true
end
O.Gate = gate

function O.SetLook(form)
    if not RJTP.LOOK_SET[form] then return { ok = false, note = "Unknown look: " .. tostring(form) } end
    local okG, why = gate()
    if not okG then return { ok = false, note = why } end
    local ascended = O.Ascended()
    local ok, err = pcall(function() Osi.PROC_RJTP_SetForm(C, form) end)
    if not ok then return { ok = false, note = "Osiris call failed: " .. tostring(err) } end
    local r = O.Report()
    if r and r.heard and r.form ~= form then
        return { ok = false, note = "Osiris did not record the look (now: " .. tostring(r.form) .. ")." }
    end
    if ascended then
        return { ok = true, note = form .. " look chosen; his Ascended form ends now." }
    end
    return { ok = true, note = form .. " look chosen (during a camp night it shows the next morning)." }
end

-- Recruit anytime (PLAN_modes_2026-10-03.md). The mode is an MCM setting, read here on the server when the button
-- is pressed; every game-state guard lives in Osiris (PROC_RJTP_RecruitAnytime), which reports one result.
local ANYTIME_NOTES = {
    OK        = { true,  "Raphael joins your party." },
    OK_CAMP   = { true,  "Your party is full: Raphael is waiting at your camp." },
    ALREADY   = { false, "Raphael is already with you." },
    WITHDRAWN = { false, "Raphael has left for good on this save." },
    BETRAYED  = { false, "Raphael has turned on you on this save; he cannot be recruited." },
    DISMISSED = { false, "You dismissed Raphael on this save; he cannot be recruited again." },
    OFFER     = { false, "His offer at the House of Hope portal is in progress; finish it first." },
    HOH       = { false, "Not while the House of Hope alarm is held: use the exit portal, where he makes his offer." },
    LEVEL     = { false, "Not available here (character creation or the nautiloid)." },
    ENDGAME   = { false, "Too late: the endgame has begun." },
    PLAYER    = { false, "Could not find your main character." },
    COMBAT    = { false, "Not during combat." },
    DIALOG    = { false, "Not during a dialogue." },
    NIGHT     = { false, "Not during a camp night." },
}

function O.Mode()
    local mcm = RJTP.Mcm()
    if mcm == nil or mcm.Get == nil then return nil end
    local ok, v = pcall(function() return mcm.Get(RJTP.S.MODE, ModuleUUID) end)
    return ok and v or nil
end

function O.RecruitAnytime()
    if not O.GameRunning() then return { ok = false, note = "Not in a running game." } end
    if O.Mode() ~= RJTP.MODE_ANYTIME then
        return { ok = false, note = "Story mode: Raphael offers to join at the House of Hope exit portal in Act 3. "
            .. "Switch the mode to 'Recruit anytime' to use this button." }
    end
    local okH, host = pcall(function() return Osi.GetHostCharacter() end)
    if not okH or host == nil or host == "" then return { ok = false, note = ANYTIME_NOTES.PLAYER[2] } end
    anytimeResult = nil
    local ok, err = pcall(function() Osi.PROC_RJTP_RecruitAnytime(host) end)
    if not ok then return { ok = false, note = "Osiris call failed: " .. tostring(err) } end
    local res = anytimeResult
    anytimeResult = nil
    local n = res and ANYTIME_NOTES[res] or nil
    if n == nil then
        return { ok = false, note = "Osiris did not confirm (" .. tostring(res) .. "); check whether he joined (see !rjtp_se)." }
    end
    return { ok = n[1], note = n[2], result = res }
end

function O.Ascend()
    local okG, why = gate()
    if not okG then return { ok = false, note = why } end
    if O.InCombat() == false then return { ok = false, note = "Ascend works only in combat." } end
    if O.Ascended() == true then return { ok = false, note = "He is already ascended. To switch between his two Ascended forms, use Infernal Guise on his spell bar." } end
    local r = O.Report()
    if r and r.heard and r.form == "Modded" then
        return { ok = false, note = "Switch from the modded form to a normal look first." }
    end
    -- Cast through the engine: action cost, cooldown and the Osiris guards (dialog, downed) all apply.
    local ok, err = pcall(function() Osi.UseSpell(C, RJTP.ASCEND_SPELL, C, C, 1) end)
    if not ok then return { ok = false, note = "Could not cast: " .. tostring(err) } end
    return { ok = true, note = "Ascend cast requested (needs his action and the spell's cooldown)." }
end

-- Osiris applies it in two phases (removes the current look, Transforms 300 ms later) and IGNORES the call
-- while he is ascended or during the camp night. Accepted = right after the call DB_RJTP_Form is "Modded" and
-- no ModdedForm row exists yet (the new template is still pending).
function O.ApplyModded(tpl)
    local okG, why = gate()
    if not okG then return { ok = false, note = why } end
    if O.Ascended() == true then return { ok = false, note = "Not while he is in his Ascended form." } end
    local ok, err = pcall(function() Osi.PROC_RJTP_ApplyModdedForm(C, tpl) end)
    if not ok then return { ok = false, note = "Osiris call failed: " .. tostring(err) } end
    local r = O.Report()
    if r == nil or not r.heard then
        return { ok = true, note = "Modded form requested (could not confirm it; see !rjtp_se)." }
    end
    if r.form == "Modded" and r.modded == nil then
        return { ok = true, note = "Modded form applied." }
    end
    return { ok = false, note = "The mod's story ignored it: that happens during his Ascended form or a camp night. Try again later." }
end

-- Auto-ascend is Osiris state (review 16 M6); the proc itself is gated on DB_RJTP_Recruited.
function O.SetAutoAscend(on)
    local okG, why = gate()
    if not okG then return { ok = false, note = why } end
    local ok, err = pcall(function() Osi.PROC_RJTP_SetAutoAscend(on and 1 or 0) end)
    if not ok then return { ok = false, note = "Could not change auto-ascend: " .. tostring(err) } end
    return { ok = true, note = "Auto-ascend " .. (on and "on" or "off") .. " for this save." }
end

-- v0.4a: a trait choice is Osiris state too (RJTP_Traits.txt). Not gated on being in the active party: Osiris keeps
-- the choice and applies it whenever he is recruited and not withdrawn (plan review S3).
function O.SetTrait(name, on)
    local ok, err = pcall(function() Osi.PROC_RJTP_SetTrait(name, on and 1 or 0) end)
    if not ok then return { ok = false, note = "Could not change trait " .. tostring(name) .. ": " .. tostring(err) } end
    return { ok = true, note = "Trait " .. tostring(name) .. (on and " on." or " off.") }
end

-- Party banter (release 1.0.0): on unless switched off; Osiris keeps the choice (RJTP_Banter.txt PROC_RJTP_SetBanter)
function O.SetBanter(on)
    local ok, err = pcall(function() Osi.PROC_RJTP_SetBanter(on and 1 or 0) end)
    if not ok then return { ok = false, note = "Could not change party banter: " .. tostring(err) } end
    return { ok = true, note = "Party banter " .. (on and "on." or "off.") }
end

-- Push every trait checkbox and the banter checkbox from MCM into the story (MCM is the authority; plan review S4).
-- Read only.
function O.PushTraits()
    local mcm = RJTP.Mcm()
    if mcm == nil or mcm.Get == nil then return end
    for id, name in pairs(RJTP.TRAITS) do
        local okG, v = pcall(function() return mcm.Get(id, ModuleUUID) end)
        if okG and type(v) == "boolean" then O.SetTrait(name, v) end
    end
    local okB, b = pcall(function() return mcm.Get(RJTP.S.BANTER, ModuleUUID) end)
    if okB and type(b) == "boolean" then O.SetBanter(b) end
end

-- Uninstall (release 1.0.0): the MCM button. Host only (WRITE_OPS); not while Raphael or the host is in combat.
function O.Uninstall()
    if not O.GameRunning() then return { ok = false, note = "Not in a running game." } end
    local okH, host = pcall(function() return Osi.GetHostCharacter() end)
    if not okH or host == nil or host == "" then return { ok = false, note = "Could not find your main character." } end
    if O.InCombat() == true then return { ok = false, note = "Not during combat." } end
    local okC, hostFighting = pcall(function() return Osi.IsInCombat(host) end)
    if okC and hostFighting == 1 then return { ok = false, note = "Not during combat." } end
    local ok, err = pcall(function() Osi.PROC_RJTP_Uninstall(host) end)
    if not ok then return { ok = false, note = "Osiris call failed: " .. tostring(err) } end
    return { ok = true, note = "Raphael Joins the Party is ready to remove: save the game, quit, then deactivate the mod." }
end

-- Current look for cycling: "Modded:<guid>", a look name, or nil if unknown.
function O.CurrentLookKey()
    local r = O.Report()
    if not (r and r.heard) then return nil end
    if r.form == "Modded" then return r.modded and ("Modded:" .. r.modded) or nil end
    return r.form
end

-- Uninstall guard (plan section 5.3): a stored modded form whose template no longer exists -> Wardrobe.
function O.UninstallGuard()
    local r = O.Report()
    if r == nil then return "report failed" end
    if not r.heard then return "not reported" end
    if r.modded == nil then return "none" end
    local okT, t = pcall(function() return Ext.Template.GetRootTemplate(r.modded) end)
    if okT and t ~= nil then return "present" end
    local ok, err = pcall(function() Osi.PROC_RJTP_SetForm(C, "Wardrobe") end)
    if ok then
        Ext.Utils.Print("[RJTP] Modded form " .. tostring(r.modded) .. " is no longer installed; reverted him to Wardrobe.")
        return "reverted"
    end
    Ext.Utils.Print("[RJTP] WARNING: modded form " .. tostring(r.modded) .. " is missing and the revert failed: " .. tostring(err))
    return "failed"
end
