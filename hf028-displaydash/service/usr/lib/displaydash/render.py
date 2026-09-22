"""渲染层：把 sys.json + proxy.json 的状态转成串口屏命令。
只依赖 UCI 配置与两个状态文件，不关心数据从哪来。"""

import datetime
import calendar
import os
import re
import time

from . import state


CODE_CN = {
    "WAN:DN": "网络异常",
    "NET:DN": "无外网",
    "DNS:DN": "域名异常",
    "AP:DN": "AP掉线",
    "SUB:ERR": "订阅异常",
    "SRV:DN": "代理异常",
    "GGL:DN": "翻墙失败",
    "GGL:SLOW": "翻墙缓慢",
    "LOAD:HI": "负载过高",
    "MEM:LO": "内存用尽",
    "TEMP:HI": "温度过高",
    "DISK:LO": "存储不足",
}


def cn_code(code):
    return CODE_CN.get(code, str(code))[:4]


def gb_safe(s):
    if s is None:
        return ""
    out = []
    for ch in str(s):
        if ch == "'":
            continue
        try:
            ch.encode("gb2312")
            out.append(ch)
        except Exception:
            continue
    return re.sub(r"\s+", " ", "".join(out)).strip()

def qr_safe(s):
    """保留可传输字符；去掉串口命令中的单引号和换行。"""
    if s is None:
        return ""
    out = []
    for ch in str(s):
        if ch in ("'", "\r", "\n"):
            continue
        try:
            ch.encode("gb2312")
            out.append(ch)
        except Exception:
            continue
    return "".join(out)


def qr_field(s):
    """Escape a WiFi QR field according to the WIFI: payload format."""
    value = qr_safe(s)
    return (value.replace("\\", "\\\\")
                 .replace(";", "\\;")
                 .replace(",", "\\,")
                 .replace(":", "\\:")
                 .replace('"', '\\"'))


def qr_content(cfg):
    """按配置生成二维码内容；关闭 WiFi 二维码时显示管理地址。"""
    default = "http://192.168.22.1"
    if not cfg.getbool("qr_enable", False):
        return default
    ssid = qr_field(cfg.get("qr_ssid"))
    if not ssid:
        return default
    pwd = qr_field(cfg.get("qr_password"))
    if pwd:
        return "WIFI:T:WPA;S:%s;P:%s;;" % (ssid, pwd)
    return "WIFI:T:nopass;S:%s;;" % ssid


def fmt_bytes(v, sw=100):
    if v >= sw * 1_000_000:
        return f"{v / 1_000_000_000:.1f}GB/s"
    if v >= sw * 1000:
        return f"{v / 1_000_000:.1f}MB/s"
    if v >= 1000:
        return f"{int(round(v / 1000))}KB/s"
    return f"{int(v)}B/s"


def status(cfg, sysd, px, grace_active=True):
    """返回 (level, code)；OK/WARN/FAIL。"""
    srv_dead = cfg.get("service_proc") != "none" and px.get("srv_ok") is False
    if grace_active and not (srv_dead and px.get("srv_seen")):
        return "OK", ""
    fails, warns = [], []
    if sysd.get("gw_ok") is False:
        fails.append("WAN:DN")
    elif sysd.get("pub_ok") is False:
        warns.append("NET:DN")
    if sysd.get("dns_ok") is False:
        fails.append("DNS:DN")
    if sysd.get("ap_ok") is False:
        fails.append("AP:DN")
    if not px.get("has_sub_urls"):
        fails.append("SUB:ERR")
    elif not px.get("manual_node") and px.get("sub_refresh") == "fail":
        fails.append("SUB:ERR")
    if srv_dead:
        fails.append("SRV:DN")
    if px.get("google_ok") is False:
        fails.append("GGL:DN")
    elif px.get("google_ms") is not None and \
            px["google_ms"] > cfg.getint("google_ms", 800):
        warns.append("GGL:SLOW")
    if sysd.get("load_pct", 0) >= cfg.getint("load_fail", 95):
        fails.append("LOAD:HI")
    elif sysd.get("load_pct", 0) >= cfg.getint("load_warn", 75):
        warns.append("LOAD:HI")
    mem = sysd.get("mem_pct")
    if mem is not None:
        if mem < cfg.getint("mem_fail", 5):
            fails.append("MEM:LO")
        elif mem < cfg.getint("mem_warn", 10):
            warns.append("MEM:LO")
    temp = sysd.get("temp")
    if temp is not None:
        if temp >= cfg.getint("temp_fail", 85):
            fails.append("TEMP:HI")
        elif temp >= cfg.getint("temp_warn", 70):
            warns.append("TEMP:HI")
    disk = sysd.get("disk_pct")
    if disk is not None:
        if disk < cfg.getint("disk_fail", 5):
            fails.append("DISK:LO")
        elif disk < cfg.getint("disk_warn", 10):
            warns.append("DISK:LO")
    if fails:
        return "FAIL", fails[0]
    if warns:
        return "WARN", warns[0]
    return "OK", ""


