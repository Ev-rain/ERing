# 贡献指南（Contributing）

感谢你愿意参与 ERing 的开发！

## 环境

- Windows 10/11（本项目为 Windows 专用工具）；
- Python 3.10+；
- 运行 `安装依赖.bat` 或手动：

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r src\ERing\requirements.txt
```

## 开发约定

- 主程序入口：`src\ERing\main.py`；核心逻辑在 `src\ERing\app\`；
- 路径解析统一走 `app\paths.py`（源码 / PyInstaller 打包双模式）；
- 日志自动轮转保留 5 份，禁止在源码中硬编码绝对路径；
- 提交前请运行：

```bat
.venv\Scripts\python.exe src\ERing\main.py --smoke
```

退出码为 0 才算通过；大改动请同时跑 `tests\selftest.py`。

## 提交规范

- 用中文或英文写清晰的提交信息，说明“改了什么、为什么”；
- 一次提交只做一件事；
- 不要提交：`.venv/`、`data/`、`release*/`、`build/`、`dist/`、`src\ERing\native\ffmpeg/`。
