# -*- coding: utf-8 -*-
"""OCR 引擎：默认 Windows 原生（快），可切换 RapidOCR（高精度、离线通用）。"""
import io
import threading
import time

from PIL import Image

from app.log_utils import log


class OcrEngine:
    def __init__(self, engine="native"):
        self._mode = engine if engine in ("native", "rapid") else "native"
        self._engine = None
        self._lock = threading.Lock()

    def set_mode(self, mode):
        if mode in ("native", "rapid"):
            self._mode = mode

    def mode(self):
        return self._mode

    def _ensure(self):
        if self._engine is None:
            with self._lock:
                if self._engine is None:
                    try:
                        from rapidocr_onnxruntime import RapidOCR
                    except ImportError:
                        raise RuntimeError(
                            "RapidOCR 未安装（为减小体积已移除；默认使用 Windows 原生 OCR）"
                        )
                    self._engine = RapidOCR()
        return self._engine

    def preload(self):
        """启动后后台预热当前引擎：原生 OCR 创建引擎；RapidOCR 加载模型并空图预热。"""

        def work():
            try:
                t0 = time.perf_counter()
                if self._mode == "native":
                    from app.native_ocr import NativeOcr
                    if NativeOcr.is_available():
                        NativeOcr._get_engine()
                        log(f"OCR 预热完成(native): {time.perf_counter() - t0:.2f}s")
                else:
                    engine = self._ensure()
                    # 空图预热，让会话完成初始化分配
                    img = Image.new("RGB", (64, 32), "white")
                    engine(img)
                    log(f"OCR 预热完成(rapid): {time.perf_counter() - t0:.2f}s")
            except Exception:
                pass

        threading.Thread(target=work, daemon=True, name="ocr-preload").start()

    def recognize(self, qimage) -> str:
        if self._mode == "native":
            try:
                from app.native_ocr import NativeOcr
                if NativeOcr.is_available():
                    return NativeOcr.recognize(qimage)
                log("Windows OCR 语言包不可用，回退 RapidOCR")
            except Exception as exc:  # noqa: BLE001
                log(f"Windows OCR 失败，回退 RapidOCR: {exc}")
        return self._recognize_rapid(qimage)

    def _recognize_rapid(self, qimage) -> str:
        from PySide6.QtCore import QBuffer

        buf = QBuffer()
        buf.open(QBuffer.OpenModeFlag.WriteOnly)
        qimage.save(buf, "PNG")
        img = Image.open(io.BytesIO(bytes(buf.data()))).convert("RGB")
        engine = self._ensure()
        result, _ = engine(img)
        if not result:
            return ""
        return "\n".join(self._layout(result))

    @staticmethod
    def _layout(items):
        """把识别框按行聚类，保持阅读顺序。"""
        rows = []
        for box, text, _score in items:
            if _score < 0.5:  # 置信度过滤（参考 JamTools）
                continue
            ys = [pt[1] for pt in box]
            xs = [pt[0] for pt in box]
            rows.append((sum(ys) / 4, sum(xs) / 4, max(ys) - min(ys), text))
        if not rows:
            return []
        rows.sort(key=lambda r: (r[0], r[1]))
        heights = sorted(r[2] for r in rows)
        median_h = heights[len(heights) // 2] if heights else 12
        threshold = max(8, median_h * 0.6)
        lines = []
        cur = []
        last_cy = None
        for cy, cx, _h, text in rows:
            if last_cy is None or abs(cy - last_cy) <= threshold:
                cur.append((cx, text))
            else:
                lines.append(" ".join(t for _, t in sorted(cur)))
                cur = [(cx, text)]
            last_cy = cy
        if cur:
            lines.append(" ".join(t for _, t in sorted(cur)))
        return lines
