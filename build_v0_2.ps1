# Raphael Joins the Party - build script (release 1.0.0 and test builds)
# Regenerates data, runs static checks, stages, converts, packs dist\RaphaelJoinsTheParty.pak and writes a manifest.
# Never deletes anything: each build stages into a fresh build\stage_<timestamp> folder, and an existing
# dist\RaphaelJoinsTheParty.pak is copied to build\prev_pak_<timestamp>.pak before it is overwritten.
# Does NOT install to the game's Mods folder.
#
# Shipping formats (verified against vanilla and WW mods):
#   * Globals, Flags, Tags, Soundbanks: .lsf (as v0.1; Globals also keep the .lsx, as WW Aylin ships both)
#   * Public/<mod>/RootTemplates/*.lsx -> .lsf only (vanilla Public/*/RootTemplates/_merged.lsf; WW Mizora
#     RootTemplates/_merged.lsf, WW Aylin RootTemplates/<uuid>.lsf)
#   * Public/<mod>/Content/**/*.lsx -> .lsf only (vanilla Content/[PAK]_CharacterVisuals/_merged.lsf; WW Mizora
#     Content/[PAK]_CharacterVisuals/5cc8d840-....lsf). This also covers dialog / timeline banks under Content.
#   * Public/<mod>/Shapeshift/Rulebook.lsx: shipped as .lsx (vanilla Public/GustavDev/Shapeshift/Rulebook.lsx)
#   * Mods/<mod>/Story/Dialogs/**/*.lsj: copied as-is; each also gets Story/DialogsBinary/<same path>.lsf unless the
#     source already has one (vanilla ships Mods/Shared/Story/Dialogs/...lsj + Story/DialogsBinary/...lsf)
#   * Mods/<mod>/Story/DialogsBinary/**/*.lsx|.lsj: converted to .lsf
#   * Mods/<mod>/ScriptExtender/** and Mods/<mod>/MCM_blueprint.json: copied as-is when present
param([ValidateSet('', 'S1b', 'VoiceDiag')][string]$Variant = '')
$ErrorActionPreference = 'Stop'
$root   = $PSScriptRoot
$divine = 'C:\bg3-sidecar-work\Tools\Divine.exe'
$ids    = Get-Content "$root\src\ids.json" -Raw | ConvertFrom-Json
$modFolder = "RaphaelJoinsTheParty_$($ids.MOD)"
$stamp  = Get-Date -Format 'yyyyMMdd_HHmmss'
$stage  = "$root\build\stage_$stamp"
$pak    = "$root\dist\RaphaelJoinsTheParty.pak"
$env:RJTP_VARIANT = $Variant  # read by tools\gen_data.py
if ($Variant -eq 'S1b') { $pak = "$root\dist\RaphaelJoinsTheParty_S1b.pak" }
# VoiceDiag: a PRIVATE diagnostic pak (it carries one copied Larian .wem); never distribute it.
if ($Variant -eq 'VoiceDiag') { $pak = "$root\dist\RaphaelJoinsTheParty_VoiceDiag.pak" }
$srcRoot = "$root\src\"

function Step($m) { Write-Host "== $m" }
function Convert-Res($from, $to) {
    New-Item -ItemType Directory -Force -Path (Split-Path -LiteralPath $to) | Out-Null
    & $divine -g bg3 -a convert-resource -s $from -d $to | Out-Null
    if (-not (Test-Path -LiteralPath $to)) { throw "convert failed: $from" }
}

Step 'bark / banter content table (line ids resolved against the line dumps)'
python "$root\tools\gen_banter_content.py"; if ($LASTEXITCODE) { throw 'gen_banter_content failed' }

Step 'camp dialog timeline (unmodified copy of the vanilla CAMP_Volo timeline; node map, scene, TimelineBank)'
# Must run BEFORE gen_dialogs: the camp dialog takes its node UUIDs from src\timeline_donor_map.json.
python "$root\tools\gen_timelines.py"; if ($LASTEXITCODE) { throw 'gen_timelines failed' }

Step 'generate dialogs (spec -> .lsj -> DialogsBinary .lsf, bank, flags, Gossips.lsx, goal facts, dialog_loca.json)'
# Review 20 S3: always regenerate, so a spec edit can never ship stale .lsj/.lsf. v0.2b NOTE: once the Toolkit has
# written TimelineIds into the .lsj, the timeline IDs must go into src\dialogs_spec.json first, or this step would
# overwrite them.
python "$root\tools\gen_dialogs.py"; if ($LASTEXITCODE) { throw 'gen_dialogs failed' }

Step 'generate data'
python "$root\tools\gen_data.py"; if ($LASTEXITCODE) { throw 'gen_data failed' }

Step 'Osiris lint'
python "$root\tools\osiris_lint.py" "$root\src\Mods\$modFolder\Story\RawFiles\Goals" "$root\build\lint_report.txt"
if ($LASTEXITCODE) { throw 'Osiris lint failed - see build\lint_report.txt' }

