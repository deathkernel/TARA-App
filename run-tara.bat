@echo off
setlocal
cd /d "%~dp0"

rem Check tracked project files only; recursive findstr can scan .venv and match separator text.
git grep -n -I -E "^(<<<<<<<|=======|>>>>>>>)" -- pyproject.toml src tests >nul 2>nul
if not errorlevel 1 (
  echo ERROR: Unresolved Git conflict markers were found in tracked project files.
  git grep -n -I -E "^(<<<<<<<|=======|>>>>>>>)" -- pyproject.toml src tests
  echo Resolve every conflict, save the files, and run run-tara.bat again.
  exit /b 1
)
if errorlevel 2 (
  echo ERROR: Could not inspect tracked project files for merge-conflict markers.
  echo Verify that Git is installed and this folder is a valid Git repository.
  exit /b 1
)

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

".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info < (3, 15) else 1)"
if errorlevel 1 (
  echo Skipping optional Voice transcription dependencies on Python 3.15 or newer.
) else (
  ".venv\Scripts\python.exe" -m pip install -e ".[voice]"
  if errorlevel 1 (
    echo Voice transcription dependencies are unavailable; the rest of TARA-App will continue.
  )
)

if not exist "tara-app.toml" (
  copy "tara-app.example.toml" "tara-app.toml" >nul
)

".venv\Scripts\python.exe" -m tara_app.handler_launcher prepare

".venv\Scripts\python.exe" -m tara_app --config "tara-app.toml"
set "TARA_EXIT_CODE=%errorlevel%"
endlocal & exit /b %TARA_EXIT_CODE%
