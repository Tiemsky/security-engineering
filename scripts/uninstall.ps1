<#
 Removes ONLY files recorded in the manifest that are still unmodified (same semantics as uninstall.sh).
 Usage: ./uninstall.ps1 -Mode global|project [-ProjectDir DIR] [-DryRun] [-RestoreBackups]
#>
param([Parameter(Mandatory)][ValidateSet('global','project')][string]$Mode, [string]$ProjectDir, [switch]$DryRun, [switch]$RestoreBackups)
$ErrorActionPreference = 'Stop'
$HomeDir = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
if ($Mode -eq 'global') { $RootState = Join-Path $HomeDir '.security-engineering' } else { if (-not $ProjectDir) { throw '-ProjectDir required' }; $ProjectDir = (Resolve-Path $ProjectDir).Path; $RootState = Join-Path $ProjectDir '.security-engineering' }
$Manifest = Join-Path $RootState "manifest-$Mode.json"
if (-not (Test-Path $Manifest)) { Write-Host "nothing to uninstall (no manifest at $Manifest)"; exit 0 }
# remove now-empty directories upward, never a tool root (.claude, .opencode, .agents, ...) nor anything above it
$Protected = @('.claude','.opencode','.agents','.gemini','.config','config','opencode','.security-engineering', (Split-Path $HomeDir -Leaf))
function Prune-Empty($d) { while ($d -and (Test-Path -LiteralPath $d) -and -not (Get-ChildItem -Force -LiteralPath $d) -and ($Protected -notcontains (Split-Path $d -Leaf))) { Remove-Item -LiteralPath $d; $d = Split-Path $d } }
function Run($m) { Write-Host ("  " + $(if ($DryRun) { '[dry-run] ' } else { '' }) + $m) }
$m = Get-Content $Manifest -Raw | ConvertFrom-Json; $removed = 0; $kept = 0
foreach ($p in $m.files.PSObject.Properties) {
  if (-not (Test-Path -LiteralPath $p.Name)) { continue }
  if ((Get-FileHash -Algorithm SHA256 -LiteralPath $p.Name).Hash.ToLower() -eq $p.Value) {
    Run "remove $($p.Name)"; $removed++
    if (-not $DryRun) { Remove-Item -LiteralPath $p.Name -Force; Prune-Empty (Split-Path $p.Name) }
  } else { Write-Host "  KEEP (modified since install) $($p.Name)"; $kept++ }
}
$b = '<!-- security-engineering:begin -->'; $e = '<!-- security-engineering:end -->'
foreach ($f in @($m.blocks)) {
  if (-not $f -or -not (Test-Path -LiteralPath $f)) { continue }
  Run "remove managed block from $f"
  if (-not $DryRun) {
    $new = [regex]::Replace((Get-Content -LiteralPath $f -Raw), "(?s)\r?\n?$([regex]::Escape($b)).*?$([regex]::Escape($e))\r?\n?", '')
    if ($new.Trim() -eq '' -and (@($m.created) -contains $f)) { Remove-Item -LiteralPath $f; Write-Host "  removed (created by installer, now empty) $f" }
    else { [IO.File]::WriteAllText($f, $new, (New-Object Text.UTF8Encoding($false))) }
  }
}
if ($Mode -eq 'project') {
  $oc = Join-Path $ProjectDir 'opencode.json'
  if (Test-Path $oc) {
    Run 'remove instructions entry from opencode.json'
    if (-not $DryRun) {
      $j = Get-Content $oc -Raw | ConvertFrom-Json; $entry = '.security-engineering/PROJECT_RULES.md'
      if ($j.PSObject.Properties['instructions']) { $j.instructions = @($j.instructions | Where-Object { $_ -ne $entry }); if ($j.instructions.Count -eq 0) { $j.PSObject.Properties.Remove('instructions') } }
      if (@($m.json_schema_added) -contains $oc -and $j.PSObject.Properties['$schema']) { $j.PSObject.Properties.Remove('$schema') }
      $left = @($j.PSObject.Properties.Name | Where-Object { $_ -ne '$schema' })
      if ((@($m.created) -contains $oc) -and $left.Count -eq 0) { Remove-Item $oc; Write-Host "  removed (created by installer, nothing else in it) $oc" }
      else { [IO.File]::WriteAllText($oc, (($j | ConvertTo-Json -Depth 32) + "`n"), (New-Object Text.UTF8Encoding($false))) }
    }
  }
}
if ($RestoreBackups -and $m.backups) { foreach ($p in $m.backups.PSObject.Properties) { if (Test-Path -LiteralPath $p.Value) { Run "restore $($p.Name) from $($p.Value)"; if (-not $DryRun) { Move-Item -LiteralPath $p.Value -Destination $p.Name -Force } } } }
if (-not $DryRun) { Remove-Item $Manifest }
Write-Host "done: removed $removed, kept $kept (project config.yaml/PROJECT_RULES.md are user-owned and left in place)"
