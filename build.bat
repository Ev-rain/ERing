@echo off
chcp 65001 >nul
cd /d "%~dp0"
".venv\Scripts\python.exe" -m pip install pyinstaller
".venv\Scripts\pyinstaller.exe" --noconfirm --clean --windowed --name 轮盘翻译 ^
  --collect-data rapidocr_onnxruntime ^
  --collect-submodules uiautomation ^
  main.py
echo.
echo 打包完成：dist\轮盘翻译\ 下的 轮盘翻译.exe 可直接运行
pause
