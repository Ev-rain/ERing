@echo off
chcp 65001 >nul
cd /d "%~dp0"
".venv\Scripts\python.exe" -m pip install pyinstaller
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
echo.
echo 打包完成：dist\ERing\ 下的 ERing.exe 可直接运行
echo 提示：录屏需要把 ffmpeg.exe 放到 exe 同级的 native\ffmpeg\ 下（或加入 PATH）
pause
