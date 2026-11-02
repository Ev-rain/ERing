@echo off
setlocal
cd /d "%~dp0"

rem Install PyInstaller only when missing: the build must never hang silently on the network.
echo [1/4] check PyInstaller ...
".venv\Scripts\python.exe" -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
  echo       not installed, installing from mirror ...
  ".venv\Scripts\python.exe" -m pip install --no-input --disable-pip-version-check --timeout 15 --retries 1 --index-url https://mirrors.cloud.tencent.com/pypi/simple/ pyinstaller
  if errorlevel 1 (
    echo [ERROR] PyInstaller install failed.
    echo         Common cause: Watt Toolkit / Steam++ proxy intercepting HTTPS.
    echo         Quit the accelerator and run build.bat again.
    pause
    exit /b 1
  )
)

rem Collect rapidocr data only if rapidocr_onnxruntime is installed.
set RAPID_COLLECT=
".venv\Scripts\python.exe" -c "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('rapidocr_onnxruntime') else 1)" >nul 2>&1
if %errorlevel%==0 set RAPID_COLLECT=--collect-data rapidocr_onnxruntime

echo [2/4] stamp build info ...
".venv\Scripts\python.exe" tools\stamp_build_info.py

echo [3/4] packaging with PyInstaller ^(Qt runtime is large, usually 1-3 minutes^) ...
".venv\Scripts\pyinstaller.exe" --noconfirm --clean --windowed --name ERing ^
  --icon src\ERing\app\assets\tray.ico ^
  --add-data "src\ERing\app\assets;assets" ^
  --add-data "src\ERing\native\wheelhook.dll;native" ^
  %RAPID_COLLECT% ^
  --collect-submodules uiautomation ^
  --hidden-import app.build_info ^
  src\ERing\main.py
if errorlevel 1 (
  echo [ERROR] PyInstaller failed, see the messages above.
  pause
  exit /b 1
)

rem PyInstaller may collect ICU DLLs from third-party apps on PATH and break QtCore.
for %%f in (dist\ERing\_internal\icu*.dll) do if exist "%%f" del "%%f"

echo [4/4] done.
echo.
echo Build complete: dist\ERing\ERing.exe
echo NOTE: recording needs ffmpeg.exe in native\ffmpeg\ next to the exe (or on PATH).
endlocal
pause
