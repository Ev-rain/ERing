@echo off
setlocal
cd /d "%~dp0"

rem Make sure pyinstaller is available in the project venv.
".venv\Scripts\python.exe" -m pip install pyinstaller >nul 2>&1

rem Collect rapidocr data only if rapidocr_onnxruntime is installed.
set RAPID_COLLECT=
".venv\Scripts\python.exe" -c "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('rapidocr_onnxruntime') else 1)" >nul 2>&1
if %errorlevel%==0 set RAPID_COLLECT=--collect-data rapidocr_onnxruntime

".venv\Scripts\pyinstaller.exe" --noconfirm --clean --windowed --name ERing ^
  --icon src\ERing\app\assets\tray.ico ^
  --add-data "src\ERing\app\assets;assets" ^
  --add-data "src\ERing\native\wheelhook.dll;native" ^
  %RAPID_COLLECT% ^
  --collect-submodules uiautomation ^
  src\ERing\main.py

rem PyInstaller may collect ICU DLLs from third-party apps on PATH and break QtCore.
for %%f in (dist\ERing\_internal\icu*.dll) do if exist "%%f" del "%%f"

echo.
echo Build complete: dist\ERing\ERing.exe
echo NOTE: recording needs ffmpeg.exe in native\ffmpeg\ next to the exe (or on PATH).
endlocal
pause
