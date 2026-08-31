# -*- coding: utf-8 -*-
"""快速自检：截图、翻译接口、OCR"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "ERing"))


def test_screenshot():
    import mss

    with mss.MSS() as sct:
        mon = sct.monitors[0]
        shot = sct.grab(mon)
    print("screen:", mon, "->", shot.width, "x", shot.height)
    assert shot.width > 0 and shot.height > 0


def test_translate():
    from app.translate import translate_text

    cfg = {
        "auto_direction": True,
        "target_lang": "zh-CN",
        "provider": "auto",
        "max_text_len": 5000,
        "openai": {},
    }
    ok, res, provider = translate_text(
        "Hello world, this is a test of the translation engine.", cfg
    )
    print("translate:", ok, provider, "->", res)
    assert ok and res


def test_ocr():
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (560, 130), "white")
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 46)
    d.text((24, 30), "你好，世界 123", font=font, fill="black")
    img.save(Path(__file__).parent / "_ocr_test.png")

    from PySide6.QtGui import QImage

    from app.ocr import OcrEngine

    text = OcrEngine().recognize(QImage(str(Path(__file__).parent / "_ocr_test.png")))
    print("ocr:", repr(text))
    assert "你好" in text


if __name__ == "__main__":
    test_screenshot()
    test_translate()
    test_ocr()
    print("ALL TESTS PASSED")
