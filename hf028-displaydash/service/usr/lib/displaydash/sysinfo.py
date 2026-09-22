"""系统信息采集：温度/负载/内存/磁盘/网关/WAN/DNS/AP/在线人数/上下行速率。
与代理/订阅采集完全分开，独立输出到 sys.json。"""

import os
import re
import socket
import subprocess
import threading
import time

from . import state


def run(cmd, timeout=5):
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except Exception:
        return -1, ""


def read_int(path):
    try:
        return int(open(path).read().strip())
    except Exception:
        return None


def ping(host, timeout=3):
    rc, _ = run(["ping", "-c", "1", "-W", "1", host], timeout=timeout)
    return rc == 0


def _cpu_util():
    vals = []
    try:
        for line in open("/proc/stat"):
            if line.startswith("cpu "):
                vals = [int(x) for x in line.split()[1:]]
                break
    except Exception:
        return 0.0
    if not vals:
        return 0.0
    return vals


def _read_temp():
    best = first = None
    try:
        for z in sorted(os.listdir("/sys/class/thermal")):
            if not z.startswith("thermal_zone"):
                continue
            base = "/sys/class/thermal/" + z
            try:
                typ = open(base + "/type").read().strip().lower()
            except Exception:
                continue
            t = read_int(base + "/temp")
            if t is not None:
                c = t / 1000.0
                if first is None:
                    first = c
                if any(k in typ for k in ("x86_pkg", "core", "cpu", "package")):
                    best = c
    except Exception:
        pass
    return best if best is not None else first


def _mem_pct():
    total = avail = None
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemTotal:"):
                total = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                avail = int(line.split()[1])
    except Exception:
        pass
    if total and avail is not None:
        return 100.0 * avail / total
    return None


def _disk_pct():
    try:
        s = os.statvfs("/")
        return 100.0 * s.f_bavail / s.f_blocks
    except Exception:
        return None


def _get_gateway():
    rc, out = run(["ip", "-4", "route", "show", "default"])
    m = re.search(r"via\s+([0-9.]+)\s+dev\s+(\S+)", out)
    return (m.group(1), m.group(2)) if m else (None, None)


def _lan_ip():
    rc, out = run(["uci", "get", "network.lan.ipaddr"], timeout=3)
    ip = out.strip().split("/", 1)[0]
    return ip if rc == 0 and ip else None


def _dns_ok():
    rc, out = run(["nslookup", "www.baidu.com"], timeout=4)
    return rc == 0 and "Address" in out


def _net_counters(iface):
    try:
        for line in open("/proc/net/dev"):
            if line.strip().startswith(iface + ":"):
                vals = line.split(":", 1)[1].split()
                return int(vals[0]), int(vals[8])
    except Exception:
        pass
    return None


def _ap_wlan_clients(cfg):
    host = cfg.get("ap_ip", "")
    user = cfg.get("ap_user", "admin")
    pwd = cfg.get("ap_password", "")
    if not host or not pwd:
        return None
    try:
        s = socket.create_connection((host, 23), timeout=4)
        s.settimeout(1.0)

        def drain(sec):
            s.settimeout(sec)
            try:
                while s.recv(4096):
                    pass
            except Exception:
                pass

        drain(0.6)
        s.sendall(user.encode() + b"\r\n")
        drain(0.4)
        s.sendall(pwd.encode() + b"\r\n")
        drain(1.0)
        s.sendall(b"screen-length disable\r\n")
        drain(0.6)
        s.sendall(b"display wlan client\r\n")
        s.settimeout(2.5)
        buf = b""
        try:
            while True:
                c = s.recv(4096)
                if not c:
                    break
                buf += c
        except Exception:
            pass
        s.close()
        txt = buf.decode("utf-8", "replace")
        if "Clients do not exist" in txt or "no clients" in txt.lower():
            return 0
        m = re.search(r"Total number of clients[^:\uff1a]*[:：]\s*(\d+)", txt,
                      re.IGNORECASE)
        if m:
            return int(m.group(1))
        return len(re.findall(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b",
                              txt)) or 0
    except Exception:
        return None