def status_text(cfg, sysd, px, grace_active=True, ap_pending=False):
    level, code = status(cfg, sysd, px, grace_active)
    if ap_pending:
        return "AP启动中", level, code
    if level == "OK":
        return "系统正常", level, code
    if level == "WARN":
        return "警告!%s" % cn_code(code), level, code
    return "故障!%s" % cn_code(code), level, code


def _fit(s, maxw=100):
    out = ""
    for c in s:
        if sum(8 if ord(x) < 256 else 16 for x in out + c) > maxw:
            break
        out += c
    return out


def _exp_line(reset_days, expire, cfg_mtime, now_d=None, style="month_start"):
    now_d = now_d or datetime.date.today()
    expire = str(expire or "")
    try:
        ey, em = int(expire[:4]), int(expire[5:7])
    except Exception:
        ey = em = None
    def reset_text(reset_date, remaining):
        date_text = ("%02d-%02d" % (reset_date.month, reset_date.day)
                     if reset_date else "--")
        return "重置:%s 剩余%d天" % (date_text, max(0, int(remaining)))

    if ey and em and (now_d.year, now_d.month) == (ey, em):
        try:
            expiry_date = datetime.date(ey, em, int(expire[8:10]))
            return reset_text(expiry_date, (expiry_date - now_d).days)
        except Exception:
            pass
    if reset_days is not None:
        elapsed = 0
        if cfg_mtime:
            try:
                elapsed = max(0, int((time.time() - cfg_mtime) / 86400))
            except Exception:
                elapsed = 0
        remaining = max(0, int(reset_days) - elapsed)
        expiry_date = None
        if ey and em:
            try:
                expiry_date = datetime.date(ey, em, int(expire[8:10]))
            except Exception:
                pass
        return reset_text(expiry_date, remaining)
    day = None
    if style == "expire_day":
        try:
            day = int(expire[8:10])
        except Exception:
            day = None
    if day is None:
        day = 1
    current_day = min(day, calendar.monthrange(now_d.year, now_d.month)[1])
    if now_d.day <= current_day:
        rd = datetime.date(now_d.year, now_d.month, current_day)
    else:
        y = now_d.year + (1 if now_d.month == 12 else 0)
        mo = 1 if now_d.month == 12 else now_d.month + 1
        rd = datetime.date(y, mo, min(day, calendar.monthrange(y, mo)[1]))
    return reset_text(rd, (rd - now_d).days)


