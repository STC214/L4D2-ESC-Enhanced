param(
    [ValidateSet('Install','Rollback','Verify')][string]$Action = 'Verify',
    [string]$ProductionRoot = 'D:\tools\01_Game_tools\L4D2_tools\spray_importer_go',
    [string]$ReportDirectory
)
$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$ProductionRoot = [IO.Path]::GetFullPath($ProductionRoot).TrimEnd('\')
if ($ProductionRoot.Length -le 3) { throw 'A specific production directory is required.' }
if (-not $ReportDirectory) { $ReportDirectory = Join-Path $Root 'reports\spray_production_l4d2_tools' }
$ReportDirectory = [IO.Path]::GetFullPath($ReportDirectory)
if (-not $ReportDirectory.StartsWith($Root+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Report directory must stay inside workspace.' }
$Destination = Join-Path $ProductionRoot 'CSP_Spray_Manager.exe'
Write-Output "TARGET $Destination"
$Hasher=[Security.Cryptography.SHA256]::Create()
try { $LockKey=[BitConverter]::ToString($Hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($ProductionRoot.ToLowerInvariant()))).Replace('-','').Substring(0,16) } finally { $Hasher.Dispose() }
$Mutex=New-Object Threading.Mutex($false,('Local\CSPSprayDeploy_'+$LockKey))
$Owned=$false
try {
try { $Owned=$Mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $Owned=$true }
if (-not $Owned) { throw 'Another spray deployment/verification is active for this production directory.' }
function Assert-NoLinks([string]$Path) {
    for ($At = [IO.Path]::GetFullPath($Path); $At; $At = [IO.Path]::GetDirectoryName($At)) {
        if ((Test-Path -LiteralPath $At) -and (([IO.File]::GetAttributes($At) -band [IO.FileAttributes]::ReparsePoint) -ne 0)) { throw 'Reparse path rejected.' }
    }
}
Assert-NoLinks $ProductionRoot
Assert-NoLinks $ReportDirectory
New-Item -ItemType Directory -Force -Path $ReportDirectory | Out-Null
$RecordPath = Join-Path $ReportDirectory 'deployment.json'
Assert-NoLinks $RecordPath
function Snapshot-Data {
    $Data = Join-Path $ProductionRoot 'CSP_Spray_Data'
    $Result = @{}
    if (-not (Test-Path -LiteralPath $Data)) { return $Result }
    $Queue = New-Object 'Collections.Generic.Queue[string]'
    $Queue.Enqueue($Data)
    while ($Queue.Count) {
        $Path = $Queue.Dequeue()
        $Item = Get-Item -LiteralPath $Path -Force
        if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Data snapshot rejects links; no deployment performed.' }
        $Relative = $Path.Substring($ProductionRoot.Length)
        if ($Item.PSIsContainer) {
            $Result[$Relative] = 'DIRECTORY'
            foreach ($Child in Get-ChildItem -LiteralPath $Path -Force) { $Queue.Enqueue($Child.FullName) }
        } else { $Result[$Relative] = (Get-FileHash -LiteralPath $Path).Hash }
    }
    return $Result
}
function Assert-SameData($Before,$After) {
    if ($Before.Count -ne $After.Count) { throw 'Production data entry count changed.' }
    foreach ($Key in $Before.Keys) {
        if (-not $After.ContainsKey($Key) -or $Before[$Key] -ne $After[$Key]) { throw 'Production data changed.' }
    }
}
function Write-Record($Value) {
    Assert-NoLinks $RecordPath
    $Text = $Value | ConvertTo-Json -Depth 15
    $Stage = Join-Path $ReportDirectory ('.deploy-record-'+[guid]::NewGuid().ToString('N')+'.tmp')
    $Bytes = (New-Object Text.UTF8Encoding($false)).GetBytes($Text)
    try {
        $Stream = [IO.File]::Open($Stage,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        try { $Stream.Write($Bytes,0,$Bytes.Length); $Stream.Flush($true) } finally { $Stream.Dispose() }
        if ([IO.File]::ReadAllText($Stage) -cne $Text) { throw 'Deployment record stage readback failed.' }
        Get-Content -LiteralPath $Stage -Raw -Encoding UTF8 | ConvertFrom-Json | Out-Null
        if (Test-Path -LiteralPath $RecordPath) {
            $Backup = Join-Path $ReportDirectory ('record-before-'+[guid]::NewGuid().ToString('N')+'.json')
            [IO.File]::Replace($Stage,$RecordPath,$Backup)
        } else { [IO.File]::Move($Stage,$RecordPath) }
        if ([IO.File]::ReadAllText($RecordPath) -cne $Text) { throw 'Deployment record readback failed.' }
    } finally {
        if (Test-Path -LiteralPath $Stage) { Remove-Item -LiteralPath $Stage }
    }
}
function Read-Record {
    Assert-NoLinks $RecordPath
    $Value = Get-Content -LiteralPath $RecordPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($Value.production_root -ne $ProductionRoot -or $Value.destination -ne $Destination) { throw 'Deployment record target mismatch.' }
    if ($Value.status -notin @('PREPARED','INSTALLED','ROLLED_BACK')) { throw 'Unknown deployment status; recovery record retained.' }
    return $Value
}
. (Join-Path $Root 'native\spray_importer\promote.ps1')
. (Join-Path $PSScriptRoot 'spray_backup_retention.ps1')
if ($Action -ne 'Verify') {
    foreach ($Process in Get-Process -Name CSP_Spray_Manager -ErrorAction SilentlyContinue) {
        if ($Process.Path -and [IO.Path]::GetFullPath($Process.Path) -eq $Destination) { throw 'Close the production spray manager first; no process is terminated.' }
    }
}
$BeforeData = Snapshot-Data
if ($Action -eq 'Install') {
    $Build = Get-Content -LiteralPath (Join-Path $Root 'reports\spray_importer_go\verification.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($Build.version -ne '1.12.1' -or -not $Build.source_snapshot_matched) { throw 'Verified 1.12.1 build required.' }
    foreach ($Step in $Build.records) { if ($Step.exit_status -ne 0) { throw 'Build verification contains a failed step.' } }
    $Source = Join-Path $Root 'dist\spray_importer_go\CSP_Spray_Manager.exe'
    if ((Get-FileHash -LiteralPath $Source).Hash -ne $Build.exe_sha256) { throw 'Source product hash differs from build evidence.' }
    $BeforeHash = (Get-FileHash -LiteralPath $Destination).Hash
    $PreviousRecord = $null
    if (Test-Path -LiteralPath $RecordPath) {
        $Previous = Read-Record
        if ($Previous.status -eq 'PREPARED') { throw 'Pending production deployment; preserve its recovery record.' }
        if ($Previous.status -eq 'INSTALLED') {
            if ($Previous.production_root -eq $ProductionRoot -and $Previous.destination -eq $Destination -and $Previous.after_sha256 -eq $Build.exe_sha256 -and $BeforeHash -eq $Build.exe_sha256) {
                Write-Output 'PASS Install already completed; original rollback record retained.'
                exit 0
            }
            if ($Previous.production_root -ne $ProductionRoot -or $Previous.destination -ne $Destination -or $BeforeHash -ne $Previous.after_sha256) {
                throw 'Production EXE differs from previous deployment; preserve its recovery record.'
            }
            $History = Join-Path $ReportDirectory 'history'
            Assert-NoLinks $History
            New-Item -ItemType Directory -Force -Path $History | Out-Null
            $PreviousRecord = Join-Path $History ('deployment-'+[guid]::NewGuid().ToString('N')+'.json')
            $RecordHash = (Get-FileHash -LiteralPath $RecordPath).Hash
            Copy-Item -LiteralPath $RecordPath -Destination $PreviousRecord
            if ((Get-FileHash -LiteralPath $PreviousRecord).Hash -ne $RecordHash) { throw 'Previous deployment history backup failed.' }
        }
    }
    $Backup = Join-Path $ProductionRoot ('.release-backups\'+[guid]::NewGuid().ToString('N')+'\before.exe')
    $Stage = Join-Path $ProductionRoot ('.deploy-'+[guid]::NewGuid().ToString('N')+'.exe')
    $Record = @{status='PREPARED';production_root=$ProductionRoot;destination=$Destination;before_sha256=$BeforeHash;after_sha256=$Build.exe_sha256;backup=$Backup;data_before=$BeforeData;source=$Source;version=$Build.version;previous_record=$PreviousRecord}
    Write-Record $Record
    try {
        Copy-Item -LiteralPath $Source -Destination $Stage
        $Record.promotion = Set-VerifiedProduct $ProductionRoot $Stage $Destination $Backup $Build.exe_sha256
        Assert-SameData $BeforeData (Snapshot-Data)
        $Record.status = 'INSTALLED'
        $Record.data_preserved = $true
        Write-Record $Record
    } finally {
        if (Test-Path -LiteralPath $Stage) { Remove-Item -LiteralPath $Stage }
    }
} elseif ($Action -eq 'Rollback') {
    $Record = Read-Record
    if ($Record.production_root -ne $ProductionRoot -or $Record.destination -ne $Destination) { throw 'Deployment record target mismatch.' }
    if ((Get-FileHash -LiteralPath $Destination).Hash -ne $Record.after_sha256) { throw 'Production EXE changed; rollback stopped.' }
    if ((Get-FileHash -LiteralPath $Record.backup).Hash -ne $Record.before_sha256) { throw 'Original backup hash mismatch.' }
    $Saved = Join-Path $ProductionRoot ('.release-backups\'+[guid]::NewGuid().ToString('N')+'\saved-new.exe')
    $Result = Set-VerifiedProduct $ProductionRoot $Record.backup $Destination $Saved $Record.before_sha256
    Assert-SameData $BeforeData (Snapshot-Data)
    $Record.status = 'ROLLED_BACK'
    $Record | Add-Member -NotePropertyName rollback -NotePropertyValue $Result -Force
    Write-Record $Record
} else {
    $Record = Read-Record
    if ($Record.status -notin @('INSTALLED','ROLLED_BACK')) { throw 'Pending deployment is not a verified installed state.' }
    if ($Record.production_root -ne $ProductionRoot -or $Record.destination -ne $Destination) { throw 'Deployment record target mismatch.' }
    $Expected = if ($Record.status -eq 'ROLLED_BACK') { $Record.before_sha256 } else { $Record.after_sha256 }
    if ((Get-FileHash -LiteralPath $Destination).Hash -ne $Expected) { throw 'Installed EXE hash mismatch.' }
    $IconReport = Join-Path $ReportDirectory ('icon-'+[guid]::NewGuid().ToString('N')+'.json')
    $Info = New-Object Diagnostics.ProcessStartInfo
    $Info.FileName = $Destination
    $Info.Arguments = '--verify-icon "'+(Join-Path $Root 'native\spray_importer\assets\app.ico')+'" "'+$IconReport+'"'
    $Info.UseShellExecute = $false
    $Info.CreateNoWindow = $true
    $Child = [Diagnostics.Process]::Start($Info)
    if (-not $Child.WaitForExit(20000)) { throw 'Installed EXE verification timed out.' }
    $Code = $Child.ExitCode
    $Child.Dispose()
    $Icon = Get-Content -LiteralPath $IconReport -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($Code -ne 0 -or $Icon.status -ne 'PASS' -or $Icon.exe_sha256 -ne $Expected) { throw 'Installed EXE/icon mismatch.' }
    Assert-SameData $BeforeData (Snapshot-Data)
    if ($Record.status -eq 'INSTALLED') {
        Remove-SupersededSprayExeBackups -ProductionRoot $ProductionRoot -Keep $Record.backup -Expected $Record.before_sha256
    }
}
Write-Output ('PASS '+$Action+'; production data preserved; EXE SHA256='+(Get-FileHash -LiteralPath $Destination).Hash)
} finally {
    if ($Owned) { $Mutex.ReleaseMutex() }
    $Mutex.Dispose()
}