class SysCollector:
    """系统采集器：main 循环每 ~2s 调 tick()，发布前调 frame()。"""

    def __init__(self, cfg):
        self.cfg = cfg
        self.window = []          # (mono, temp, cpu)
        self._last_cpu = None
        self._gw = None
        _wan = (cfg.get("wan_iface") or "").strip().lower()
        self._auto_iface = _wan in ("", "auto")
        self._iface = "" if self._auto_iface else _wan
        self._last_net = 0.0
        self._last_dns = -120.0
        self._last_ap = 0.0
        self._last_clients = -120.0
        self._pub_counter = None
        self.online = None
        self.gw_ok = None
        self.pub_ok = None
        self.dns_ok = None
        self.ap_ok = None
        self.temp_now = None
        self.mem_now = None
        self.disk_now = None

    def tick(self, now):
        cfg = self.cfg
        if now - (self._last_net or 0) >= cfg.getint("net_check_sec", 30) \
                or not self._last_net:
            self._last_net = now
            gw, dev = _get_gateway()
            if dev and self._auto_iface:
                self._iface = dev
            self._gw = gw
            self.gw_ok = bool(gw) and ping(gw)
            self.pub_ok = ping(cfg.get("public_ip", "223.5.5.5"))
        if now - self._last_dns >= cfg.getint("dns_check_sec", 60):
            self._last_dns = now
            self.dns_ok = _dns_ok()
        if now - self._last_ap >= cfg.getint("ap_check_sec", 30):
            self._last_ap = now
            self.ap_ok = ping(cfg.get("ap_ip", "")) if cfg.get("ap_ip") else None
        if now - self._last_clients >= cfg.getint("ap_clients_check_sec", 10):
            self._last_clients = now
            host = cfg.get("ap_ip", "")

            def poll():
                self.online = _ap_wlan_clients(self.cfg) if host else None

            threading.Thread(target=poll, daemon=True).start()
        if not self.window or now - self.window[-1][0] >= 4:
            cpu = self._cpu_sample()
            temp = _read_temp()
            self.temp_now = temp
            self.mem_now = _mem_pct()
            self.disk_now = _disk_pct()
            self.window.append((now, temp, cpu))
            self.window = [x for x in self.window if x[0] > now - 70]

    def _cpu_sample(self):
        v = _cpu_util()
        if not v:
            return 0.0
        if self._last_cpu is not None:
            dt = max(1, sum(v) - sum(self._last_cpu))
            idle = (v[3] + v[4]) - (self._last_cpu[3] + self._last_cpu[4])
            self._last_cpu = v
            return max(0.0, min(100.0, 100.0 * (dt - idle) / dt))
        self._last_cpu = v
        return 0.0

    def frame(self, now):
        """发布帧：温度/负载取窗口最大、速率取窗口均值，写 sys.json。"""
        tmps = [x[1] for x in self.window if x[1] is not None]
        utils = [x[2] for x in self.window]
        temp = max(tmps) if tmps else _read_temp()
        load = max(utils) if utils else 0.0
        mem = _mem_pct()
        disk = _disk_pct()
        dl = ul = 0.0
        cnt = _net_counters(self._iface)
        if cnt:
            if self._pub_counter:
                dt = now - self._pub_counter[0]
                if dt > 0:
                    dl = max(0.0, (cnt[0] - self._pub_counter[1]) * 8 / dt / 1e6)
                    ul = max(0.0, (cnt[1] - self._pub_counter[2]) * 8 / dt / 1e6)
            self._pub_counter = (now, cnt[0], cnt[1])
        self.window = []
        data = {
            "ts": now,
            "iface": self._iface,
            "gw": self._gw,
            "lan_ip": _lan_ip(),
            "gw_ok": self.gw_ok,
            "pub_ok": self.pub_ok,
            "dns_ok": self.dns_ok,
            "ap_ok": self.ap_ok,
            "online": self.online,
            "temp": temp,
            "load_pct": load,
            "mem_pct": mem,
            "disk_pct": disk,
            "dl_mbps": dl,
            "ul_mbps": ul,
        }
        state.write_json(state.SYS_FILE, data)
        return data