def build_cmds(cfg, sysd, px, status_line="系统正常", qr="", qr_update=True):
    """生成 SET_TXT 命令；控件 ID 全部可由 UCI 映射。"""
    ids = {
        "clock": cfg.getint("id_clock", 0),
        "status": cfg.getint("id_status", 1),
        "ip": cfg.getint("id_ip", 2),
        "temp": cfg.getint("id_temp", 3),
        "up": cfg.getint("id_up", 4),
        "dl": cfg.getint("id_dl", 5),
        "sub": cfg.getint("id_sub", 6),
        "node": cfg.getint("id_node", 7),
        "prog": cfg.getint("id_prog", 8),
        "usage": cfg.getint("id_usage", 9),
        "exit": cfg.getint("id_exit", 10),
        "reset": cfg.getint("id_reset", 11),
        "online": cfg.getint("id_online", 12),
        "qr": cfg.getint("id_qr", 0),
    }

    def txt(idk, s):
        return f"SET_TXT({ids[idk]},'{gb_safe(s)}')"

    now = time.localtime()
    clock = "%s %s" % (time.strftime("%H:%M", now),
                       time.strftime("%a", now).upper())
    online = "-" if sysd.get("online") is None else str(sysd["online"])
    temp = sysd.get("temp")
    temp = 0 if temp is None else temp
    mem = sysd.get("mem_pct")
    mem_used = (100 - mem) if mem is not None else None
    sw = cfg.getint("speed_switch", 100)
    dl = sysd.get("dl_mbps", 0.0) * 1e6 / 8
    ul = sysd.get("ul_mbps", 0.0) * 1e6 / 8

    name = px.get("sub_name") or "-"
    sub_text = "订阅:%s" % _fit(name, 120)
    node_text = "节点:%s" % (px.get("node_label") or
                            px.get("node_addr") or "-")
    ip_line = "管理:%s" % (sysd.get("lan_ip") or "-")

    total = px.get("sub_total_gb")
    used = px.get("sub_used_gb")
    remain = px.get("sub_remain_gb")
    pct = 0
    usage = ""
    if total and total > 0 and used is not None:
        # 已用/总流量 形式；进度条同口径
        pct = int(min(100, max(0, 100.0 * used / total)))
        usage = "流量:已用%.2fG/%.0fG" % (used, total)
    elif used is not None:
        usage = "流量:已用%.2fG" % used
    elif remain is not None:
        usage = "流量:剩余%.2fG" % remain

    expire = px.get("sub_expire") or "N/A"
    reset_days = px.get("sub_reset_days")
    try:
        mtime = os.path.getmtime(state.PROXY_FILE + ".sub")
    except Exception:
        mtime = None
    if px.get("manual_node"):
        reset_line = ""
    else:
        reset_line = _exp_line(reset_days, expire, mtime,
                               style=(px.get("reset_style") or "month_start"))

    exit_ip = "出口:%s" % (px.get("exit_ip") or "-")
    if px.get("manual_node") and not px.get("has_sub_urls"):
        sub_text = "无订阅文件或链接"
        usage = ""
        reset_line = ""
        pct = 0

    cmds = [
        txt("clock", clock),
        txt("status", status_line),
        txt("ip", ip_line),
        txt("temp", ("温度:%.0fC 内存:%.0f%%" % (temp, mem_used))
            if mem_used is not None else "温度:%.0fC" % temp),
        txt("up", "UP:%s" % fmt_bytes(ul, sw)),
        txt("dl", "DL:%s" % fmt_bytes(dl, sw)),
        txt("sub", sub_text),
        txt("node", node_text),
        txt("usage", usage),
        txt("exit", exit_ip),
        txt("reset", reset_line),
        txt("online", "User:%s" % online),
        f"SET_PROG({ids['prog']},{pct})",
    ]
    if qr_update:
        # 未显式传入内容时按当前配置生成（关闭时为管理地址）。
        # 只有外部明确要求空内容时才使用带引号的空参数，避免
        # QBAR(id,) 被部分固件忽略。
        qr = qr_content(cfg) if qr == "" else qr
        qr = "''" if qr == "" else qr
        # QBAR's second argument is an unquoted string (per HF028 protocol).
        # Quoting it makes the quote characters part of the QR payload.
        cmds.append(f"QBAR({ids['qr']},{qr})")
    return cmds
