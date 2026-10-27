-- RJTP SE layer, SERVER: detection of Raphael forms added by other mods (research 15 section 2.2; plan 5.3).
-- ON DEMAND ONLY (the MCM tab is opened, Rescan is pressed, or the cycle hotkey needs the list). One pass,
-- no Tick, result cached for the session.
--
-- Algorithm: walk the character root templates once; resolve each one's CharacterVisualResourceID (following
-- ParentTemplateId when the field is empty, so parent-inherited visuals are not missed - review 16 M7); look the
-- visual up once (memoised) and keep it if its BaseVisual or one of its slot visuals is one of Raphael's.
-- The skeleton class comes from that match. DEMON-skeleton candidates are EXCLUDED in v0.2: a display-only
-- transform onto another skeleton breaks his class animations, and the combat-only guarantees belong to
-- RJTP_FORM_ASCENDED (research 15 section 2.2 step 5; review 16 M7). The server validates again on Apply.

RJTP = RJTP or {}
local D = {}
RJTP.Detect = D

-- Raphael's base visuals and heads -> skeleton class (full GUIDs resolved from the vanilla extracts in
-- _vanilla_ref\forms\ ; research 15 section 2.2 step 1)
local BASES = {
    ["fc86cc9a-57e6-3e4a-e2fe-ba65497d73dc"] = "HUM",      -- HUM_M_RAPHAEL_Base
    ["cc5a80b8-53c7-bffa-8ce6-ec4e50ca70a9"] = "CAMBION",  -- CAMBION_M_RAPHAEL_Base
    ["20009054-c40e-7809-7345-f7093bd6f0a6"] = "DEMON",    -- DEMON_Raphael_Base
}
local HEADS = {
    ["925e51a1-4f87-cbac-e9f0-922ff50f7f8d"] = "HUM",      -- human head
    ["0165a0a4-a221-258c-38c4-595c98769630"] = "CAMBION",  -- Cambion Raphael head
    ["96f89dbb-3fcf-fc0d-9637-3c7b557d2599"] = "DEMON",    -- Demon Raphael head
}
-- Vanilla visuals (and our own) that already have a form or are not his: never offered.
local SKIP_VISUALS = {
    ["dc5589d3-5f3b-0ac4-ef9d-88c34dd85f9c"] = true, -- S_GLO_Monitor human (our Signature form)
    ["fd95c042-a48c-f72e-7e31-5e5530fa121e"] = true, -- devil form (our Devil form)
    ["7b5c3c88-4302-21e6-d2bd-855df3a961f6"] = true, -- S_GLO_Monitor_HUM_Shapeshifter_FX
    ["5deb7984-ca09-3c34-3d73-33362845b1c1"] = true, -- dummies
    ["3c501bce-8e5a-258a-abad-a68b61cb4574"] = true,
    ["ccdd5479-8c86-0e39-dd1e-487f9241d730"] = true,
    ["04bb7981-0d6d-4d41-91e8-54ace7b3a33c"] = true,
    ["45719593-64b2-bfd5-f15f-93ea77934993"] = true,
    ["150b2403-6cb5-85a3-0b2e-e8814268422d"] = true, -- civilians using the head
    ["4390bba5-2b86-28d8-04f1-10f643a8b6c9"] = true,
    ["bf8c5cd9-c0fd-4533-84eb-5f4687be427f"] = true, -- RJTP_Raphael_Wardrobe (ours)
}
local SKIP_TEMPLATES = {
    ["1f9da419-8224-42e8-894a-8907cb978360"] = true, -- devil
    ["f5e9cb22-70c4-46ba-bff8-ed9fe8dfb1c8"] = true, -- Ascended Fiend
    ["001b64f6-4918-4045-8197-878cf263e893"] = true, -- x2 devil
    ["4877074c-bfd1-4ba5-9c8a-be33a3640e81"] = true, -- QUEST_Monitor_Incubus
    ["acd7060a-43bd-4dc9-b050-9d9b2cf7b7df"] = true, -- S_GLO_Monitor parent
    ["b9c43f26-8210-4ebc-82d7-21d01b46eef7"] = true, -- RJTP_Raphael_SuitForm (ours)
    ["b94a1acd-bf4c-45f0-95ea-027fa0438773"] = true, -- RJTP_Raphael_WardrobeForm (ours)
}
-- Larian module folders: templates from these are base game, not "forms from other mods".
local LARIAN_FOLDERS = {
    Gustav = true, GustavDev = true, GustavX = true, Shared = true, SharedDev = true,
    Honour = true, HonourX = true, MainUI = true, ModBrowser = true, Engine = true, Game = true,
}
-- Friendly labels for known mods (research 15 section 2.2 step 3); shown only when that mod is loaded.
local KNOWN = {
    { prefix = "54a3ae4c", mod = "e2761c2f-2713-4c40-fb98-b68a02c0e0f4", label = "Crowned Archdevil (Inferna Victoria)" },
}
local MAX_CANDIDATES = 100 -- keeps the reply far below SE's 1 MB net-message cap

