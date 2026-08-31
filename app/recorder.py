# -*- coding: utf-8 -*-
"""录屏：ffmpeg + gdigrab 区域录制（参考 JamTools）。"""
import shutil
import subprocess
import threading
from pathlib import Path

from app.log_utils import log

FFMPEG_DIR = Path(__file__).resolve().parent.parent / "native" / "ffmpeg"


def find_ffmpeg():
    exe = FFMPEG_DIR / "ffmpeg.exe"
    if exe.exists():
        return str(exe)
    return shutil.which("ffmpeg")


class Recorder:
    def __init__(self):
        self._proc = None
        self._path = None
        self._lock = threading.Lock()

    @property
    def recording(self):
        with self._lock:
            return self._proc is not None

    @property
    def output_path(self):
        with self._lock:
            return self._path

    def start(self, phys_rect, out_path, fps=30, draw_mouse=True, fmt="mp4"):
        """phys_rect：物理像素 QRect。"""
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            raise RuntimeError("未找到 ffmpeg")
        x, y = phys_rect.x(), phys_rect.y()
        w, h = max(2, phys_rect.width()), max(2, phys_rect.height())
        # libx264 + yuv420p 要求宽高为偶数，奇数会编码失败输出 0KB
        w -= w % 2
        h -= h % 2
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            ffmpeg, "-y",
            "-f", "gdigrab",
            "-framerate", str(fps),
            "-draw_mouse", "1" if draw_mouse else "0",
            "-offset_x", str(x), "-offset_y", str(y),
            "-video_size", f"{w}x{h}",
            "-i", "desktop",
            "-movflags", "+faststart",  # moov 前置：即使被强杀文件也可播放
        ]
        if fmt == "gif":
            cmd += ["-c:v", "gif", "-r", str(fps)]
        else:
            cmd += ["-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", "-crf", "23"]
        cmd.append(str(out_path))
        with self._lock:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._path = str(out_path)
        log(f"recording start: {w}x{h} @ ({x},{y}) -> {out_path}")
        return str(out_path)

    def stop(self, timeout=8):
        with self._lock:
            proc, self._proc = self._proc, None
            path = self._path
            self._path = None
        if proc is None:
            return None
        try:
            if proc.poll() is None:
                proc.stdin.write(b"q")
                proc.stdin.flush()
        except Exception:
            pass
        try:
            proc.wait(timeout=timeout)
        except Exception:
            proc.kill()
        log(f"recording stop -> {path}")
        return path
