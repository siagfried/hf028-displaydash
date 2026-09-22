# -*- coding: utf-8 -*-
"""
HF028 / HFD 系列串口屏驱动（Python）

协议要点（依据《HFD 应用文档》与官方 GD32 例程）：
  * UART：115200/38400/19200/9600，8 数据位、1 停止位、无校验（8N1）
  * 指令为 ASCII 字符串，多个指令用 ';' 分隔，整串以 ";\r\n" 结束
  * 屏执行完一条指令串后回复 "OK\r\n"（推荐收到 OK 再发下一条）
  * 文本内容按 GB2312 编码发送（不是 UTF-8）
  * 若模块开启了 485 地址模式，每条指令串前需加 "ADDR(n);"
  * 指令串总长度不能超过模块缓冲区（HF028 为 1024 字节）

示例：
    from hfd import HFDScreen
    with HFDScreen("COM10") as scr:
        print(scr.ping())
        scr.clr(0)
        scr.backlight(100)
        scr.dc32(20, 30, "HF028 OK", color=15)
        scr.set_txt(10, "01")          # 需要 sGUI 工程已下载到屏内
"""

from __future__ import annotations

import re
import time

import serial


class HFDError(IOError):
    """HFD 通信错误。"""


class HFDScreen:
    """HFD（HF 系列串口屏）ASCII 指令驱动。"""

    SUPPORTED_BAUD = (9600, 19200, 38400, 115200)
    # 常用颜色编号（0~63 详见文档颜色值表）
    COLORS = {
        "black": 0,
        "red": 1,
        "green": 2,
        "blue": 3,
        "yellow": 4,
        "cyan": 5,
        "magenta": 6,
        "gray": 7,
        "white": 15,
    }

    def __init__(self, port, baudrate=115200, address=None, timeout=0.5):
        """
        port    : Windows 下为 'COM10' 等串口号
        baudrate: 必须与屏内设置一致（默认 115200）
        address : None=无地址模式；开启 485 地址后传设备地址整数（0 为广播）
        timeout : 串口读取超时（秒）
        """
        if baudrate not in self.SUPPORTED_BAUD:
            raise HFDError(f"不支持的波特率 {baudrate}，仅支持 {self.SUPPORTED_BAUD}")
        self.port = port
        self.baudrate = baudrate
        self.address = address
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=timeout,
        )
        self.ser.reset_input_buffer()

    # ------------------------------------------------------------------ 基础

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _drain(self):
        """丢弃历史残留数据，避免干扰下一条指令的应答判断。"""
        self.ser.reset_input_buffer()

    def _make_frame(self, commands):
        if not commands:
            raise HFDError("指令列表为空")
        parts = [c.strip() for c in commands if str(c).strip()]
        if not parts:
            raise HFDError("指令列表为空")
        frame = ";".join(parts) + ";\r\n"
        if self.address is not None:
            frame = f"ADDR({int(self.address)});" + frame
        try:
            data = frame.encode("gb2312")  # 指令本身是 ASCII，文本参数支持中文
        except UnicodeEncodeError as e:
            raise HFDError(f"内容含 GB2312 无法编码的字符：{e}") from e
        if len(data) > 1024:
            raise HFDError(f"指令串 {len(data)} 字节超过 HF028 的 1024 字节缓冲区限制")
        return data

    def _read_response(self, read_timeout):
        end = time.monotonic() + read_timeout
        buf = bytearray()
        idle_from = None
        while time.monotonic() < end:
            waiting = self.ser.in_waiting
            if waiting:
                buf.extend(self.ser.read(waiting))
                idle_from = time.monotonic()
            elif buf:
                # 数据流已停顿：收到 OK（正常结束）或无 OK 但已无更多数据
                if b"OK\r\n" in buf or (
                    idle_from is not None and time.monotonic() - idle_from >= 0.05
                ):
                    break
            time.sleep(0.005)
        return bytes(buf)

    def cmd(self, *commands, read_timeout=1.0, drain=True):
        """
        发送一条指令串并等待模块应答。
        返回模块返回的原始字节（通常含 "OK\\r\\n"，GET_ADDR 等还有内容行）。
        可一次传多条指令：cmd("BL(0)", "CLR(0)")。
        """
        if drain:
            self._drain()
        data = self._make_frame(commands)
        self.ser.write(data)
        resp = self._read_response(read_timeout)
        if not resp:
            raise HFDError(
                f"{self.port} 无应答：请检查接线/波特率，或关闭占用串口的软件"
            )
        if b"OK\r\n" not in resp and not any(
            m in resp for m in (b"GETADDR", b"VAR", b"UP", b"DN")
        ):
            raise HFDError(f"收到非预期应答：{resp!r}")
        return resp

    # ------------------------------------------------------------------ 连接

    def ping(self, tries=2):
        """
        通信测试：发送 GET_ADDR();。
        模块会回 GETADDR/OK 等内容；屏幕上若已下载工程也会显示状态。
        先按无地址方式试，失败则用广播地址 ADDR(0) 再试。
        """
        last = b""
        for addr in (None, 0):
            if addr is not None:
                saved, self.address = self.address, addr
            try:
                last = self.cmd("GET_ADDR();")
                return last
            except HFDError:
                pass
            finally:
                if addr is not None:
                    self.address = saved
            if tries <= 1:
                break
        raise HFDError(f"{self.port} 通信失败，最后应答：{last!r}")

    def get_addr_info(self):
        """
        解析 GET_ADDR 应答，返回 (485是否启用, 模块地址或 None)。
        实际应答形如 GETADDR_0_1（下划线分隔）：前段为是否启用 485，
        后段在启用时为模块地址。
        """
        raw = self.ping()
        text = raw.decode("ascii", "replace")
        m = re.search(r"GETADDR[_\s]+(\d+)(?:[_\s]+(\d+))?", text)
        if not m:
            return None, None
        enabled = int(m.group(1))
        addr = int(m.group(2)) if m.group(2) else None
        return bool(enabled), addr if enabled else None

    # ------------------------------------------------------------------ 系统

    def version(self):
        """VER()：版本信息显示在屏上，同时回 OK。"""
        self.cmd("VER()")

    def set_baud(self, bps):
        """BPS(bps)：修改屏内波特率（掉电保存）。改完需按新波特率重新连接。"""
        if bps not in self.SUPPORTED_BAUD:
            raise HFDError(f"波特率必须为 {self.SUPPORTED_BAUD}")
        self.cmd(f"BPS({bps})")

    def reset(self):
        """RESET()：重启模块。"""
        try:
            self.cmd("RESET()")
        except HFDError:
            pass

    def delay(self, ms):
        """DELAYMS(ms)：模块内部延时（文档建议不要超过 1500ms）。"""
        if ms > 1500:
            raise HFDError("DELAYMS 建议不超过 1500ms")
        self.cmd(f"DELAYMS({ms})")

    def set_direction(self, d):
        """DIR(d)：0=原始竖屏；1=逆时针旋转 90°横屏；2/3 见文档。掉电保存。"""
        self.cmd(f"DIR({int(d)})")

    def lcd_on(self, on=True):
        """LCDON(on)：1 开屏，0 关屏（关屏时背光同时熄灭）。"""
        self.cmd(f"LCDON({1 if on else 0})")

    def backlight(self, percent):
        """
        背光亮度 0~100%（100=最亮）。屏内 BL 值与文档一致（0 最亮、255 熄灭）。
        该参数掉电不保存。
        """
        if not 0 <= percent <= 100:
            raise HFDError("背光亮度应为 0~100")
        bl = int(round((100 - percent) * 255 / 100))
        self.cmd(f"BL({bl})")

    # ------------------------------------------------------------------ 图形

    def clr(self, color):
        """CLR(color)：整屏清屏，color 为 0~63 颜色编号。"""
        self.cmd(f"CLR({self._color(color)})")

    def ps(self, x, y, color):
        """PS(x,y,color)：画点。"""
        self.cmd(f"PS({int(x)},{int(y)},{self._color(color)})")

    def line(self, x1, y1, x2, y2, color):
        """PL(x1,y1,x2,y2,color)：画直线。"""
        self.cmd(f"PL({int(x1)},{int(y1)},{int(x2)},{int(y2)},{self._color(color)})")

    def box(self, x1, y1, x2, y2, color):
        """BOX：空心矩形。"""
        self.cmd(f"BOX({int(x1)},{int(y1)},{int(x2)},{int(y2)},{self._color(color)})")

    def box_fill(self, x1, y1, x2, y2, color):
        """BOXF：实心矩形。"""
        self.cmd(f"BOXF({int(x1)},{int(y1)},{int(x2)},{int(y2)},{self._color(color)})")

    def circle(self, x, y, r, color):
        """CIR：空心圆。"""
        self.cmd(f"CIR({int(x)},{int(y)},{int(r)},{self._color(color)})")

    def circle_fill(self, x, y, r, color):
        """CIRF：实心圆。"""
        self.cmd(f"CIRF({int(x)},{int(y)},{int(r)},{self._color(color)})")

    def set_char_bg(self, color):
        """SBC(color)：设定带底色字符（DCV*/DC48+ 模式 1）使用的底色。"""
        self.cmd(f"SBC({self._color(color)})")

    def dc(self, size, x, y, text, color, with_bg=False):
        """
        直接显示字符（无需 sGUI 控件）。size: 16/24/32（HF028 支持），
        with_bg=True 时使用 SBC() 设定的底色（DCV* 指令）。
        """
        if size not in (16, 24, 32, 48, 72, 96):
            raise HFDError("字高仅支持 16/24/32/48/72/96")
        name = f"DCV{size}" if with_bg else f"DC{size}"
        if size in (48, 72, 96):
            self.cmd(f"{name}({int(x)},{int(y)},'{text}',{self._color(color)},{1 if with_bg else 0})")
        else:
            self.cmd(f"{name}({int(x)},{int(y)},'{text}',{self._color(color)})")

    def dc16(self, x, y, text, color=15, with_bg=False):
        self.dc(16, x, y, text, color, with_bg)

    def dc24(self, x, y, text, color=15, with_bg=False):
        self.dc(24, x, y, text, color, with_bg)

    def dc32(self, x, y, text, color=15, with_bg=False):
        self.dc(32, x, y, text, color, with_bg)

    def qrcode(self, x, y, content):
        """QRCODE(x,y,content)：直接画 128x128 二维码（HF028 可用 3 参版本）。"""
        self.cmd(f"QRCODE({int(x)},{int(y)},'{content}')")

    def fs_img(self, addr, x, y, w, h, mirror=0):
        """FSIMG：按 FLASH 地址显示图片（地址可在 sGUI 图片资源区看到）。"""
        self.cmd(f"FSIMG({int(addr)},{int(x)},{int(y)},{int(w)},{int(h)},{int(mirror)})")

    # ------------------------------------------------------------------ 控件

    def jump(self, page):
        """
        JUMP(n)：跳转页面（后面同串的指令会被忽略，应单独发送）。
        注意：跳转后控件指令只对目标页的控件有效；官方 demo 例程从不调用
        JUMP，直接操作开机页上的控件即可。
        """
        self.cmd(f"JUMP({int(page)})")

    def set_txt(self, ctrl_id, text):
        """SET_TXT(id,'文本')：更新当前页面文本控件内容。"""
        text = str(text).replace("'", "")
        self.cmd(f"SET_TXT({int(ctrl_id)},'{text}')")

    def set_num(self, ctrl_id, value, digits=0):
        """SET_NUM(id,数值,位数)：更新数字控件（digits 为格式化位数）。"""
        self.cmd(f"SET_NUM({int(ctrl_id)},{value},{int(digits)})")

    def set_btn(self, ctrl_id, pressed=True):
        """SET_BTN(id,status)：1=按下状态，0=抬起状态。"""
        self.cmd(f"SET_BTN({int(ctrl_id)},{1 if pressed else 0})")

    def set_btn_img(self, ctrl_id, pressed, pic_id):
        """SET_BTN_IMG(id,status,pid)：修改图片按钮某状态下的图片编号。"""
        self.cmd(f"SET_BTN_IMG({int(ctrl_id)},{1 if pressed else 0},{int(pic_id)})")

    def set_prog(self, ctrl_id, value):
        """SET_PROG(id,0~100)：更新进度条控件。"""
        if not 0 <= int(value) <= 100:
            raise HFDError("进度值应为 0~100")
        self.cmd(f"SET_PROG({int(ctrl_id)},{int(value)})")

    def set_point(self, ctrl_id, angle):
        """SET_POINT(id,0~360)：更新指针控件角度。"""
        if not 0 <= int(angle) <= 360:
            raise HFDError("指针角度应为 0~360")
        self.cmd(f"SET_POINT({int(ctrl_id)},{int(angle)})")

    def set_qbar(self, qr_id, content):
        """QBAR(id,内容)：更新页面里的二维码控件（id 0 或 1）。"""
        self.cmd(f"QBAR({int(qr_id)},'{content}')")

    def set_fcolor(self, ctrl_id, color):
        """SET_FCOLOR(id,color)：前景/字体颜色（按键/文本/数字控件）。"""
        self.cmd(f"SET_FCOLOR({int(ctrl_id)},{self._color(color)})")

    def set_bcolor(self, ctrl_id, color, pressed=False):
        """SET_BCOLOR(抬起底色) / SET_BCOLOR2(按下底色)。"""
        name = "SET_BCOLOR2" if pressed else "SET_BCOLOR"
        self.cmd(f"{name}({int(ctrl_id)},{self._color(color)})")

    def set_frame_color(self, ctrl_id, color):
        """SET_FRAME_COLOR(id,color)：控件边框颜色。"""
        self.cmd(f"SET_FRAME_COLOR({int(ctrl_id)},{self._color(color)})")

    # ------------------------------------------------------------------ 工具

    @staticmethod
    def _color(color):
        if isinstance(color, str):
            try:
                return HFDScreen.COLORS[color.lower()]
            except KeyError:
                raise HFDError(
                    f"未知颜色名 {color!r}，可用：{', '.join(HFDScreen.COLORS)}"
                ) from None
        color = int(color)
        if not 0 <= color <= 63:
            raise HFDError("颜色编号应为 0~63")
        return color
