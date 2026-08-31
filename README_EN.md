# ERing

**An easy-to-use radial toolkit for your desktop.**

A Windows desktop utility: **hold the right mouse button and drag** to summon a radial
menu. Pick **Translate** to translate **selected text** or **text inside a screenshot**
(OCR), or use the built-in **region screen recorder** and **DeepSeek balance checker**.

> UI interactions, colors and layout heavily reference
> [StarPie](https://github.com/SoftBlack42/StarPie). Special thanks to its author!

## Features

- Radial menu summoned by right-drag (Translate / Record / Settings);
- Translate selected text directly, or screenshot → OCR → translate;
- Resizable result panel with its own dark/light theme;
- Region recording (ffmpeg), MP4/GIF, 15/30/60 FPS, timer on the stop button;
- DeepSeek balance & today's consumption (balance-diff based, ignores top-ups);
- Tray: double-click to open settings, autostart, open recording folder;
- Five settings pages; everything persisted.

## Quick Start (source)

Requirements: Windows 10/11, Python 3.10+.

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r src\ERing\requirements.txt
.venv\Scripts\pythonw.exe src\ERing\main.py
```

Optional high-accuracy offline OCR (adds ~220MB):

```bat
.venv\Scripts\python.exe -m pip install -r src\ERing\requirements-ocr.txt
```

Recording requires `ffmpeg.exe` in `src\ERing\native\ffmpeg\` (not committed) or in PATH.

## Release Build

Run `build.bat` (PyInstaller) → `dist\ERing\ERing.exe`. A ready-to-run package is also
provided under `release1.0.0\` (not in git). Copy the whole folder to another 64-bit
Windows 10/11 machine and run `ERing.exe` — no Python needed. ffmpeg is included there.

## License

MIT — see [LICENSE](LICENSE).
