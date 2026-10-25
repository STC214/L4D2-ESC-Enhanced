@echo off
setlocal
chcp 65001 >nul
title Evo / Model 卸载
set "EVO_UNINSTALL_SELF=%~f0"
set "EVO_UNINSTALL_MODE=%~1"
powershell.exe -NoProfile -Command "$t=[IO.File]::ReadAllText($env:EVO_UNINSTALL_SELF,[Text.Encoding]::UTF8); $p=$t -split '(?m)^# POWERSHELL-BODY\r?$',2; if($p.Count -ne 2){exit 1}; & ([scriptblock]::Create($p[1]))"
set "EVO_UNINSTALL_RESULT=%errorlevel%"
if /i not "%~1"=="/preview" if /i not "%~1"=="/preview-full" pause
exit /b %EVO_UNINSTALL_RESULT%
# POWERSHELL-BODY
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath([IO.Path]::GetDirectoryName($env:EVO_UNINSTALL_SELF)).TrimEnd('\')
$preview=$env:EVO_UNINSTALL_MODE -in @('/preview','/preview-full')
$previewFull=$env:EVO_UNINSTALL_MODE -eq '/preview-full'
$packageFiles=@(
 'winmm.dll',
 'bin\winmm.dll',
 'manifest.json',
 'updatelog.txt',
 'Evolved\d3d9.dll',
 'Evolved\config.sample',
 'Evolved\version.txt',
 'left4dead2\addons\mdR_Anims_Base_for_l4d2vr.vpk',
 'left4dead2\addons\killicon.vpk',
 'left4dead2\sound\vrmod\kill.wav',
 'left4dead2\sound\vrmod\hit.wav',
 'left4dead2\sound\vrmod\headshot.wav'
)
$legacyHelperDirs=@('evo_professor_physics','bin\neko\plugins\evo_professor_physics')
$dataDirs=@('Evolved','L4d2evomodel')+$legacyHelperDirs
$logFiles=@('winmm-loader.log','bin\winmm-loader.log')
$planned=New-Object 'System.Collections.Generic.List[string]'
$plannedDirs=New-Object 'System.Collections.Generic.List[string]'
$failures=New-Object 'System.Collections.Generic.List[string]'
function SafePath([string]$relative) {
 $path=[IO.Path]::GetFullPath((Join-Path $root $relative))
 if(-not $path.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)){throw "越界路径：$relative"}
 $cursor=$path
 while($cursor -and $cursor.Length -ge $root.Length){
  if(Test-Path -LiteralPath $cursor){
   if((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw "拒绝清理链接路径：$cursor"}
  }
  $cursor=[IO.Path]::GetDirectoryName($cursor)
 }
 return $path
}
function CheckTree([string]$relative){
 $path=SafePath $relative
 if(Test-Path -LiteralPath $path -PathType Container){
  $stack=New-Object 'System.Collections.Generic.Stack[string]';$stack.Push($path)
  while($stack.Count){
   $directory=$stack.Pop()
   foreach($item in Get-ChildItem -LiteralPath $directory -Force){
    if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw "数据目录含链接，停止：$($item.FullName)"}
    if($item.PSIsContainer){$stack.Push($item.FullName)}
   }
  }
 }
}
try{
 Write-Host '卸载 Evo 和 Model：根目录、bin 及 bin\neko\plugins'
 Write-Host "位置：$root"
 $exe=SafePath 'left4dead2.exe'
 if(-not $preview -and -not(Test-Path -LiteralPath $exe -PathType Leaf)){throw '请将脚本放到含 left4dead2.exe 的游戏根目录'}
 if(-not $preview -and (Get-Process left4dead2 -ErrorAction SilentlyContinue)){throw '请先退出游戏，未删除文件'}
 if(Test-Path -LiteralPath $exe -PathType Leaf){
  $image=[Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($exe))
  if($image.Contains('L4D2Evolved.EntryPatch.v')){throw '检测到 EXE 入口补丁，请先用入口补丁工具的 restore 功能还原。本脚本不覆盖游戏 EXE，也未删除文件。'}
 }
 foreach($prefix in @('','bin\','bin\neko\plugins\')){
  foreach($name in @('L4D2Evolved.dll','L4D2Evolved.pdb','L4d2evomodel.dll','L4d2evomodel.pdb','L4D2ModelRuntime.dll','L4D2ModelRuntime.pdb','EvoProfessorPrediction.exe','L4D2MeshCacheHost.exe','L4D2FrameGenerationHost.exe')){
   $relative=$prefix+$name
   if(Test-Path -LiteralPath (SafePath $relative) -PathType Leaf){$planned.Add($relative)}
  }
 }
 foreach($relative in $packageFiles){
  if(Test-Path -LiteralPath (SafePath $relative) -PathType Leaf){$planned.Add($relative)}
 }
 foreach($dir in $legacyHelperDirs){
  foreach($name in @('EvoProfessorPrediction.exe','PositionBasedDynamics-LICENSE.txt','Eigen-LICENSE.txt')){
   $relative=$dir+'\'+$name
   if(Test-Path -LiteralPath (SafePath $relative) -PathType Leaf){$planned.Add($relative)}
  }
 }
 if($preview){$choice=if($previewFull){'2'}else{'1'}}else{
  Write-Host '1：卸载程序，保留设置、模型锚点、旧解算配置和日志（默认）'
  Write-Host '2：完整卸载，同时删除本游戏的 Evo / Model 数据、旧解算目录和加载日志'
  $choice=Read-Host '请选择 1 或 2，回车为 1，其他输入取消'
  if($choice -eq ''){$choice='1'}
 }
 if($choice -notin @('1','2')){Write-Host '已取消';exit 0}
 if($choice -eq '2'){
  foreach($relative in $logFiles){if(Test-Path -LiteralPath (SafePath $relative) -PathType Leaf){$planned.Add($relative)}}
  foreach($dir in $dataDirs){CheckTree $dir;if(Test-Path -LiteralPath (SafePath $dir) -PathType Container){$plannedDirs.Add($dir)}}
 }
 Write-Host '将删除文件：';$planned | ForEach-Object{Write-Host "  $_"}
 if($plannedDirs.Count){Write-Host '将完整删除目录（包括其中设置、锚点和日志）：';$plannedDirs | ForEach-Object{Write-Host "  $_"}}
 Write-Host '保留 L4N 核心和其他插件、根目录 d3d9.dll、VR 共享目录、其他 VPK、下载压缩包，以及跨安装共用的 helper 缓存。'
 if($preview){Write-Host "仅预览模式 $choice，未修改文件。/preview-full 可查看完整卸载范围。";exit 0}
 if((Read-Host '确认永久删除上述内容？输入 Y 继续') -ne 'Y'){Write-Host '已取消';exit 0}
 if(Get-Process left4dead2 -ErrorAction SilentlyContinue){throw '游戏已启动，卸载取消'}
 foreach($relative in $planned){
  try{
   $path=SafePath $relative
   if(-not(Test-Path -LiteralPath $path -PathType Leaf)){continue}
   Remove-Item -LiteralPath $path -Force
   if(Test-Path -LiteralPath $path){throw '删除后仍存在'}
   Write-Host "[已删除] $relative"
  }catch{$failures.Add("$relative : $($_.Exception.Message)")}
 }
 if($choice -eq '2'){
  foreach($dir in $plannedDirs){
   try{
    CheckTree $dir;$path=SafePath $dir
    if(Test-Path -LiteralPath $path -PathType Container){
     Remove-Item -LiteralPath $path -Recurse -Force
     if(Test-Path -LiteralPath $path){throw '目录仍存在'}
     Write-Host "[已删除目录] $dir"
    }
   }catch{$failures.Add("$dir : $($_.Exception.Message)")}
  }
 }
 if($failures.Count){Write-Host '未完全卸载：';$failures | ForEach-Object{Write-Host "[失败] $_"};exit 1}
 Write-Host '卸载完成。'
 if($choice -eq '1'){Write-Host '设置、模型锚点、旧解算配置和日志已保留；选 2 可一并删除。'}
 exit 0
}catch{Write-Host "[停止] $($_.Exception.Message)";exit 1}