D.cache = nil      -- { list = {...}, byId = {...}, ms = n, stats = {...} }

local function field(obj, name)
    local ok, v = pcall(function() return obj[name] end)
    if ok then return v end
    return nil
end

-- FixedString, or an OverrideableProperty pushed as a table/userdata with .Value
local function fs(v)
    if v == nil then return nil end
    local tv = type(v)
    if tv == "string" then return v end
    if tv == "table" or tv == "userdata" then
        local inner = field(v, "Value")
        if inner ~= nil then return tostring(inner) end
    end
    return tostring(v)
end

local function guid(s)
    s = fs(s)
    if s == nil or s == "" then return nil end
    if #s >= 36 then return string.lower(string.sub(s, -36)) end
    return string.lower(s)
end

local function folderFromFileName(fn)
    fn = fs(fn)
    if not fn or fn == "" then return nil end
    fn = string.gsub(fn, "\\", "/")
    return string.match(fn, "Public/([^/]+)/") or string.match(fn, "Mods/([^/]+)/")
end

local function modNamesByFolder()
    local map = {}
    pcall(function()
        for _, uuid in ipairs(Ext.Mod.GetLoadOrder() or {}) do
            local m = Ext.Mod.GetMod(uuid)
            local info = m and m.Info
            if info and info.Directory then map[tostring(info.Directory)] = tostring(info.Name or info.Directory) end
        end
    end)
    return map
end

local function isModLoaded(uuid)
    local ok, v = pcall(function() return Ext.Mod.IsModLoaded(uuid) end)
    return ok and v == true
end

-- visual id -> class string, or false (memoised per scan)
local function classifyVisual(vis, memo)
    local c = memo[vis]
    if c ~= nil then return c end
    c = false
    local ok, r = pcall(function() return Ext.Resource.Get(vis, "CharacterVisual") end)
    if ok and r ~= nil then
        local base = guid(field(r, "BaseVisual"))
        if base and BASES[base] then
            c = BASES[base]
        else
            local set = field(r, "VisualSet")
            local slots = set and field(set, "Slots")
            if slots then
                pcall(function()
                    for i = 1, #slots do
                        local vr = guid(field(slots[i], "VisualResource"))
                        if vr and HEADS[vr] then c = HEADS[vr] break end
                    end
                end)
            end
        end
    end
    memo[vis] = c
    return c
end

local function resolveVisual(t, all, depth)
    local v = guid(field(t, "CharacterVisualResourceID"))
    if v then return v end
    if depth >= 6 then return nil end
    local parent = fs(field(t, "ParentTemplateId"))
    if not parent or parent == "" then return nil end
    local p = all[parent]
    if p == nil then
        local ok, pt = pcall(function() return Ext.Template.GetRootTemplate(parent) end)
        p = ok and pt or nil
    end
    if p == nil then return nil end
    return resolveVisual(p, all, depth + 1)
