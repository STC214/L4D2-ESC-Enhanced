@echo off
start "" /wait "%~dp0CSP_Spray_Manager.exe" --portable-install
exit /b %errorlevel%
