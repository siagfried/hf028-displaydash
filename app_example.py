# -*- coding: utf-8 -*-
"""
HF028 实时数据驱动示例

驱动官方 demo 工程（已烧录在屏内）中的控件：
    page 0（sGUI 里显示为 page 1）
    文本 0/1/10/11 = 时钟/日期，数字 2~5，进度条 6~9

运行：
    py app_example.py --seconds 15     # 演示 15 秒后自动停止
    py app_example.py                  # 无限运行，Ctrl+C 停止

把下面的 read_telemetry() 换成你的真实数据来源（串口/网络/文件……），
并在 update_screen() 里把值填到对应控件即可。
"""

import argparse
import math
import random
import time
from datetime import datetime

from hfd import HFDScreen


def read_telemetry(t):
    """
    模拟数据源：t 为运行秒数。返回需要显示的字段。
    真实使用时：换成读传感器/下位机数据，返回相同结构的 dict。
    """
    return {
        "temp": round(25 + 5 * math.sin(t / 8), 1),   # 温度 ℃
        "hum": round(60 + 10 * math.sin(t / 5 + 1), 1),  # 湿度 %
        "press": round(1013 + 8 * math.sin(t / 11), 1),  # 气压 hPa
        "bat": round(78 + 5 * math.sin(t / 6 + 2), 1),   # 电量 %
        "prog": [int(50 + 40 * math.sin((t + i * 1.3) / 4)) for i in range(4)],
    }


def clamp_prog(v):
    """进度条值限制在 0~100。"""
    return max(0, min(100, v))


def update_screen(scr, tele):
    """把一帧数据写到 demo 工程控件上（时间/日期 + 4 个数字 + 4 条进度）。"""
    now = datetime.now()
    cmds = [
        f"SET_TXT(0,'{now:%H:%M:}')",
        f"SET_TXT(10,'{now:%S}')",
        f"SET_TXT(1,'{now:%Y}/{now.month}/')",
        f"SET_TXT(11,'{now.day:02d}')",
        f"SET_NUM(2,{int(tele['temp'])},2)",
        f"SET_NUM(3,{int(tele['hum'])},2)",
        f"SET_NUM(4,{int(tele['press'] % 100)},2)",
        f"SET_NUM(5,{int(tele['bat'])},2)",
    ]
    cmds += [f"SET_PROG({6 + i},{clamp_prog(v)})" for i, v in enumerate(tele["prog"])]
    scr.cmd(*cmds)


def main():
    ap = argparse.ArgumentParser(description="HF028 实时数据演示")
    ap.add_argument("--port", default="COM10")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--seconds", type=float, default=0, help="演示秒数，0=无限")
    ap.add_argument("--interval", type=float, default=1.0, help="刷新间隔秒")
    args = ap.parse_args()

    start = time.monotonic()
    t = 0.0
    print(f"打开 {args.port} @ {args.baud}，开始实时演示（Ctrl+C 停止）...")
    with HFDScreen(args.port, baudrate=args.baud) as scr:
        scr.jump(0)  # 官方 demo 控件所在页
        time.sleep(0.5)
        while not args.seconds or time.monotonic() - start < args.seconds:
            tele = read_telemetry(t)
            update_screen(scr, tele)
            print(
                f"t={t:5.1f}s  temp={tele['temp']:5.1f} hum={tele['hum']:5.1f} "
                f"press={tele['press']:6.1f} bat={tele['bat']:5.1f} "
                f"prog={tele['prog']}"
            )
            t += args.interval
            time.sleep(args.interval)
    print("演示结束。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已停止。")
