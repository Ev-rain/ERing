@echo off
chcp 65001 >nul
cd /d "%~dp0"
where g++ >nul 2>nul
if %errorlevel%==0 (
  g++ -shared -O2 -static -static-libgcc -o wheelhook.dll wheelhook.cpp -luser32
  if %errorlevel%==0 (
    echo 编译成功：native\wheelhook.dll
  ) else (
    echo 编译失败，请检查 g++。
  )
) else (
  echo 未找到 g++，请安装 MSYS2/MinGW 或 Visual Studio 的 C++ 工具链。
)
pause
