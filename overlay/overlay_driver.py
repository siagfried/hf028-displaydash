# -*- coding: utf-8 -*-
"""
基于 UI-BK.bmp 底图的界面驱动（对应 overlay.sGUI）。

界面需要先用 sGUI 下载到模块（横屏 320x240，页面背景图 = UI-BK.bmp）。
所有文字/数值/进度条都是变量控件，按控件 ID 更新。

运行（在工程根目录）：
    py overlay/overlay_driver.py --seconds 20
"""

import argparse
import math
import time
from dataclasses import dataclass
from datetime import datetime

from hfd import HFDScreen


@dataclass
class OverlayData:
    header_title: str = "OPENWRT CLASH"
    header_dt: str = "12:26 09-03"
    system: str = "SYSTEM: OK"
    ip: str = "IP: 192.168.222.222"
    temp_load: str = "TEMP:38 C LOAD:100%"
    dl: str = "DL: 95.8 M"
    up: str = "UP: 12.1 M"
    sub: str = "SUB: AMYTELCOM"
    expire: str = "EXPIRE: 2026-11-27"
    prog: int = 35           # 0~100，进度条控件 id9
    usage: str = "14.91 / 250 GB"
    wan: str = "WAN:110.123.456.789(CN)"
    proxy: str = "PRX:445.000.000.000(HK)"
    qr: str = ""             # 二维码控件(id=0，全局)内容


SET_TXT_MAP = {
    0: "header_title",
    1: "header_dt",
    2: "system",
    3: "ip",
    4: "temp_load",
    5: "dl",
    6: "up",
    7: "sub",
    8: "expire",
    10: "usage",
    11: "wan",
    12: "proxy",
}


def build_commands(d: OverlayData, enable_qr=False):
    cmds = [f"SET_TXT({cid},'{getattr(d, attr)}')" for cid, attr in SET_TXT_MAP.items()]
    cmds.append(f"SET_PROG(9,{int(d.prog)})")
    if d.qr:
        cmds.append(f"QBAR(0,'{d.qr}')")
    return cmds


def update(scr, d: OverlayData):
    cmds = build_commands(d)
    cur, size = [], 0
    for cmd in cmds:
        cur.append(cmd)
        size += len(cmd.encode("gb2312")) + 1
        if size > 900:
            scr.cmd(*cur)
            cur, size = [], 0
    if cur:
        scr.cmd(*cur)


def mock_data(t: float) -> OverlayData:
    now = datetime.now()
    return OverlayData(
        header_title="OPENWRT CLASH",
        header_dt=f"{now:%H:%M} {now:%m-%d}",
        system="SYSTEM: OK",
        ip="IP: 192.168.222.222",
        temp_load=f"TEMP:{int(30 + 8 * math.sin(t / 6))} C LOAD:{int(20 + 15 * math.sin(t / 9))}%",
        dl=f"DL: {95.8 + 5 * math.sin(t / 3):.1f} M",
        up=f"UP: {12.1 + 3 * math.cos(t / 4):.1f} M",
        sub="SUB: AMYTELCOM",
        expire="EXPIRE: 2026-11-27",
        prog=int(35 + 30 * math.sin(t / 4)),
        usage=f"{14.91 + 0.5 * t:.2f} / 250 GB",
        wan="WAN:110.123.456.789(CN)",
        proxy="PRX:445.000.000.000(HK)",
    )


def main():
    ap = argparse.ArgumentParser(description="HF028 界面驱动（UI-BK.bmp 底图）")
    ap.add_argument("--port", default="COM10")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--seconds", type=float, default=0, help="演示秒数，0=无限")
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--qr", default="", help="可选：WiFi 二维码内容（需先加二维码控件）")
    args = ap.parse_args()

    start = time.monotonic()
    t = 0.0
    print(f"打开 {args.port} @ {args.baud}，开始刷新界面（Ctrl+C 停止）...")
    with HFDScreen(args.port, baudrate=args.baud) as scr:
        scr.jump(0)
        time.sleep(0.5)
        d0 = mock_data(0)
        d0.qr = args.qr
        update(scr, d0)
        while not args.seconds or time.monotonic() - start < args.seconds:
            d = mock_data(t)
            d.qr = args.qr
            update(scr, d)
            print(f"t={t:5.1f}s  {d.system}  {d.ip}  {d.dl}  {d.usage}  prog={d.prog}")
            t += args.interval
            time.sleep(args.interval)
    print("演示结束。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已停止。")
