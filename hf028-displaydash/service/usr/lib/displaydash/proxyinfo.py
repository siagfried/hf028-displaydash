"""代理与订阅采集（仅 HomeProxy/sing-box），与系统采集分离。

输出到 proxy.json，字段直接供渲染使用；不再依赖任何外部 shell 脚本。
"""

import hashlib
import os
import re
import socket
import ssl
import subprocess
import threading
import time
import urllib.parse
import urllib.request

from . import state


def run(cmd, timeout=5):
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except Exception:
        return -1, ""


def uci_get(opt):
    rc, out = run(["uci", "get", opt], timeout=3)
    v = out.strip()
    return v if rc == 0 and v else ""


def pgrep_running(name):
    rc, _ = run(["pgrep", "-f", name], timeout=3)
    return rc == 0


_HP_URL_CACHE = (0.0, [])


def _hp_urls():
    """HomeProxy 订阅 URL 列表（3 秒缓存）。

    兼容命名节 homeproxy.subscription.subscription_url 与匿名节
    homeproxy.@subscription[N].subscription_url（两者都可能是 UCI list）。
    """
    global _HP_URL_CACHE
    if _HP_URL_CACHE[0] > time.time() - 3:
        return _HP_URL_CACHE[1]
    rc, out = run(["uci", "show", "homeproxy"], timeout=6)
    urls = []
    if rc == 0:
        for m in re.finditer(
                r"homeproxy\.(?:@subscription\[\d+\]|subscription)"
                r"\.subscription_url=(.*)$", out, re.M):
            urls.extend(
                u.replace("\\'", "'")
                for u in re.findall(r"'((?:[^'\\]|\\.)*)'", m.group(1))
                if u)
    _HP_URL_CACHE = (time.time(), urls)
    return urls
def _sub_hash(url):
    return hashlib.md5(url.split("#", 1)[0].encode("utf-8")).hexdigest()


def _sub_title(url):
    main, _, frag = url.partition("#")
    if frag:
        try:
            return urllib.parse.unquote(frag)
        except Exception:
            return frag
    m = re.match(r"^[a-zA-Z]+://([^/]+)", main)
    return m.group(1) if m else main


def _current_sub():
    h = uci_get("homeproxy.config.main_node")
    gh = uci_get("homeproxy.%s.grouphash" % h) if h else ""
    if not gh:
        return {}
    for u in _hp_urls():
        if _sub_hash(u) == gh:
            return {"url": u, "title": _sub_title(u), "hash": gh}
    return {}


def _curl(url, timeout=10):
    rc, out = run(["curl", "-s", "--max-time", str(timeout), url],
                  timeout=timeout + 3)
    return out.strip()


def _curl_ip(url, timeout=8):
    ip = _curl(url, timeout)
    return ip if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip) else ""


