# -*- coding: utf-8 -*-
"""合成预览：用户底图 UI-BK.bmp + 控件文字（放大 2 倍）。"""

import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_sgui import controls  # noqa: E402


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT_COLOR = {0: (0, 0, 0), 15: (255, 255, 255)}
SCALE = 2


def font_for(px):
    try:
        return ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", px)
    except Exception:
        return ImageFont.load_default()


bg_path = os.path.join(ROOT, "UI-BK.bmp")
img = Image.open(bg_path).convert("RGB").resize((320 * SCALE, 240 * SCALE), Image.LANCZOS)
d = ImageDraw.Draw(img)

for c in controls:
    x, y, w, h = c["x"] * SCALE, c["y"] * SCALE, c["w"] * SCALE, c["h"] * SCALE
    if c["cname"] == "QProgressBar":
        d.rectangle([x, y, x + w, y + h], fill=(200, 200, 200))
        d.rectangle([x, y, x + int(w * 0.35), y + h], fill=(0, 0, 0))
    if c["text"]:
        f = font_for(int(c["size"]) * SCALE)
        d.text((x + 3 * SCALE, y + 1 * SCALE), c["text"],
               fill=TEXT_COLOR.get(c["font"], (0, 0, 0)), font=f)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "overlay_preview.png")
img.save(out)
print("written:", out, img.size)
