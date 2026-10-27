-- Raphael Joins the Party - optional Script Extender layer, server bootstrap (plan v0.2 section 5).
-- Everything the mod needs works without Script Extender (spells + Osiris). This layer only adds the MCM page,
-- hotkeys and forms from other mods, and it only ever calls the mod's Osiris procs.
Ext.Require("Shared/RJTP_Shared.lua")
Ext.Require("Server/RJTP_Osiris.lua")
Ext.Require("Server/RJTP_Detect.lua")
Ext.Require("Server/RJTP_Server.lua")
Ext.Utils.Print("[RJTP] Raphael Joins the Party SE layer " .. RJTP.BUILD .. " loaded (server).")
