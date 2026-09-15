@echo off
setlocal
powershell.exe -NoProfile -File "%~dp0install_partme_blender_mcp.ps1" %*
exit /b %ERRORLEVEL%
