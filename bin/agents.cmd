@echo off
rem Entry point for the agents catalog CLI on Windows. Add this directory to PATH.
rem python -m imports from the working directory first, so run from the repository root.
setlocal
pushd "%~dp0.."
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m catalog %*
) else (
    python -m catalog %*
)
set "AGENTS_EXIT=%errorlevel%"
popd
exit /b %AGENTS_EXIT%
