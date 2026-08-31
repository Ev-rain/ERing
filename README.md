# ERing

**An easy-to-use radial toolkit for your desktop.**

一个 Windows 桌面效率小工具：**按住鼠标右键拖动**呼出轮盘，选中「翻译」即可把
**选中的文本**或**截图中的文字**翻译成目标语言；轮盘里还集成了**区域录屏**、
**设置**与 **DeepSeek 余额/今日消费** 查询。

> 界面交互、配色与美术风格大量参考了 [StarPie](https://github.com/SoftBlack42/StarPie)
> （轮盘手势菜单、浅/暗双主题、设置面板布局等）。在此特别感谢 StarPie 作者的优秀设计与开源！

## ✨ 功能特性

- **右键轮盘菜单**：右键按下拖动呼出，拖动方向即选择（上=翻译、右=录屏、下=设置）；
  支持外甩取消手势、弹出动画速度三档、暗/亮双主题。
- **DeepSeek 余额 / 今日消费**：绑定 API Key 后，轮盘圆心显示总余额与今日消费
  （按当日余额差值统计，充值增长自动忽略）；未绑定 Key 时圆心显示「退出」。
- **即选即译**：有选中文本 → 直接翻译选中文字；无选中文本 → 框选截图 → OCR 识别 → 翻译。
- **翻译结果浮窗**：独立主题（暗/亮）、可拖拽移动、可拖边缘调整大小并记住尺寸、
  一键复制译文/原文。
- **区域录屏**：框选区域或单击全屏，ffmpeg 录制 MP4/GIF，帧率 15/30/60 可选，
  停止按钮自带录制计时器，录制内容不会把按钮/提示录进去。
- **AI 翻译**：默认免费源（MyMemory → Google → Edge 兜底），也可配置 OpenAI 兼容接口
  （DeepSeek、硅基流动、本地 Ollama 等）。
- **系统托盘**：双击打开设置；右键菜单含开机自启动（勾选切换）、设置、打开录屏文件位置、退出。
- **设置面板**：翻译 / 轮盘与识别 / 录屏 / DeepSeek / 通用 五个页面，所有配置持久化。

## 📁 目录结构

```text
ERing/
├── src/ERing/              # 主程序源码（对应 StarPie 的 WinPieGestures）
│   ├── main.py             # 程序入口
│   ├── app/                # 核心源码包
│   │   ├── wheel.py        # 轮盘菜单（StarPie 风格双主题）
│   │   ├── settings_dialog.py  # 设置面板
│   │   ├── result_window.py    # 翻译结果浮窗
│   │   ├── recorder.py     # 录屏（ffmpeg gdigrab）
│   │   ├── tray.py         # 系统托盘
│   │   ├── ocr.py / native_ocr.py  # 文字识别
│   │   ├── translate.py    # 翻译源
│   │   ├── deepseek.py     # 余额/今日消费
│   │   ├── autostart.py    # 开机自启动（注册表）
│   │   ├── window_icon.py  # 任务栏图标修复
│   │   └── assets/         # 图标等资源
│   ├── native/
│   │   ├── wheelhook.cpp/.dll  # C++ 全局鼠标钩子
│   │   └── ffmpeg/         # ffmpeg（体积大，未随仓库提交，见下方说明）
│   ├── data/               # 运行时数据（日志/设置/录屏，不入库）
│   ├── requirements.txt
│   └── requirements-ocr.txt
├── tests/                  # 自检脚本
├── releases/               # 版本发布约定
├── assets/                 # README 等文档素材
├── CHANGELOG.md / CONTRIBUTING.md / SECURITY.md / README_EN.md
├── 安装依赖.bat / 启动.bat / build.bat
└── LICENSE
```

## 🚀 快速开始

环境要求：Windows 10/11，Python 3.10+（安装时勾选 “Add to PATH” 或装有 `py` 启动器）。

1. 双击 **安装依赖.bat**（首次运行：创建 `.venv` 虚拟环境并安装依赖）；
2. 如果 `src\ERing\native\wheelhook.dll` 不存在，双击 **src\ERing\native\build.bat** 编译 C++ 钩子
   （需要 MSYS2/MinGW 的 g++；没有则程序会自动回退纯 Python 钩子）；
3. 双击 **启动.bat** 运行。

也可以手动运行：

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r src\ERing\requirements.txt
.venv\Scripts\pythonw.exe src\ERing\main.py
```

### 可选依赖：RapidOCR

默认依赖已尽量精简（约 300MB）。如需「RapidOCR 高精度离线识别」选项，
额外执行一次即可（约 +220MB，cv2/onnxruntime 体积较大）：

```bat
.venv\Scripts\python.exe -m pip install -r src\ERing\requirements-ocr.txt
```

未安装时，设置里的 RapidOCR 选项会置灰；OCR 默认使用 Windows 原生引擎。

### ffmpeg 说明

录屏依赖 ffmpeg。`src\ERing\native\ffmpeg\` 体积较大（约 68MB），未包含在 Git 仓库中；
请自行放入 `src\ERing\native\ffmpeg\ffmpeg.exe`（推荐从 [gyan.dev ffmpeg builds](https://www.gyan.dev/ffmpeg/builds/)
下载 Essentials 版），或把 ffmpeg 加入 PATH，程序会自动找到。

## 🎯 使用说明

| 操作 | 效果 |
| --- | --- |
| 按住鼠标右键拖动 | 呼出轮盘，拖动方向选择功能 |
| 轮盘「翻译」+ 有选中文本 | 直接翻译选中的文本 |
| 轮盘「翻译」+ 无选中文本 | 框选截图 → OCR 识别 → 翻译 |
| 轮盘「录屏」 | 框选区域（单击=全屏）开始录屏 |
| 轮盘「设置」 | 打开设置面板 |
| 圆心（余额/退出）松开 | 取消本次操作（不退出程序） |
| 托盘双击 | 打开设置 |

录屏时：白色圆角外壳的停止按钮（含计时器）可拖到任意位置并记住位置，单击即停止。
截图/录屏框选时：左键拖拽框选，右键或 Esc 取消。

## ⚙️ 设置面板

- **翻译设置**：目标语言、自动判断方向、翻译面板主题（暗/亮）、翻译源、OpenAI 兼容接口；
- **轮盘与识别**：拖动触发距离、轮盘主题、弹出动画速度、外甩取消及距离、OCR 引擎
  （默认 Windows 原生 OCR；RapidOCR 为可选安装）；
- **录屏设置**：帧率（15/30/60）、鼠标指针、MP4/GIF、保存位置与「打开录屏文件」；
- **DeepSeek 账户**：API Key、查询余额、今日消费（按当日余额差值统计，充值增长自动忽略）；
- **通用**：开机自启动、关闭设置窗口行为（最小化到托盘/直接关闭）、记住翻译窗口大小、调试日志。

## ❓ 常见问题

- **录屏文件 0KB / 无法打开**：libx264 要求宽高为偶数，程序已自动向下取整，请更新到最新版本；
- **需要管理员权限的窗口无法呼出轮盘**：普通权限的钩子不生效，请以管理员身份运行本工具；
- **首次 OCR 较慢**：程序启动时已后台预热；或换用 Windows 原生 OCR（设置 → 轮盘与识别）；
- **今日消费为 0**：需要先查询过一次余额才会建立当日基准。

## 📦 打包为独立 exe

双击 **build.bat**（基于 PyInstaller），产物在 `dist\ERing\ERing.exe`（约 130~350MB，
取决于打包机是否安装了 RapidOCR）。exe 可直接拷贝到其他 64 位 Windows 10/11 上运行，
无需安装 Python；运行时会在 exe 同级自动创建 `data\`（配置/日志/录屏）目录。

打包/分发注意：

- **ffmpeg**：exe 不内置，需把 `ffmpeg.exe` 放到 exe 同级的 `native\ffmpeg\` 下，
  或加入系统 PATH，否则录屏不可用；
- 在未安装 RapidOCR 的机器上打包可显著减小体积（不含 cv2/onnxruntime/numpy）；
- 原生 OCR（Windows.Media.Ocr）需要目标系统安装了对应语言包。

## 📄 开源协议

MIT License，详见 [LICENSE](LICENSE)。

## 🙏 致谢

- [StarPie](https://github.com/SoftBlack42/StarPie)：轮盘交互、美术风格与设置面板布局的重要参考；
- 录屏与识别方案参考了 [JamTools](https://github.com/fandesfyf/JamTools)；
- 免费翻译源：MyMemory / Google / 微软 Edge。
