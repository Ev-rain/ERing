@echo off
chcp 65001 >nul
cd /d "%~dp0"
".venv\Scripts\python.exe" -m pip install pyinstaller
set RAPID_COLLECT=
".venv\Scripts\python.exe" -c "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('rapidocr_onnxruntime') else 1)" >nul 2>&1
if %errorlevel%==0 set RAPID_COLLECT=--collect-data rapidocr_onnxruntime
".venv\Scripts\pyinstaller.exe" --noconfirm --clean --windowed --name ERing ^
  %RAPID_COLLECT% ^
  --collect-submodules uiautomation ^
  main.py
echo.
echo 打包完成：dist\ERing\ 下的 ERing.exe 可直接运行
pause
