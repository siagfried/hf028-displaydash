# -*- coding: utf-8 -*-
"""
HF028 串口屏连通性 + 点亮自检脚本

运行：
    py selftest.py --port COM10

选项：
    --port      串口号（默认 COM10）
    --baud      波特率（默认 115200）
    --ping-only 只做通信测试，不动屏幕
    --demo-ui   追加演示 sGUI 控件指令（要求屏内已下载 SGUI工程/demo 工程，
                 且当前停留在它的页面 1）
"""

import argparse
import time

from hfd import HFDScreen


def run_ping(scr):
    print("== 1/4 通信测试 ==")
    raw = scr.ping()
    text = raw.decode("ascii", "replace")
    print("发送: GET_ADDR();")
    print("应答: %r" % text)
    enabled, addr = scr.get_addr_info()
    if enabled:
        print(f"模块已启用 485 地址，地址 = {addr}")
    else:
        print("模块处于无地址(TTL)模式")
    print("屏幕应当收到 OK。\n")


def run_raw_demo(scr):
    print("== 2/4 基础图形/文字测试（无需 sGUI 工程）==")
    scr.backlight(100)          # 背光最亮
    scr.clr("black")            # 黑底

    scr.box(6, 6, 233, 180, "yellow")          # 外框
    scr.circle_fill(52, 40, 16, "red")         # 实心红圆
    scr.circle_fill(92, 40, 16, "green")       # 实心绿圆
    scr.circle_fill(132, 40, 16, "blue")       # 实心蓝圆

    scr.dc32(30, 80, "HF028 串口屏", color="white")
    scr.dc24(45, 125, "COM10 115200 8N1", color="cyan")
    scr.dc16(58, 165, "UART link OK - 等待OK指令", color="gray")

    # 直线 + 空心图形
    scr.line(6, 186, 233, 186, "white")
    scr.line(6, 200, 233, 200, "gray")
    scr.box(15, 188, 100, 234, "yellow")
    scr.circle(140, 211, 22, "cyan")
    print("基础显示已发送。\n")


def run_dynamic_demo(scr):
    print("== 3/4 动态效果演示（滑动色块）==")
    scr.clr("black")
    scr.dc24(30, 20, "动态演示 Dynamic", color="white")
    for i in range(6):
        scr.clr("black")
        x = 10 + i * 35
        scr.box_fill(x, 70, x + 30, 120, i % 7 + 1)
        scr.dc24(x - 4, 135, f"{i}", color="cyan")
        time.sleep(0.35)
    scr.clr("black")
    scr.dc32(35, 80, "驱动成功", color="green")
    scr.dc24(52, 125, "HF028 QVGA 240x320", color="gray")
    print("动态演示完成，屏幕停在“驱动成功”。\n")


def run_ui_demo(scr):
    print("== 4/4 sGUI 控件演示（需已下载官方 demo 工程）==")
    # 官方 demo 例程不跳页：控件实际位于运行时的 page 0（sGUI 里显示为 page 1）
    scr.jump(0)
    time.sleep(0.5)
    scr.set_txt(0, "23:59:")     # 时钟“时:分:”
    scr.set_txt(10, "58")        # 秒
    scr.set_txt(11, "01")        # 日期尾段（随工程而定）
    vals = [(2, 12), (3, 34), (4, 56), (5, 78)]
    for ctrl_id, value in vals:
        scr.set_num(ctrl_id, value, 2)
    for ctrl_id, pct in [(6, 10), (7, 35), (8, 60), (9, 90)]:
        scr.set_prog(ctrl_id, pct)
    scr.set_txt(1, "demo ok")
    print("控件指令已发送（文本/数字/进度条）。\n")


def main():
    ap = argparse.ArgumentParser(description="HF028 串口屏自检")
    ap.add_argument("--port", default="COM10")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--ping-only", action="store_true")
    ap.add_argument("--demo-ui", action="store_true")
    args = ap.parse_args()

    print(f"打开 {args.port} @ {args.baud} ...")
    with HFDScreen(args.port, baudrate=args.baud) as scr:
        run_ping(scr)
        if not args.ping_only:
            run_raw_demo(scr)
            time.sleep(2.0)
            run_dynamic_demo(scr)
            if args.demo_ui:
                run_ui_demo(scr)

    print("完成。若屏幕没有反应，请把现象（是否亮背光/是否花屏/串口应答）发我。" )


if __name__ == "__main__":
    main()
