<#
 security-engineering installer for Windows PowerShell 5.1+ / PowerShell 7 (no admin rights, copy-based, no symlinks).
 Usage: ./install.ps1 -Mode global|project [-Tools claude,opencode,antigravity] [-ProjectDir DIR] [-DryRun] [-Force]
                      [-VendorSkills] [-AllowVersionChange] [-ClaudeDir D] [-OpenCodeDir D] [-AntigravityDir D] [-SharedDir D] [-Framework F]
 Same manifest format and semantics as install.sh. Exit codes: 0 ok, 3 conflicts, 4 version refusal.
#>
param(
  [Parameter(Mandatory)][ValidateSet('global','project')][string]$Mode,
  [string[]]$Tools, [string]$ProjectDir, [switch]$DryRun, [switch]$Force, [switch]$VendorSkills, [switch]$AllowVersionChange,
  [string]$ClaudeDir, [string]$OpenCodeDir, [string]$AntigravityDir, [string]$SharedDir, [string]$Framework = ''
)
$ErrorActionPreference = 'Stop'
$Src = Split-Path -Parent $PSScriptRoot
$Version = (Get-Content (Join-Path $Src 'VERSION') -Raw).Trim()
$Ts = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$HomeDir = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
$Conflicts = 0; $Actions = 0; $NewFiles = @{}; $Backups = @{}; $Blocks = @(); $Created = @(); $SchemaAdded = @()
function Say($m) { Write-Host $m }
function Act($m) { $script:Actions++; Say ("  " + $(if ($DryRun) { '[dry-run] ' } else { '' }) + $m) }
function Sha($p) { (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLower() }
function Utf8NoBom($path, $text) { [IO.File]::WriteAllText($path, $text, (New-Object Text.UTF8Encoding($false))) }

Say "security-engineering $Version · PowerShell $($PSVersionTable.PSVersion) · mode=$Mode dry_run=$DryRun"
if ($Mode -eq 'global') {
  if (-not $ClaudeDir) { $ClaudeDir = Join-Path $HomeDir '.claude' }
  if (-not $OpenCodeDir) { $OpenCodeDir = Join-Path (Join-Path $HomeDir '.config') 'opencode' }   # unverified on native Windows: override with -OpenCodeDir if your OpenCode uses another path
  if (-not $AntigravityDir) { $AntigravityDir = Join-Path (Join-Path $HomeDir '.gemini') 'config' }
  $RootState = Join-Path $HomeDir '.security-engineering'; if (-not $SharedDir) { $SharedDir = Join-Path $RootState 'shared' }; $InstallSkills = $true
} else {
  if (-not $ProjectDir) { throw '-ProjectDir required in project mode' }
  $ProjectDir = (Resolve-Path $ProjectDir).Path
  if (-not $ClaudeDir) { $ClaudeDir = Join-Path $ProjectDir '.claude' }
  if (-not $OpenCodeDir) { $OpenCodeDir = Join-Path $ProjectDir '.opencode' }
  if (-not $AntigravityDir) { $AntigravityDir = Join-Path $ProjectDir '.agents' }
  $RootState = Join-Path $ProjectDir '.security-engineering'; if (-not $SharedDir) { $SharedDir = Join-Path $RootState 'shared' }; $InstallSkills = [bool]$VendorSkills
}
$Manifest = Join-Path $RootState "manifest-$Mode.json"
if (-not $Tools) {
  if ($Mode -eq 'global') {
    $Tools = @(); if ((Test-Path $ClaudeDir) -or (Get-Command claude -ErrorAction SilentlyContinue)) { $Tools += 'claude' }
    if ((Test-Path $OpenCodeDir) -or (Get-Command opencode -ErrorAction SilentlyContinue)) { $Tools += 'opencode' }
    if ((Test-Path $AntigravityDir) -or (Get-Command agy -ErrorAction SilentlyContinue)) { $Tools += 'antigravity' }
  } else { $Tools = @('claude','opencode','antigravity') }
}
$Tools = @($Tools | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
if (-not $Tools) { Say 'no supported tool detected; pass -Tools'; exit 2 }
Say "tools: $($Tools -join ',')"
function Has($t) { $Tools -contains $t }

$Old = @{}; $PrevVersion = ''
if (Test-Path $Manifest) {
  $m = Get-Content $Manifest -Raw | ConvertFrom-Json; $PrevVersion = $m.version
  $m.files.PSObject.Properties | ForEach-Object { $Old[$_.Name] = $_.Value }
  if ($m.backups) { $m.backups.PSObject.Properties | ForEach-Object { $Backups[$_.Name] = $_.Value } }
  if ($m.blocks) { $Blocks = @($m.blocks) }
  if ($m.created) { $Created = @($m.created) }
  if ($m.json_schema_added) { $SchemaAdded = @($m.json_schema_added) }
  if ($PrevVersion -and ([version]$PrevVersion -gt [version]$Version) -and -not $AllowVersionChange) { Say "REFUSED: installed $PrevVersion is newer than source $Version (downgrade). Use -AllowVersionChange."; exit 4 }
}
$Pcfg = Join-Path $RootState 'config.yaml'
if ($Mode -eq 'project' -and (Test-Path $Pcfg)) {
  $pin = [regex]::Match((Get-Content $Pcfg -Raw), '(?m)^security_engineering_version:\s*"?([0-9][0-9.]*)"?').Groups[1].Value
  if ($pin -and $pin -ne $Version -and -not $AllowVersionChange) { Say "REFUSED: project pins $pin but source is $Version. Re-run with -AllowVersionChange to move the pin."; exit 4 }
}

function Install-File($s, $d) {
  $ss = Sha $s
  if (-not (Test-Path -LiteralPath $d)) { Act "copy  $d"; if (-not $DryRun) { New-Item -ItemType Directory -Force (Split-Path $d) | Out-Null; Copy-Item -LiteralPath $s -Destination $d }; $script:NewFiles[$d] = $ss; return }
  $ds = Sha $d
  if ($ds -eq $ss) { if ($Old.ContainsKey($d)) { $script:NewFiles[$d] = $ss } else { Say "  adopted (pre-existing, identical, left unmanaged): $d" }; return }
  if ($Old.ContainsKey($d) -and $Old[$d] -eq $ds) { Act "update $d"; if (-not $DryRun) { Copy-Item -LiteralPath $s -Destination $d -Force }; $script:NewFiles[$d] = $ss; return }
  if ($Force) { Act "backup+overwrite $d (-> $d.bak.$Ts)"; if (-not $DryRun) { Copy-Item -LiteralPath $d -Destination "$d.bak.$Ts"; Copy-Item -LiteralPath $s -Destination $d -Force }; $script:NewFiles[$d] = $ss; $script:Backups[$d] = "$d.bak.$Ts"; return }
  Say "CONFLICT $d exists and is not managed/unmodified by this installer (use -Force to back up and overwrite)"; $script:Conflicts++
}
function Install-Tree($from, $to) {
  $root = (Resolve-Path $from).Path
  Get-ChildItem -LiteralPath $root -Recurse -File | Sort-Object FullName | ForEach-Object { Install-File $_.FullName (Join-Path $to $_.FullName.Substring($root.Length).TrimStart('\','/')) }
}
function Install-Skills($target) { Get-ChildItem (Join-Path $Src 'skills') -Directory | ForEach-Object { Install-Tree $_.FullName (Join-Path $target $_.Name) } }

Say "shared resources -> $SharedDir"
foreach ($d in 'core','contracts','policies') { Install-Tree (Join-Path $Src $d) (Join-Path $SharedDir $d) }
Install-File (Join-Path $Src 'scripts/assessment-gate.py') (Join-Path $SharedDir 'scripts/assessment-gate.py')
Install-File (Join-Path $Src 'tests/lib/minischema.py') (Join-Path $SharedDir 'scripts/minischema.py')
if (Has 'claude') { Say 'claude-code'; if ($InstallSkills) { Install-Skills (Join-Path $ClaudeDir 'skills') }; Install-Tree (Join-Path $Src 'adapters/claude-code/agents') (Join-Path $ClaudeDir 'agents') }
if (Has 'opencode') {
  Say 'opencode'
  if ($InstallSkills) { if (Has 'claude') { Say '  skills: skipped (OpenCode also discovers Claude-compatible skill paths; avoids duplicates)' } else { Install-Skills (Join-Path $OpenCodeDir 'skills') } }
  Install-Tree (Join-Path $Src 'adapters/opencode/agents') (Join-Path $OpenCodeDir 'agents')
}
if (Has 'antigravity') {
  Say 'antigravity'; if ($InstallSkills) { Install-Skills (Join-Path $AntigravityDir 'skills') }
  Install-Tree (Join-Path $Src 'adapters/antigravity/agents') (Join-Path $AntigravityDir 'agents'); Install-Tree (Join-Path $Src 'adapters/antigravity/rules') (Join-Path $AntigravityDir 'rules')
}

function Sub-Template($p) { (Get-Content $p -Raw).Replace('{{VERSION}}', $Version).Replace('{{FRAMEWORK}}', $(if ($Framework) { $Framework } else { 'generic' })) }
function Set-ManagedBlock($file, $tpl) {
  $b = '<!-- security-engineering:begin -->'; $e = '<!-- security-engineering:end -->'
  $block = "$b`n$((Sub-Template $tpl).TrimEnd())`n$e"
  $exists = Test-Path $file; if (-not $exists -and ($script:Created -notcontains $file)) { $script:Created += $file }; $cur = if ($exists) { Get-Content $file -Raw } else { '' }
  if ($cur.Contains($b)) {
    $new = [regex]::Replace($cur, "(?s)$([regex]::Escape($b)).*?$([regex]::Escape($e))", { param($mm) $block })
    if ($new -eq $cur) { return }
    Act "update managed block in $file"
  } else { $new = $(if ($cur) { $cur.TrimEnd() + "`n`n" } else { '' }) + $block + "`n"; Act "append managed block to $file" }
  if (-not $DryRun) { if ($exists) { Copy-Item $file "$file.bak.$Ts" }; Utf8NoBom $file $new }
  if ($script:Blocks -notcontains $file) { $script:Blocks += $file }
}
if ($Mode -eq 'project') {
  if (-not $Framework) {
    $cj = Join-Path $ProjectDir 'composer.json'; $pj = Join-Path $ProjectDir 'package.json'
    $Framework = if ((Test-Path $cj) -and (Select-String -Path $cj -Pattern '"laravel/framework"' -Quiet)) { 'laravel' } elseif ((Test-Path $pj) -and (Select-String -Path $pj -Pattern '"@nestjs/core"' -Quiet)) { 'nestjs' } else { 'generic' }
  }
  Say "project integration (framework=$Framework)"
  if (-not (Test-Path $Pcfg)) { Act "create $Pcfg"; if (-not $DryRun) { New-Item -ItemType Directory -Force $RootState | Out-Null; Utf8NoBom $Pcfg (Sub-Template (Join-Path $Src 'adapters/project/config.yaml.template')) } }
  elseif ($AllowVersionChange) { Act "move pin in $Pcfg to $Version"; if (-not $DryRun) { Copy-Item $Pcfg "$Pcfg.bak.$Ts"; Utf8NoBom $Pcfg ([regex]::Replace((Get-Content $Pcfg -Raw), '(?m)^security_engineering_version:.*$', "security_engineering_version: `"$Version`"")) } }
  $pr = Join-Path $RootState 'PROJECT_RULES.md'
  if (-not (Test-Path $pr)) { Act "create $pr"; if (-not $DryRun) { New-Item -ItemType Directory -Force $RootState | Out-Null; Utf8NoBom $pr (Sub-Template (Join-Path $Src 'adapters/project/PROJECT_RULES.md.template')) } }
  if (Has 'claude') { Set-ManagedBlock (Join-Path $ProjectDir 'CLAUDE.md') (Join-Path $Src 'adapters/claude-code/CLAUDE.md.template') }
  if ((Has 'opencode') -or (Has 'antigravity')) { Set-ManagedBlock (Join-Path $ProjectDir 'AGENTS.md') (Join-Path $Src 'adapters/opencode/AGENTS.md.template') }
  if (Has 'opencode') {
    $oc = Join-Path $ProjectDir 'opencode.json'
    if (-not (Test-Path $oc)) { Act "create $oc"; if ($script:Created -notcontains $oc) { $script:Created += $oc }; if (-not $DryRun) { Copy-Item (Join-Path $Src 'adapters/opencode/opencode.json.template') $oc } }
    elseif (-not ((Select-String -Path $oc -Pattern 'security-engineering/PROJECT_RULES.md' -SimpleMatch -Quiet) -and (Select-String -Path $oc -Pattern '"$schema"' -SimpleMatch -Quiet))) {
      Act "merge instructions entry into $oc (other keys preserved; backup kept)"
      if (-not (Select-String -Path $oc -Pattern '"$schema"' -SimpleMatch -Quiet) -and ($script:SchemaAdded -notcontains $oc)) { $script:SchemaAdded += $oc }
      if (-not $DryRun) {
        Copy-Item $oc "$oc.bak.$Ts"; $j = Get-Content $oc -Raw | ConvertFrom-Json; $entry = '.security-engineering/PROJECT_RULES.md'
        if (-not $j.PSObject.Properties['instructions']) { $j | Add-Member -NotePropertyName instructions -NotePropertyValue @($entry) }
        elseif ($j.instructions -notcontains $entry) { $j.instructions = @($j.instructions) + $entry }
        if (-not $j.PSObject.Properties['$schema']) { $j | Add-Member -NotePropertyName '$schema' -NotePropertyValue 'https://opencode.ai/config.json' }
        Utf8NoBom $oc (($j | ConvertTo-Json -Depth 32) + "`n")
      }
    }
  }
}
if (-not $DryRun) {
  New-Item -ItemType Directory -Force $RootState | Out-Null
  $files = [ordered]@{}; foreach ($k in $Old.Keys) { $files[$k] = $Old[$k] }; foreach ($k in $NewFiles.Keys) { $files[$k] = $NewFiles[$k] }
  Utf8NoBom $Manifest ([ordered]@{ version = $Version; mode = $Mode; installed_at = $Ts; files = $files; blocks = @($Blocks); backups = $Backups; created = @($Created); json_schema_added = @($SchemaAdded) } | ConvertTo-Json -Depth 8)
  Say "manifest: $Manifest"
}
Say "done: $Actions action(s), $Conflicts conflict(s)$(if ($DryRun) { ' (dry-run: nothing written)' })"
if ($Conflicts -gt 0) { exit 3 }