end

function D.Scan()
    local t0 = RJTP.Now()
    local stats = { templates = 0, characters = 0, matched = 0, demon = 0, vanilla = 0, unattributed = 0 }
    local list, byId = {}, {}
    local ownDir = nil
    pcall(function() ownDir = tostring(Ext.Mod.GetMod(ModuleUUID).Info.Directory) end)
    local okAll, all = pcall(function() return Ext.Template.GetAllRootTemplates() end)
    if not okAll or type(all) ~= "table" and type(all) ~= "userdata" then
        D.cache = { list = list, byId = byId, ms = RJTP.Now() - t0, stats = stats, error = tostring(all) }
        return D.cache
    end
    local memo, names = {}, nil
    local okLoop, errLoop = pcall(function()
        for id, t in pairs(all) do
            stats.templates = stats.templates + 1
            local tt = fs(field(t, "TemplateType"))
            if tt and string.lower(tt) == "character" then
                stats.characters = stats.characters + 1
                local tid = guid(field(t, "Id")) or guid(id)
                local vis = resolveVisual(t, all, 0)
                if tid and vis and not SKIP_TEMPLATES[tid] and not SKIP_VISUALS[vis] then
                    local class = classifyVisual(vis, memo)
                    if class then
                        stats.matched = stats.matched + 1
                        local folder = folderFromFileName(field(t, "FileName"))
                        local known = nil
                        for _, k in ipairs(KNOWN) do
                            if string.sub(tid, 1, #k.prefix) == k.prefix and isModLoaded(k.mod) then known = k end
                        end
                        -- FAIL CLOSED (review S4): offer a template only when its source is a known, non-Larian,
                        -- non-RJTP mod folder, or it is on the hand-checked KNOWN list. DEMON is always excluded.
                        if class == "DEMON" then
                            stats.demon = stats.demon + 1
                        elseif known == nil and folder == nil then
                            stats.unattributed = stats.unattributed + 1
                        elseif known == nil and (LARIAN_FOLDERS[folder] or string.match(folder, "^DiceSet_")
                                or folder == ownDir) then
                            stats.vanilla = stats.vanilla + 1
                        elseif #list < MAX_CANDIDATES then
                            names = names or modNamesByFolder()
                            local name = fs(field(t, "TemplateName")) or tid
                            if name == "" then name = tid end
                            local mod = folder and (names[folder] or folder) or "?"
                            if known then name = known.label end
                            local c = { id = tid, name = name, mod = mod, skel = class }
                            list[#list + 1] = c
                            byId[tid] = c
                        end
                    end
                end
            end
        end
    end)
    table.sort(list, function(a, b) return (a.name .. a.id) < (b.name .. b.id) end)
    -- unique display labels (used by the dynamic enum on MCM builds that support it)
    local seen = {}
    for _, c in ipairs(list) do
        local label = c.name .. " [" .. c.mod .. "]"
        if seen[label] then label = label .. " #" .. string.sub(c.id, 1, 8) end
        seen[label] = true
        c.label = label
    end
    D.cache = { list = list, byId = byId, ms = RJTP.Now() - t0, stats = stats,
                error = (not okLoop) and tostring(errLoop) or nil }
    return D.cache
end

function D.Get(force)
    if force or D.cache == nil then return D.Scan() end
    return D.cache
end

-- Server-side validation for an Apply request: in this session's candidate list and still a root template.
function D.Validate(tpl)
    tpl = guid(tpl)
    if not tpl then return false, "No template." end
    local cache = D.Get(false)
    if not cache.byId[tpl] then return false, "Not a detected Raphael form (press Rescan)." end
    local ok, t = pcall(function() return Ext.Template.GetRootTemplate(tpl) end)
    if not ok or t == nil then return false, "That form's mod is no longer loaded." end
    return true, tpl
end
