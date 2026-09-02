@echo off
setlocal
chcp 65001 >nul

cd /d "%~dp0"

set "APP_DIR=%CD%\market_checker_app"
if not exist "%APP_DIR%\model_v3\import_prices.py" (
  echo [CHYBA] Nenasel jsem model_v3 importer.
  pause
  exit /b 1
)

if not exist "%CD%\data" mkdir "%CD%\data"
set "DB_FILE=%CD%\data\model_v3_prices.db"

set "PYTHON_EXE="
if exist "%APP_DIR%\.venv\Scripts\python.exe" (
  set "PYTHON_EXE=%APP_DIR%\.venv\Scripts\python.exe"
) else (
  where py >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_EXE=py -3"
  ) else (
    set "PYTHON_EXE=python"
  )
)

for /f %%D in ('powershell -NoProfile -Command "(Get-Date).ToUniversalTime().ToString('yyyy-MM-dd')"') do set "SNAPSHOT_DATE=%%D"

echo.
echo ================================================
echo   JOHNY-SKORE Model V3 - import dat
echo ================================================
echo [INFO] Pouzivam Python: %PYTHON_EXE%
echo [INFO] Snapshot datum UTC: %SNAPSHOT_DATE%
echo [INFO] Zdroj: kompletni viditelny MT5 watchlist
echo [INFO] Benchmark: SPY
echo.

echo [INFO] Kontroluji zavislosti...
%PYTHON_EXE% -m pip install -r "%APP_DIR%\requirements.txt"
if errorlevel 1 (
  echo.
  echo [CHYBA] Instalace zavislosti selhala.
  pause
  exit /b 1
)

echo.
echo [INFO] Spoustim import. Okno nezavirej, dokud nedobehne.
%PYTHON_EXE% -m market_checker_app.model_v3.import_prices --mt5-watchlist --snapshot-date "%SNAPSHOT_DATE%" --db "%DB_FILE%"
set "IMPORT_ERROR=%ERRORLEVEL%"

echo.
if "%IMPORT_ERROR%"=="0" (
  echo [HOTOVO] Data jsou v: %DB_FILE%
) else if "%IMPORT_ERROR%"=="3" (
  echo [UPOZORNENI] Import dobehl, ale nektere tickery se nepodarilo nacist.
  echo Podrobnosti jsou vypsane vyse.
) else (
  echo [CHYBA] Import selhal. Podrobnosti jsou vypsane vyse.
)
echo.
pause
endlocal
