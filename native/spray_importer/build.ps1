param()
$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$Report = Join-Path $Root 'reports\spray_importer_go'
$Out = Join-Path $Root 'dist\spray_importer_go'
$env:GOTMPDIR = Join-Path $Root 'reports\go_tmp'
$env:TMP = $env:GOTMPDIR
$env:TEMP = $env:GOTMPDIR
$env:GOCACHE = Join-Path $Root 'reports\go_cache'
$env:CGO_ENABLED = '0'
$env:GOOS = 'windows'
$env:GOARCH = 'amd64'
New-Item -ItemType Directory -Force -Path $Report,$Out,$env:GOTMPDIR,$env:GOCACHE | Out-Null
$Asset = Join-Path $PSScriptRoot 'assets\selector.vpk'
$Base = Join-Path $Root 'dist\spray_selector_prototype\CSP_Numbered_Selector_TEST.vpk'
$Pin = 'DB23C3A7BA9AAAFF8A062C771B6C4755CBDC2D34B0BCCA21A499FA8F51904F67'
New-Item -ItemType Directory -Force -Path (Split-Path $Asset) | Out-Null
if (Test-Path -LiteralPath $Base) {
    if ((Get-FileHash -LiteralPath $Base).Hash -ne $Pin) { throw 'Re-establish the selector baseline before rebuilding.' }
    Copy-Item -LiteralPath $Base -Destination $Asset
}
if ((Get-FileHash -LiteralPath $Asset).Hash -ne $Pin) { throw 'Embedded resource copy mismatch.' }
$Records = [Collections.Generic.List[object]]::new()
Add-Type -AssemblyName System.Web.Extensions
Add-Type -ReferencedAssemblies ([psobject].Assembly.Location) -TypeDefinition @'
using System;
using System.Collections;
using System.Collections.Generic;
using System.Management.Automation;
public static class CSPBuildJson {
    public static object Plain(object value) {
        while (value is PSObject) value = ((PSObject)value).BaseObject;
        if (value == null || value is string || value is ValueType) return value;
        var dictionary = value as IDictionary;
        if (dictionary != null) {
            var clean = new Dictionary<string, object>();
            foreach (DictionaryEntry item in dictionary) clean.Add((string)item.Key, Plain(item.Value));
            return clean;
        }
        var sequence = value as IEnumerable;
        if (sequence != null) {
            var clean = new List<object>();
            foreach (object item in sequence) clean.Add(Plain(item));
            return clean.ToArray();
        }
        throw new InvalidOperationException("Unexpected report type: " + value.GetType().FullName);
    }
}
'@
$JsonWriter = New-Object System.Web.Script.Serialization.JavaScriptSerializer
$JsonWriter.MaxJsonLength = 16777216
function Write-ReportJson {
    param([string]$Path, [object]$Value)
    $Text = $JsonWriter.Serialize([CSPBuildJson]::Plain($Value))
    [IO.File]::WriteAllText($Path, $Text, [Text.UTF8Encoding]::new($false))
}
$GuardPaths = @(
    'E:\SteamLibrary\steamapps\common\Left 4 Dead 2\bin\gameui.dll',
    'E:\SteamLibrary\steamapps\common\Left 4 Dead 2\bin\neko\plugins\CSPSelector.dll',
    'E:\SteamLibrary\steamapps\common\Left 4 Dead 2\left4dead2\addons\CSP_Numbered_Selector_TEST.vpk'
)
$GameAddons = 'E:\SteamLibrary\steamapps\common\Left 4 Dead 2\left4dead2\addons'
if (Test-Path -LiteralPath $GameAddons) {
    $GuardPaths += @(Get-ChildItem -LiteralPath $GameAddons -Filter '*C_ESC_LED*.vpk' -File | Select-Object -ExpandProperty FullName)
}
$Before = @{}
foreach ($Path in $GuardPaths) {
    if (Test-Path -LiteralPath $Path) { $Before[$Path] = (Get-FileHash -LiteralPath $Path).Hash }
}
function Invoke-RecordedGo {
    param([string[]]$GoArgs)
    $Lines = & go @GoArgs 2>&1
    $Code = $LASTEXITCODE
    $Literal = ($Lines | ForEach-Object { $_.ToString() }) -join "`n"
    $Records.Add(@{ command = @('go') + $GoArgs; input = 'synthetic fixtures only'; output = $Literal; exit_status = $Code })
    $Literal
    if ($Code -ne 0) { throw "go exited $Code" }
}
Push-Location $PSScriptRoot
try {
    $GoFiles = @(Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.go' -File | Select-Object -ExpandProperty FullName)
    $Unformatted = & gofmt -l @GoFiles
    if ($LASTEXITCODE -ne 0 -or $Unformatted) { throw "Run gofmt first: $Unformatted" }
    Invoke-RecordedGo -GoArgs @('version')
    Invoke-RecordedGo -GoArgs @('test','-count=2','-v','./...')
    # The one LPARAM -> MINMAXINFO cast is a required Win32 callback ABI boundary.
    # All remaining vet analyzers stay enabled; the native smoke exercises that cast.
    Invoke-RecordedGo -GoArgs @('vet','-unsafeptr=false','./...')
    $Exe = Join-Path $Out 'CSP_Spray_Manager.exe'
    Invoke-RecordedGo -GoArgs @('build','-trimpath','-ldflags=-H=windowsgui -s -w -buildid=','-o',$Exe,'.')
    $Smoke = Join-Path $Report ('win32-smoke.' + [guid]::NewGuid().ToString('N') + '.json')
    Write-Output 'STAGE native-smoke-start'
    $StartInfo = New-Object Diagnostics.ProcessStartInfo
    $StartInfo.FileName = $Exe
    $StartInfo.Arguments = '--smoke "' + $Smoke + '"'
    $StartInfo.UseShellExecute = $false
    $StartInfo.CreateNoWindow = $true
    $Process = [Diagnostics.Process]::Start($StartInfo)
    if (-not $Process.WaitForExit(20000)) { throw 'Native smoke exceeded 20 seconds; inspect the window, do not auto-kill it.' }
    $SmokeCode = $Process.ExitCode
    $Process.Dispose()
    $Records.Add(@{ command = @($Exe,'--smoke',$Smoke); input = 'no user input'; exit_status = $SmokeCode; output = (Get-Content -LiteralPath $Smoke -Raw -Encoding utf8) })
    if ($SmokeCode -ne 0 -or (Get-Content -LiteralPath $Smoke -Raw | ConvertFrom-Json).status -ne 'PASS') { throw 'Native smoke failed.' }
    Copy-Item -LiteralPath $Smoke -Destination (Join-Path $Report 'win32-smoke.json')
    Write-Output 'STAGE native-smoke-pass'
    foreach ($Path in $Before.Keys) { if ((Get-FileHash -LiteralPath $Path).Hash -ne $Before[$Path]) { throw "Protected file changed: $Path" } }
    Write-Output 'STAGE protected-hashes-pass'
    $SourceHashes = @{}
    foreach ($Path in Get-ChildItem -LiteralPath $PSScriptRoot -File) { $SourceHashes[$Path.Name] = (Get-FileHash -LiteralPath $Path.FullName).Hash }
    Write-Output 'STAGE source-hashes-pass'
    $Result = @{status='TWO_GO_TEST_ROUNDS_AND_NATIVE_WIN32_SMOKE_PASS'; records=$Records.ToArray(); source_sha256=$SourceHashes; embedded_vpk_sha256=$Pin; exe=$Exe; exe_sha256=(Get-FileHash -LiteralPath $Exe).Hash; protected=$Before; real_game_deployment='NOT_PERFORMED'; manual_ui='PENDING'; vet_exception='unsafeptr: Win32 LPARAM to MINMAXINFO callback conversion; native ABI smoke required'; version='1.1.1'}
    Write-ReportJson -Path (Join-Path $Report 'verification.json') -Value $Result
    Write-Output "PASS: $Exe"
} finally {
    Write-ReportJson -Path (Join-Path $Report 'commands.json') -Value $Records.ToArray()
    Pop-Location
}
