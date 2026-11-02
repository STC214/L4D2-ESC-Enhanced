$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'promote.ps1')
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$Work = Join-Path $Root ('reports\spray_importer_go\promotion-tests\' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $Work | Out-Null
$Candidate = Join-Path $Work 'candidate.bin'
$Destination = Join-Path $Work 'product.bin'
$Backup = Join-Path $Work 'before.bin'
[IO.File]::WriteAllBytes($Candidate,[byte[]](1,2,3,4))
[IO.File]::WriteAllBytes($Destination,[byte[]](8,9,10))
$Expected = (Get-FileHash -LiteralPath $Candidate).Hash
$Before = (Get-FileHash -LiteralPath $Destination).Hash
$Failed = $false
try { Set-VerifiedProduct $Root $Candidate $Destination $Backup ('0' * 64) | Out-Null } catch { $Failed = $true }
if (-not $Failed -or (Get-FileHash -LiteralPath $Destination).Hash -ne $Before) { throw 'Bad candidate changed the product.' }
$Lock = [IO.File]::Open($Destination,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
$Failed = $false
try { Set-VerifiedProduct $Root $Candidate $Destination $Backup $Expected | Out-Null } catch { $Failed = $true } finally { $Lock.Dispose() }
if (-not $Failed -or (Get-FileHash -LiteralPath $Destination).Hash -ne $Before) { throw 'Locked product was changed.' }
$Result = Set-VerifiedProduct $Root $Candidate $Destination $Backup $Expected
if ((Get-FileHash -LiteralPath $Destination).Hash -ne $Expected -or (Get-FileHash -LiteralPath $Backup).Hash -ne $Before) { throw 'Promotion/backup readback mismatch.' }
Write-Output 'PASS 3 file-promotion fixtures: corrupt candidate, locked destination, success + exact backup'
