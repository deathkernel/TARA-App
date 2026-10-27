@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 -m venv .venv
  ) else (
    python -m venv .venv
  )
  if errorlevel 1 (
    echo Could not create the TARA virtual environment. Install Python 3.11 or newer first.
    exit /b 1
  )
)

".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 (
  echo TARA-App installation failed.
  exit /b 1
)

if not exist "tara-app.toml" (
  copy "tara-app.example.toml" "tara-app.toml" >nul
)

".venv\Scripts\python.exe" -m tara_app.handler_launcher prepare

".venv\Scripts\python.exe" -m tara_app --config "tara-app.toml"
set "TARA_EXIT_CODE=%errorlevel%"
endlocal & exit /b %TARA_EXIT_CODE%