Step 'Osiris story compile check (LSLib StoryCompiler; orphan DBs are fatal in game)'
python "$root\tools\story_compile_check.py" "$root\src\Mods\$modFolder\Story\RawFiles\Goals" "$root\build\storycheck"
if ($LASTEXITCODE) { throw 'story compile check failed - see build\storycheck\story_compile_last.txt' }

Step 'Osiris story compile with the REAL compiler (Toolkit Osiris.dll, the author''s load order captured 2026-10-01)'
python "$root\tools\story_dll_check.py" "$root\build\story_base_noRJTP_20261001.div" "$root\src\Mods\$modFolder\Story\RawFiles\Goals" "$root\build\storydll" | Tee-Object -FilePath "$root\build\storydll_report.txt"
if ($LASTEXITCODE) { throw 'Osiris.dll story compile failed - see build\storydll_report.txt' }

Step 'stats / loca / GUID check'
python "$root\tools\check_stats.py" "$root\build\stats_report.txt"
if ($LASTEXITCODE) { throw 'stats check failed - see build\stats_report.txt' }

Step 'source parse check'
python "$root\tools\check_lsx.py" "$root\src"; if ($LASTEXITCODE) { throw 'source parse check failed' }

# Files that are converted instead of copied (binary-only resource types)
# 2026-10-04: the re-keyed voice bank is NEVER packed. The companion speaks under vanilla Raphael's speaker id, so the
# game uses Larian's own bank and audio. The bank .lsx stays in src only because tools\gen_dialogs.py checks every
# NPC line handle against it.
function Is-Excluded($rel) {
    return ($rel -match '\\Soundbanks\\[^\\]+\.lsx$')
}

function Is-ConvertOnly($rel) {
    return ($rel -match '\\(Flags|Tags)\\[^\\]+\.lsx$') -or
           ($rel -match '\\Soundbanks\\[^\\]+\.lsx$') -or
           ($rel -match '^Public\\[^\\]+\\RootTemplates\\.+\.lsx$') -or
           ($rel -match '^Public\\[^\\]+\\Content\\.+\.lsx$') -or
           ($rel -match '^Mods\\[^\\]+\\Story\\DialogsBinary\\.+\.(lsx|lsj)$') -or
           ($rel -match '^Mods\\[^\\]+\\Localization\\[^\\]+\.lsx$')   # v0.3e message-box keys (as vanilla .lsf)
}

Step "stage -> $stage"
New-Item -ItemType Directory -Force $stage | Out-Null
foreach ($top in 'Mods', 'Public') {
    Get-ChildItem "$root\src\$top" -Recurse -File | ForEach-Object {
        $rel = $_.FullName.Substring($srcRoot.Length)
        if ((Is-ConvertOnly $rel) -or (Is-Excluded $rel)) { return }
        $dst = Join-Path $stage $rel
        New-Item -ItemType Directory -Force -Path (Split-Path -LiteralPath $dst) | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $dst
    }
}

Step 'goal files -> CRLF, UTF-8 without BOM (as vanilla)'
$utf8 = New-Object System.Text.UTF8Encoding($false)
Get-ChildItem "$stage\Mods\$modFolder\Story\RawFiles\Goals" -Filter *.txt | ForEach-Object {
    $txt = [IO.File]::ReadAllText($_.FullName) -replace "`r?`n", "`r`n"
    [IO.File]::WriteAllText($_.FullName, $txt, $utf8)
}

Step 'convert -> lsf (Globals, Flags, Tags, Soundbanks, RootTemplates, Content banks, DialogsBinary)'
$converted = 0
Get-ChildItem "$root\src" -Recurse -File | Where-Object { $_.Extension -in '.lsx', '.lsj' } | ForEach-Object {
    $rel = $_.FullName.Substring($srcRoot.Length)
    $isGlobal = $rel -match '\\Globals\\.+\.lsx$'
    if (Is-Excluded $rel) { return }
    if ($isGlobal -or (Is-ConvertOnly $rel)) {
        $dstRel = $rel -replace '\.(lsx|lsj)$', '.lsf'
        Convert-Res $_.FullName (Join-Path $stage $dstRel)
        $converted++
    }
}
# Dialogs: .lsj source -> DialogsBinary .lsf when the source has no binary of its own
$dlgRoot = "$root\src\Mods\$modFolder\Story\Dialogs"
if (Test-Path $dlgRoot) {
    Get-ChildItem $dlgRoot -Recurse -File -Filter *.lsj | ForEach-Object {
        $sub = $_.FullName.Substring($dlgRoot.Length + 1) -replace '\.lsj$', ''
        $binSrc = "$root\src\Mods\$modFolder\Story\DialogsBinary\$sub"
        if (-not ((Test-Path -LiteralPath "$binSrc.lsf") -or (Test-Path -LiteralPath "$binSrc.lsx") -or (Test-Path -LiteralPath "$binSrc.lsj"))) {
            Convert-Res $_.FullName "$stage\Mods\$modFolder\Story\DialogsBinary\$sub.lsf"
            $converted++
        }
    }
}
if ($Variant -eq 'VoiceDiag') {
    # Two banks that say different sentences for the test line (tools\make_voice_diag.py explains why)
    $wemName = (python "$root\tools\make_voice_diag.py" $root | Select-Object -Last 1).Trim()
    if ($LASTEXITCODE) { throw 'make_voice_diag failed' }
    $sbDir = "$stage\Mods\$modFolder\Localization\English\Soundbanks"
    New-Item -ItemType Directory -Force $sbDir | Out-Null
    Convert-Res "$root\build\voicediag\bank_modfolder.lsx" "$sbDir\95a854c917cc477483f0ce6bf93924e2.lsf"
    Copy-Item -LiteralPath "$root\build\voicediag\$wemName" -Destination "$sbDir\$wemName"
    $converted++
}
Write-Host "   $converted file(s) converted"

