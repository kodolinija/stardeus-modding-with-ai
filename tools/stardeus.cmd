@echo off
rem Runs the workspace tools with the first Python 3.10+ found (py -3, python, or python3).
setlocal
for %%P in ("py -3" "python" "python3") do (
    %%~P -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && (
        %%~P "%~dp0stardeus.py" %*
        exit /b
    )
)
echo Python 3.10 or newer is needed: https://www.python.org/downloads/ (tick "Add python.exe to PATH") 1>&2
exit /b 127
