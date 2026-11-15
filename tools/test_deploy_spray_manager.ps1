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
    Copy-Item -LiteralPath 'D:\tools\01_Game_tools\spray_importer_go\CSP_Spray_Manager.exe' -Destination $Old
}
$OldHash = (Get-FileHash -LiteralPath $Old).Hash
Copy-Item -LiteralPath $Old -Destination (Join-Path $Production 'CSP_Spray_Manager.exe')
[IO.File]::WriteAllBytes((Join-Path $Data 'fixture.bin'),[byte[]](1,2,3,4))
function Run-Step([string]$Action) {
    & powershell.exe -NoProfile -File $Script -Action $Action -ProductionRoot $Production -ReportDirectory $Report
    if ($LASTEXITCODE -ne 0) { throw "Deployment fixture $Action failed." }
}
Run-Step 'Install'
$First = Get-Content -LiteralPath (Join-Path $Report 'deployment.json') -Raw -Encoding UTF8 | ConvertFrom-Json
Run-Step 'Install'
$Again = Get-Content -LiteralPath (Join-Path $Report 'deployment.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($First.backup -ne $Again.backup) { throw 'Repeat install replaced the rollback record.' }
Run-Step 'Verify'
Run-Step 'Rollback'
Run-Step 'Verify'
if ((Get-FileHash -LiteralPath (Join-Path $Production 'CSP_Spray_Manager.exe')).Hash -ne $OldHash) { throw 'Fixture rollback hash mismatch.' }
if ([BitConverter]::ToString([IO.File]::ReadAllBytes((Join-Path $Data 'fixture.bin'))) -ne '01-02-03-04') { throw 'Fixture data changed.' }
Write-Output ('PASS deployment syntax, install, idempotency, installed PE check, exact rollback, data preservation; '+$Case)
