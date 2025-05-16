@echo off

where uv >nul 2>nul
if %ERRORLEVEL%==0 (
    echo uv is installed
) else (
    echo uv is not installed
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
)

uv run main.py