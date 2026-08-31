# -*- coding: utf-8 -*-
"""Windows 原生 OCR（Windows.Media.Ocr）。
速度快（约 20~30ms），依赖系统语言包（如 简体中文 zh-Hans-CN）。
原生结果会在中文字符间插入空格，这里做轻量清理。"""
import asyncio
import re
import threading

_CJK_SPACE = re.compile(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])")
_PUNCT_SPACE = re.compile(r"\s+([，。！？；：、．,.!?;:])")
_AFTER_PUNCT_CJK = re.compile(r"([，。！？；：、．])\s+(?=[\u4e00-\u9fff])")
_FULLWIDTH_DOT = re.compile("．")
_DIGIT_SPACE = re.compile(r"(?<=\d)\s+(?=\d)")


class NativeOcr:
    _engine = None
    _lock = threading.Lock()

    @classmethod
    def cleanup(cls):
        """退出前显式释放 WinRT 引擎对象，避免解释器终结阶段 GC 崩溃。"""
        with cls._lock:
            cls._engine = None

    @classmethod
    def is_available(cls):
        try:
            import winsdk.windows.media.ocr as ocr
            return len(ocr.OcrEngine.available_recognizer_languages) > 0
        except Exception:
            return False

    @classmethod
    def _get_engine(cls):
        if cls._engine is None:
            with cls._lock:
                if cls._engine is None:
                    import winsdk.windows.media.ocr as ocr
                    langs = list(ocr.OcrEngine.available_recognizer_languages)
                    lang = next(
                        (l for l in langs if l.language_tag.lower().startswith("zh")),
                        None,
                    )
                    if lang is None and langs:
                        lang = langs[0]
                    cls._engine = (
                        ocr.OcrEngine.try_create_from_language(lang) if lang else None
                    )
        return cls._engine

    @classmethod
    def recognize(cls, qimage) -> str:
        """在后台线程中调用：asyncio.run 创建一次性事件循环执行 WinRT 异步。"""
        return asyncio.run(cls._recognize_async(qimage))

    @classmethod
    async def _recognize_async(cls, qimage):
        import winsdk.windows.graphics.imaging as imaging
        import winsdk.windows.storage.streams as streams

        from PySide6.QtCore import QBuffer

        engine = cls._get_engine()
        if engine is None:
            raise RuntimeError("Windows OCR 不可用")

        buf = QBuffer()
        buf.open(QBuffer.OpenModeFlag.WriteOnly)
        qimage.save(buf, "PNG")
        png = bytes(buf.data())

        stream = streams.InMemoryRandomAccessStream()
        writer = streams.DataWriter(stream)
        writer.write_bytes(png)
        await writer.store_async()
        stream.seek(0)
        decoder = await imaging.BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        result = await engine.recognize_async(bitmap)
        text = result.text or ""
        text = _CJK_SPACE.sub("", text)
        text = _PUNCT_SPACE.sub(r"\1", text)
        text = _AFTER_PUNCT_CJK.sub(r"\1", text)
        text = _FULLWIDTH_DOT.sub(".", text)
        text = _DIGIT_SPACE.sub("", text)
        return text.strip()
