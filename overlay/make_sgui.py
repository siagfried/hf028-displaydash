# -*- coding: utf-8 -*-
"""
基于 UI-BK.bmp 底图生成 overlay.sGUI（HF028 横屏 320x240）。

背景 = UI-BK.bmp（在 sGUI 中作为页面背景图，图片资源 id 0）。
页面上所有文字/数值/进度条都是透明变量控件，叠在背景上。
"""

import os


def ctrl(cname, cid, x, y, w, h, text="", size=16,
         font=0, bg=0, style=0, progType=0, styleColor=0):
    return dict(cname=cname, cid=cid, x=x, y=y, w=w, h=h, text=text,
                size=size, font=font, bg=bg, style=style,
                progType=progType, styleColor=styleColor)


controls = []

# 顶部深色标题栏（白字）
controls.append(ctrl("QLabel", 0, 6, 8, 150, 16, "OPENWRT CLASH", 16, 15, 0, 0))
controls.append(ctrl("QLabel", 1, 222, 8, 94, 16, "12:26 09-03", 16, 15, 0, 0))

# 红色面板（深字）
controls.append(ctrl("QLabel", 2, 14, 38, 150, 22, "SYSTEM: OK", 24, 0, 0, 0))
controls.append(ctrl("QLabel", 3, 14, 64, 178, 16, "IP: 192.168.222.222", 16, 0, 0, 0))
controls.append(ctrl("QLabel", 4, 14, 82, 200, 16, "TEMP:38 C LOAD:100%", 16, 0, 0, 0))
controls.append(ctrl("QLabel", 5, 200, 38, 118, 22, "DL: 95.8 M", 24, 0, 0, 0))
controls.append(ctrl("QLabel", 6, 200, 72, 118, 22, "UP: 12.1 M", 24, 0, 0, 0))

# 灰色面板（深字）
controls.append(ctrl("QLabel", 7, 14, 114, 180, 16, "SUB: AMYTELCOM", 16, 0, 0, 0))
controls.append(ctrl("QLabel", 8, 14, 132, 180, 16, "EXPIRE: 2026-11-27", 16, 0, 0, 0))
controls.append(ctrl("QProgressBar", 9, 14, 154, 176, 12, "", 16, 0, 7, 1, 0, 0))
controls.append(ctrl("QLabel", 10, 14, 172, 180, 16, "14.91 / 250 GB", 16, 0, 0, 0))
controls.append(ctrl("QLabel", 11, 14, 194, 180, 14, "WAN:110.123.456.789(CN)", 16, 0, 0, 0))
controls.append(ctrl("QLabel", 12, 14, 210, 180, 14, "PRX:445.000.000.000(HK)", 16, 0, 0, 0))

# 白色面板
controls.append(ctrl("QLabel", 13, 212, 216, 108, 14, "SCAN FOR WIFI", 16, 0, 0, 0))


def control_xml(c):
    text = (c["text"]
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))
    return f"""    <ClassName ClassName="{c['cname']}">
      <id>{c['cid']}</id>
      <x>{c['x']}</x>
      <y>{c['y']}</y>
      <w>{c['w']}</w>
      <h>{c['h']}</h>
      <text>{text}</text>
      <fontSize>{c['size']}</fontSize>
      <hAlign>0</hAlign>
      <vAlign>0</vAlign>
      <fontColorNum>{c['font']}</fontColorNum>
      <backgroundColorNum>{c['bg']}</backgroundColorNum>
      <pressColorNum>0</pressColorNum>
      <imageNum>-1</imageNum>
      <cutImageNum>-1</cutImageNum>
      <backgroundImageNum>-1</backgroundImageNum>
      <backgroundCutImageNum>-1</backgroundCutImageNum>
      <pressImageNum>-1</pressImageNum>
      <pressCutImageNum>-1</pressCutImageNum>
      <progType>{c['progType']}</progType>
      <style>{c['style']}</style>
      <styleColorNum>{c['styleColor']}</styleColorNum>
      <pointerX>0</pointerX>
      <pointerY>0</pointerY>
      <pointerW>0</pointerW>
      <pointerL>0</pointerL>
      <pointerAngle>0</pointerAngle>
    </ClassName>
"""


def build(controls):
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<ui>",
        '  <frame frame="frame">',
        "    <frameW>320</frameW>",
        "    <frameH>240</frameH>",
        "    <parentImageNum>-1</parentImageNum>",
        "    <parentBackgroundNum>16</parentBackgroundNum>",
        "    <screenType>3</screenType>",
        "    <dpi>240*320(QVGA)</dpi>",
        "    <baud>115200</baud>",
        "    <blValue>1048077668</blValue>",
        "    <logo1>-1</logo1>",
        "    <logo2>-1</logo2>",
        "    <logox>0</logox>",
        "    <logoy>0</logoy>",
        "    <logow>0</logow>",
        "    <logoh>0</logoh>",
        "    <logotime>0</logotime>",
        "  </frame>",
        '  <page id="1">',
        '    <pageImageNum pageImageNum="0"/>',
        '    <pageBackgroundNum pageBackgroundNum="16"/>',
    ]
    parts.extend(control_xml(c) for c in controls)
    parts.extend(["  </page>", "</ui>"])
    return "\n".join(parts) + "\n"


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "overlay.sGUI")
    xml = build(controls)
    with open(out, "w", encoding="utf-8", newline="") as f:
        f.write(xml)
    import xml.dom.minidom as M
    M.parse(out)
    print("written:", out)
    print("controls:", len(controls))
