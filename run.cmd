@echo off
setlocal
set "ROOT_DIR=%~dp0"

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  python "%ROOT_DIR%src\dfm_cli.py" %*
  exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 "%ROOT_DIR%src\dfm_cli.py" %*
  exit /b %ERRORLEVEL%
)

echo Python 3 is required to run cnc-dfm.
exit /b 1