class ProxyCollector:
    """代理/订阅采集器。tick() 做定时检查，frame() 出发布快照。"""

    def __init__(self, cfg):
        self.cfg = cfg
        self.srv_ok = None
        self.srv_seen = False
        self.google_ok = None
        self.google_ms = None
        self.last_srv = -120.0
        self.last_google = -120.0
        self.last_sub = 0.0
        self.last_net = 0.0
        self.prev_subhash = None
        self.prev_key = None
        self.sub_running = False
        self.net_running = False
        self.net_req_time = 0.0
        self.net_hold_until = 0.0
        self.net_hold_tag = ""
        self.net_hold = False
        self.sub_req_time = 0.0

    # ---------------- 定时检查 ----------------
    def tick(self, now):
        cfg = self.cfg
        if now - self.last_srv >= cfg.getint("srv_check_sec", 10):
            self.last_srv = now
            if pgrep_running("sing-box"):
                self.srv_ok = True
                self.srv_seen = True
            else:
                self.srv_ok = False
        if now - self.last_google >= cfg.getint("google_check_sec", 60):
            self.last_google = now
            self.google_ok, self.google_ms = self._google()
        # 出口刷新失败/节点切换后：最多 15 秒重试直到成功
        net = state.read_json(state.PROXY_FILE + ".net")
        if net.get("stale") and \
                now - self.last_net >= cfg.getint("exit_retry_sec", 30):
            self.last_net = now
            self.refresh_net()

    def _google(self):
        url = self.cfg.get("google_url",
                           "http://www.gstatic.com/generate_204")
        rc, out = run(
            ["curl", "-sk", "-o", "/dev/null", "-w", "%{http_code} %{time_total}",
             "--connect-timeout", "4", "--max-time", "8", url], timeout=12)
        parts = out.split()
        ok = rc == 0 and parts and parts[0] in ("200", "204")
        ms = None
        if len(parts) > 1:
            try:
                ms = int(float(parts[1]) * 1000)
            except Exception:
                ms = None
        return ok, ms

    # ---------------- 节点变化检测 ----------------
    def check_change(self, now):
        h = uci_get("homeproxy.config.main_node")
        cur = _current_sub()
        urls = tuple(_hp_urls())
        key = (h, urls, cur.get("hash", ""),
               uci_get("homeproxy.%s.label" % h) if h else "",
               uci_get("homeproxy.%s.address" % h) if h else "")
        changed = self.prev_key is not None and self.prev_key != key
        self.prev_key = key
        if changed:
            self.net_hold = True
            self.net_hold_until = time.monotonic() + \
                self.cfg.getint("exit_retry_sec", 30)
            self.net_req_time = time.time()
            self.net_hold_tag = key[3] or "homeproxy"
            self.refresh_net()
        if self.prev_subhash != cur.get("hash"):
            self.prev_subhash = cur.get("hash", "")
            if cur.get("hash") and self.refresh_sub():
                self.sub_req_time = time.time()

        # 定时订阅刷新：间隔取“当前订阅自己的 sub_refresh_sec”
        if cur.get("hash") and not self.sub_running:
            ov = self.cfg.sub_for(cur.get("url", ""))
            try:
                iv = int(float(
                    (ov and ov.get("sub_refresh_sec")) or 3600))
            except Exception:
                iv = 3600
            if iv > 0 and now - self.last_sub >= iv:
                self.last_sub = now
                self.refresh_sub()
        return changed

    # ---------------- 出口/公网 IP ----------------
    def refresh_net(self):
        if self.net_running:
            return False

        def work():
            self.net_running = True
            try:
                pub = _curl_ip("https://ip.3322.net")
                prx = _curl_ip("https://api.ipify.org")
                data = {"public": pub, "proxy": prx, "public_cc": "",
                        "proxy_cc": "", "node": self.net_hold_tag,
                        "stale": 0}
                for k, ip in (("public_cc", pub), ("proxy_cc", prx)):
                    if ip:
                        rc, out = run(
                            ["curl", "-s", "--max-time", "5",
                             "http://ip-api.com/csv/%s?fields=countryCode" % ip])
                        code = out.strip().split(",")[0] if out.strip() else ""
                        data[k] = code.upper() if code else ""
                if not (pub and prx):
                    old = state.read_json(state.PROXY_FILE + ".net")
                    data["public"] = pub or old.get("public", "")
                    data["proxy"] = prx or old.get("proxy", "")
                    data["public_cc"] = data["public_cc"] or old.get("public_cc", "")
                    data["proxy_cc"] = data["proxy_cc"] or old.get("proxy_cc", "")
                    data["stale"] = 1
                state.write_json(state.PROXY_FILE + ".net", data)
            finally:
                self.net_running = False

        threading.Thread(target=work, daemon=True).start()
        return True

    def _net_done(self):
        try:
            mtime_ok = os.path.getmtime(state.PROXY_FILE + ".net") >= \
                self.net_req_time
        except Exception:
            mtime_ok = False
        if not mtime_ok:
            return False
        net = state.read_json(state.PROXY_FILE + ".net")
        return not net.get("stale") and net.get("node") == self.net_hold_tag

    # ---------------- 订阅信息（内置抓取，无 subinfo.sh） ----------------
    def refresh_sub(self):
        if self.sub_running:
            return False

        def work():
            self.sub_running = True
            try:
                cur = _current_sub()
                url = cur.get("url", "")
                h = cur.get("hash", "")
                data = {"hash": h, "name": "", "used": "N/A",
                        "total": "N/A", "remain": "N/A", "reset": "N/A",
                        "expire": "N/A", "refresh": "none",
                        "remain_gb": None, "used_gb": None, "total_gb": None}
                old = state.read_json(state.PROXY_FILE + ".sub")
                if not url:
                    if old.get("hash") == "":
                        data.update(old)
                    state.write_json(state.PROXY_FILE + ".sub", data)
                    return
                ov = self.cfg.sub_for(url)
                head = self._fetch_headers(url, ov)
                if head:
                    self._apply_header(data, head)
                    data["hash"] = h
                    data["refresh"] = "ok"
                    data["name"] = head.get("filename", "")
                else:
                    data["hash"] = h
                    if old.get("hash") != h:
                        data["refresh"] = "fail"
                        data["name"] = ""
                    else:
                        data.update({k: old.get(k, v) for k, v in data.items()
                                    if old.get(k) not in (None, "")})
                        data["refresh"] = "fail"
                rl = self._hp_remain_label(h)
                if rl is not None:
                    data["remain_gb"] = rl
                    data["remain"] = "%.2f GB" % rl
                state.write_json(state.PROXY_FILE + ".sub", data)
            finally:
                self.sub_running = False

        threading.Thread(target=work, daemon=True).start()
        self.last_sub = time.monotonic()
        return True

    def _fetch_headers(self, url, ov=None):
        """抓订阅链接响应头；服务器只给 Clash 系 UA 返回用户信息。"""
        sub_ua = (ov and ov.get("subscription_ua")) or ""
        uas = [sub_ua or "clash-verge/v2.4.5",
               "Wget/1.21 (HomeProxy, like v2rayN)"]
        for ua in uas[:1 if sub_ua else 2]:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": ua})
                ctx = ssl._create_unverified_context()
                with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
                    hd = {k.lower(): v for k, v in r.headers.items()}
                    return self._parse_header(hd)
            except Exception:
                continue
        return None

    @staticmethod
    def _parse_header(hd):
        out = {}
        ui = hd.get("subscription-userinfo", "")
        m = re.search(r"upload=(\d+)", ui)
        up = int(m.group(1)) if m else 0
        m = re.search(r"download=(\d+)", ui)
        dn = int(m.group(1)) if m else 0
        m = re.search(r"total=(\d+)", ui)
        total = int(m.group(1)) if m else 0
        m = re.search(r"expire=(\d+)", ui)
        if up or dn:
            out["used_gb"] = round((up + dn) / 1073741824.0, 2)
            out["used"] = "%.2f GB" % out["used_gb"]
        if total:
            out["total_gb"] = round(total / 1073741824.0, 2)
            out["total"] = "%.2f GB" % out["total_gb"]
        if m:
            try:
                exp = int(m.group(1))
                # expire=0 表示未设置到期，不转成 1970-01-01
                if exp > 0:
                    out["expire"] = time.strftime(
                        "%Y-%m-%d", time.localtime(exp))
            except Exception:
                pass
        cd = hd.get("content-disposition", "")
        fm = re.search(r"filename\*?=\s*(?:UTF-8'')?([^;]+)", cd, re.I)
        if fm:
            try:
                out["filename"] = urllib.parse.unquote(
                    fm.group(1).strip().strip('"'))
            except Exception:
                out["filename"] = ""
        return out

    @staticmethod
    def _apply_header(data, head):
        for k in ("used_gb", "total_gb", "used", "total", "expire", "filename"):
            if head.get(k) is not None:
                data[k] = head[k]

    @staticmethod
    def _hp_remain_label(hash_match):
        rc, out = run(["uci", "show", "homeproxy"], timeout=6)
        if rc != 0:
            return None
        m = re.search(
            r"homeproxy\.([0-9a-f]{32})\.label='剩余流量[：:]\s*([\d.]+)\s*"
            r"([KMGT])?i?B?'", out)
        if not m:
            return None
        if hash_match and uci_get("homeproxy.%s.grouphash" % m.group(1)) != \
                hash_match:
            return None
        val = float(m.group(2))
        unit = m.group(3) or "G"
        return val * {"K": 1.0 / 1048576.0, "M": 1.0 / 1024.0,
                      "G": 1.0, "T": 1024.0}[unit]

    # ---------------- 发布快照 ----------------
    def frame(self):
        cfg = self.cfg
        h = uci_get("homeproxy.config.main_node")
        cur = _current_sub()
        label = uci_get("homeproxy.%s.label" % h) if h else ""
        addr = uci_get("homeproxy.%s.address" % h) if h else ""
        net = state.read_json(state.PROXY_FILE + ".net")
        sub = state.read_json(state.PROXY_FILE + ".sub")

        # 订阅数据：只有 hash 匹配当前订阅才采用（防串数据）
        if sub.get("hash") != cur.get("hash"):
            sub = {}

        # 手工覆盖优先级：服务器 > 默认/推算 > 手工填写。
        # 手工值先取“默认(main)”，若当前订阅命中了 config sub 段则用该段覆盖。
        ov = cfg.sub_for(cur.get("url", ""))

        def _man(key):
            return ov.get(key, "") if ov else ""

        def _manf(key):
            try:
                return float(_man(key))
            except Exception:
                return 0.0

        used = sub.get("used_gb")
        total = sub.get("total_gb")
        remain = sub.get("remain_gb")
        if total is None and used is not None and remain is not None:
            total = round(used + remain, 2)
        if used is None and total is not None and remain is not None:
            used = max(0.0, round(total - remain, 2))
        if remain is None and total is not None and used is not None:
            remain = max(0.0, round(total - used, 2))
        if used is None and _manf("sub_used_manual") > 0:
            used = _manf("sub_used_manual")
        if total is None and _manf("sub_total_manual") > 0:
            total = _manf("sub_total_manual")

        name = _man("sub_name_manual") or sub.get("name") or \
            cur.get("title") or ("手动节点" if not cur else "-")
        _exp = sub.get("expire")
        if _exp in (None, "", "N/A"):
            _exp = ""
        expire = _exp or _man("sub_expire_manual") or ""
        reset = sub.get("reset")
        rst = (ov and ov.get("reset_style")) or "month_start"

        net_ready = not net.get("stale") and net.get("node") == label
        if self.net_hold:
            if self._net_done() or time.monotonic() >= self.net_hold_until:
                self.net_hold = False
        hold = self.net_hold

        data = {
            "ts": time.time(),
            "srv_ok": self.srv_ok,
            "srv_seen": self.srv_seen,
            "google_ok": self.google_ok,
            "google_ms": self.google_ms,
            "node_hash": h,
            "node_label": label,
            "node_addr": addr,
            "manual_node": not bool(cur),
            "has_sub_urls": bool(_hp_urls()),
            "sub_hash": cur.get("hash", ""),
            "sub_title": cur.get("title", ""),
            "sub_name": name,
            "sub_used_gb": used,
            "sub_total_gb": total,
            "sub_remain_gb": remain,
            "sub_expire": expire,
            "sub_reset_days": int(reset) if str(reset).isdigit() else None,
            "reset_style": rst,
            "sub_refresh": sub.get("refresh", "none"),
            "public_ip": net.get("public", ""),
            "public_cc": net.get("public_cc", ""),
            "exit_ip": net.get("proxy", ""),
            "exit_cc": net.get("proxy_cc", ""),
            "net_stale": net.get("stale", 1),
            "net_hold": hold,
            "net_synced": net_ready,
            "change_detected": bool(self.net_hold),
        }
        state.write_json(state.PROXY_FILE, data)
        return data
