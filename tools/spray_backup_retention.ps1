function Remove-SupersededSprayExeBackups {
    param([string]$ProductionRoot,[string]$Keep,[string]$Expected)
    $Base = [IO.Path]::GetFullPath((Join-Path $ProductionRoot '.release-backups')).TrimEnd('\')
    $Keep = [IO.Path]::GetFullPath($Keep)
    Write-Output "BACKUP RETENTION TARGET $Base; KEEP $Keep"
    if (-not $Keep.StartsWith($Base+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Rollback backup is not inside the backup directory.' }
    Assert-NoLinks $Base
    Assert-NoLinks $Keep
    if ((Get-FileHash -LiteralPath $Keep).Hash -ne $Expected) { throw 'Latest rollback backup hash mismatch; keep every older backup.' }
    $Candidates = [Collections.Generic.List[string]]::new()
    foreach ($Directory in Get-ChildItem -LiteralPath $Base -Directory -Force) {
        Assert-NoLinks $Directory.FullName
        foreach ($File in Get-ChildItem -LiteralPath $Directory.FullName -Force) {
            Assert-NoLinks $File.FullName
            if ($File.PSIsContainer -or $File.Name -notin @('before.exe','saved-new.exe')) { throw 'Unexpected backup entry; preserve it for inspection.' }
            $Resolved = [IO.Path]::GetFullPath($File.FullName)
            if (-not $Resolved.StartsWith($Base+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Backup cleanup path escaped its base.' }
            if ($Resolved -ne $Keep) { $Candidates.Add($Resolved) }
        }
    }
    # Validation above completes before the first deletion. Never recurse and
    # never touch source images, game recovery records, or the active backup.
    foreach ($Path in $Candidates) { Remove-Item -LiteralPath $Path -Force }
    foreach ($Directory in Get-ChildItem -LiteralPath $Base -Directory -Force) {
        if (@(Get-ChildItem -LiteralPath $Directory.FullName -Force).Count -eq 0) { [IO.Directory]::Delete($Directory.FullName) }
    }
    if ((Get-FileHash -LiteralPath $Keep).Hash -ne $Expected) { throw 'Latest rollback backup changed during cleanup.' }
    Write-Output ('PASS latest EXE rollback backup retained; superseded files removed='+$Candidates.Count)
}
