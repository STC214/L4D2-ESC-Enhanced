@echo off
start "" /wait "%~dp0manager\CSP_Spray_Manager.exe" --portable-install
exit /b %errorlevel%