Step 'localization: english.xml -> .loca (xml also kept, as WW mods ship it)'
$locaDir = "$stage\Localization\English"
New-Item -ItemType Directory -Force $locaDir | Out-Null
& $divine -g bg3 -a convert-loca -s "$root\src\Mods\$modFolder\Localization\English\english.xml" -d "$locaDir\RaphaelJoinsTheParty.loca" | Out-Null
if (-not (Test-Path "$locaDir\RaphaelJoinsTheParty.loca")) { throw 'loca conversion failed' }

Step 'stage parse check'
python "$root\tools\check_lsx.py" $stage; if ($LASTEXITCODE) { throw 'stage parse check failed' }
if (Select-String -Path "$stage\Mods\$modFolder\meta.lsx" -Pattern 'ScriptExtender|Script Extender' -Quiet) {
    throw 'meta.lsx mentions Script Extender (it must never be a dependency)'
}

Step "pack -> $pak"
New-Item -ItemType Directory -Force "$root\dist" | Out-Null
if (Test-Path $pak) {
    $prev = "$root\build\prev_pak_$stamp.pak"
    Copy-Item -LiteralPath $pak -Destination $prev
    Write-Host "   previous pak kept as $prev"
}
& $divine -g bg3 -a create-package -s $stage -d $pak | Out-Null
if (-not (Test-Path $pak)) { throw 'pack failed' }

Step 'manifest'
$list = & $divine -g bg3 -a list-package -s $pak
# Guard (review 2026-10-04): outside the private VoiceDiag variant the pak carries NO voice bank and NO audio,
# and the speaker id in the data must be the one the SE layer enforces.
if ($Variant -ne 'VoiceDiag') {
    $bad = @($list | Where-Object { $_ -match 'Soundbanks/|\.wem' })
    if ($bad.Count) { throw "pak contains voice bank or audio files: $($bad -join '; ')" }
}
# Guard (v0.3a): exactly the one copied timeline + its scene; the timeline must be byte-identical to the donor.
$tl = @($list | Where-Object { $_ -match 'Timeline/Generated/' } | ForEach-Object { ($_ -split "`t")[0] } | Sort-Object)
$tlWant = @("Public/$modFolder/Timeline/Generated/RJTP_CAMP_Raphael.lsf", "Public/$modFolder/Timeline/Generated/RJTP_CAMP_Raphael_Scene.lsf") | Sort-Object
if (($tl -join '|') -ne ($tlWant -join '|')) { throw "unexpected timeline files in the pak: $($tl -join '; ')" }
$donorHash = (Get-FileHash "$root\_vanilla_ref\timeline_donor\CAMP_Volo.lsf" -Algorithm SHA256).Hash
$oursHash  = (Get-FileHash "$stage\Public\$modFolder\Timeline\Generated\RJTP_CAMP_Raphael.lsf" -Algorithm SHA256).Hash
if ($donorHash -ne $oursHash) { throw 'the staged camp timeline is not byte-identical to the donor timeline' }
if (-not ($list | Where-Object { $_ -match "Public/$modFolder/Gossips/Gossips\.lsx" })) { throw 'Gossips.lsx is missing from the pak' }
$spkData = [regex]::Match((Get-Content "$root\tools\gen_data.py" -Raw), 'VOICE_SPEAKER = "([0-9a-f-]{36})"').Groups[1].Value
$spkLua  = [regex]::Match((Get-Content "$root\src\Mods\$modFolder\ScriptExtender\Lua\Shared\RJTP_Shared.lua" -Raw), 'RJTP\.VANILLA_RAPHAEL = "([0-9a-f-]{36})"').Groups[1].Value
if (-not $spkData -or $spkData -ne $spkLua) { throw "voice speaker id differs: gen_data '$spkData' vs Lua '$spkLua'" }
$hash = (Get-FileHash $pak -Algorithm SHA256).Hash
$size = (Get-Item $pak).Length
$manifest = @(
    "Raphael Joins the Party 1.0.0"
    "built:  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    "pak:    $pak"
    "size:   $size bytes"
    "sha256: $hash"
    "stage:  $stage"
    ""
    "contents:"
) + $list
$manifest | Out-File -Encoding utf8 "$root\build\build_manifest_v0_2$Variant.txt"
Write-Host "OK  $pak  $size bytes  SHA256 $hash"
