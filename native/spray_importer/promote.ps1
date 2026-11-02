function Set-VerifiedProduct {
    param([string]$Root,[string]$Candidate,[string]$Destination,[string]$Backup,[string]$Expected)
    $Root = [IO.Path]::GetFullPath($Root).TrimEnd('\')
    foreach ($Path in @($Candidate,$Destination,$Backup)) {
        $Full = [IO.Path]::GetFullPath($Path)
        if (-not $Full.StartsWith($Root + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Promotion target outside project root.' }
        $At = $Full
        while ($At) {
            if (Test-Path -LiteralPath $At) {
                if (([IO.File]::GetAttributes($At) -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Promotion path contains a reparse point.' }
            }
            $At = [IO.Path]::GetDirectoryName($At)
        }
    }
    if ($Candidate -eq $Destination -or $Candidate -eq $Backup -or $Backup -eq $Destination) { throw 'Promotion paths must be distinct.' }
    if ((Get-FileHash -LiteralPath $Candidate).Hash -ne $Expected) { throw 'Candidate hash mismatch; previous product kept.' }
    $BeforeHash = $null
    if (Test-Path -LiteralPath $Destination) {
        $BeforeHash = (Get-FileHash -LiteralPath $Destination).Hash
        New-Item -ItemType Directory -Force -Path (Split-Path $Backup) | Out-Null
        Copy-Item -LiteralPath $Destination -Destination $Backup
        if ((Get-FileHash -LiteralPath $Backup).Hash -ne $BeforeHash) { throw 'Previous product backup failed.' }
    }
    $Stage = Join-Path (Split-Path $Destination) ('.verified-' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        Copy-Item -LiteralPath $Candidate -Destination $Stage
        if ((Get-FileHash -LiteralPath $Stage).Hash -ne $Expected) { throw 'Promotion stage hash mismatch.' }
        if ($BeforeHash) {
            if ((Get-FileHash -LiteralPath $Destination).Hash -ne $BeforeHash) { throw 'Product changed before promotion.' }
            # Use an explicit backup path: PowerShell 5 converts a null string
            # argument to an empty path for this overload on some systems.
            [IO.File]::Replace($Stage,$Destination,$Backup)
        } else {
            [IO.File]::Move($Stage,$Destination)
        }
    } finally {
        if (Test-Path -LiteralPath $Stage) { [IO.File]::Delete($Stage) }
    }
    if ((Get-FileHash -LiteralPath $Destination).Hash -ne $Expected) { throw 'Promoted product readback mismatch; backup retained.' }
    return @{candidate=$Candidate;before_sha256=$BeforeHash;backup=$Backup;after_sha256=$Expected}
}
