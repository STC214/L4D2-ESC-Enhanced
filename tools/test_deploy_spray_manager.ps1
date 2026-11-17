$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Script = Join-Path $PSScriptRoot 'deploy_spray_manager.ps1'
$Tokens = $null
$Errors = $null
[Management.Automation.Language.Parser]::ParseFile($Script,[ref]$Tokens,[ref]$Errors) | Out-Null
if ($Errors.Count) { throw ($Errors | Out-String) }
$Case = Join-Path $Root ('reports\spray_production_test\'+[guid]::NewGuid().ToString('N'))
$Production = Join-Path $Case 'production'
$Report = Join-Path $Case 'report'
$Data = Join-Path $Production 'CSP_Spray_Data'
New-Item -ItemType Directory -Force -Path $Data | Out-Null
$Old = Join-Path $Root 'reports\spray_release_review\baseline\production-before.exe'
if (-not (Test-Path -LiteralPath $Old)) {
    Copy-Item -LiteralPath 'D:\tools\01_Game_tools\L4D2_tools\spray_importer_go\CSP_Spray_Manager.exe' -Destination $Old
}
$OldHash = (Get-FileHash -LiteralPath $Old).Hash
Copy-Item -LiteralPath $Old -Destination (Join-Path $Production 'CSP_Spray_Manager.exe')
[IO.File]::WriteAllBytes((Join-Path $Data 'fixture.bin'),[byte[]](1,2,3,4))
New-Item -ItemType Directory -Force -Path $Report | Out-Null
$Legacy = @{status='INSTALLED';production_root=$Production;destination=(Join-Path $Production 'CSP_Spray_Manager.exe');after_sha256=$OldHash;version='previous-fixture-version'}
[IO.File]::WriteAllText((Join-Path $Report 'deployment.json'),($Legacy|ConvertTo-Json),(New-Object Text.UTF8Encoding($false)))
function Run-Step([string]$Action) {
    & powershell.exe -NoProfile -File $Script -Action $Action -ProductionRoot $Production -ReportDirectory $Report
    if ($LASTEXITCODE -ne 0) { throw "Deployment fixture $Action failed." }
}
Run-Step 'Install'
$First = Get-Content -LiteralPath (Join-Path $Report 'deployment.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not (Test-Path -LiteralPath $First.previous_record)) { throw 'Previous version deployment record was not archived.' }
Run-Step 'Install'
$Again = Get-Content -LiteralPath (Join-Path $Report 'deployment.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($First.backup -ne $Again.backup) { throw 'Repeat install replaced the rollback record.' }
Run-Step 'Verify'
$Stale = Join-Path $Production '.release-backups\superseded'
New-Item -ItemType Directory -Force -Path $Stale | Out-Null
Copy-Item -LiteralPath $Old -Destination (Join-Path $Stale 'before.exe')
Copy-Item -LiteralPath $Old -Destination (Join-Path $Stale 'saved-new.exe')
Run-Step 'Verify'
if (Test-Path -LiteralPath $Stale) { throw 'Superseded EXE backups retained.' }
if ((Get-FileHash -LiteralPath $First.backup).Hash -ne $OldHash) { throw 'Latest rollback backup removed.' }
$InstalledText = [IO.File]::ReadAllText((Join-Path $Report 'deployment.json'))
function Expect-Rejected([string]$Action) {
    $Info = New-Object Diagnostics.ProcessStartInfo
    $Info.FileName='powershell.exe'
    $Info.Arguments='-NoProfile -NonInteractive -File "'+$Script+'" -Action '+$Action+' -ProductionRoot "'+$Production+'" -ReportDirectory "'+$Report+'"'
    $Info.UseShellExecute=$false; $Info.CreateNoWindow=$true
    $Info.RedirectStandardOutput=$true; $Info.RedirectStandardError=$true
    $Child=[Diagnostics.Process]::Start($Info)
    $ErrorTask=$Child.StandardError.ReadToEndAsync()
    $Output=$Child.StandardOutput.ReadToEnd(); $Child.WaitForExit()
    $Code=$Child.ExitCode; $ErrorText=$ErrorTask.Result; $Child.Dispose()
    if ($Code -eq 0) { throw ('Invalid deployment record accepted by '+$Action+': '+$Output) }
}
$Hasher=[Security.Cryptography.SHA256]::Create()
try { $LockKey=[BitConverter]::ToString($Hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($Production.ToLowerInvariant()))).Replace('-','').Substring(0,16) } finally { $Hasher.Dispose() }
$Lock=New-Object Threading.Mutex($false,('Local\CSPSprayDeploy_'+$LockKey))
if (-not $Lock.WaitOne(0)) { throw 'Fixture lock is unexpectedly occupied.' }
try { Expect-Rejected 'Verify' } finally { $Lock.ReleaseMutex();$Lock.Dispose() }
foreach ($Status in @('PREPARED','UNKNOWN')) {
    $Bad=$InstalledText|ConvertFrom-Json
    $Bad.status=$Status
    $BadText=$Bad|ConvertTo-Json -Depth 15
    [IO.File]::WriteAllText((Join-Path $Report 'deployment.json'),$BadText,(New-Object Text.UTF8Encoding($false)))
    Expect-Rejected 'Verify'
    Expect-Rejected 'Install'
    if ([IO.File]::ReadAllText((Join-Path $Report 'deployment.json')) -cne $BadText) { throw 'Rejected record was overwritten.' }
    if ((Get-FileHash -LiteralPath (Join-Path $Production 'CSP_Spray_Manager.exe')).Hash -ne $First.after_sha256) { throw 'Rejected operation changed product.' }
}
[IO.File]::WriteAllText((Join-Path $Report 'deployment.json'),$InstalledText,(New-Object Text.UTF8Encoding($false)))
Run-Step 'Rollback'
Run-Step 'Verify'
if (@(Get-ChildItem -LiteralPath $Report -Filter 'record-before-*.json').Count -lt 2) { throw 'Atomic record backups missing.' }
foreach ($Saved in Get-ChildItem -LiteralPath $Report -Filter 'record-before-*.json') {
    Get-Content -LiteralPath $Saved.FullName -Raw -Encoding UTF8|ConvertFrom-Json|Out-Null
}
if (@(Get-ChildItem -LiteralPath $Report -Filter '.deploy-record-*.tmp' -Force).Count) { throw 'Temporary record stage retained.' }
if ((Get-FileHash -LiteralPath (Join-Path $Production 'CSP_Spray_Manager.exe')).Hash -ne $OldHash) { throw 'Fixture rollback hash mismatch.' }
if ([BitConverter]::ToString([IO.File]::ReadAllBytes((Join-Path $Data 'fixture.bin'))) -ne '01-02-03-04') { throw 'Fixture data changed.' }
Write-Output ('PASS deployment syntax, mutex rejection, pending/unknown-state rejection, atomic record backups/readback, install/idempotency/PE check, exact rollback and data preservation; '+$Case)
