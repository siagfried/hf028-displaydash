"""UCI 配置读取（/etc/config/<name>），支持热加载。"""

import os
import shlex
import time


SCREEN_PROFILE_KEYS = {
    "page_logo_plain", "page_progress", "page_data",
    "id_clock", "id_status", "id_ip", "id_temp", "id_up", "id_dl",
    "id_sub", "id_node", "id_prog", "id_usage", "id_exit", "id_reset",
    "id_online", "id_prog_logo", "id_qr", "color_normal",
}


class Cfg:
    """扁平读取一个 UCI 配置文件的所有 option。

    示例：displaydash.@main[0].brightness_day → 直接以 brightness_day 读取。
    """

    def __init__(self, name="displaydash"):
        self.name = name
        self.path = "/etc/config/" + name
        self.vals = {}
        self.subs = []
        self.screens = []
        self.screen = {}
        self._mtime = None
        self._screen_mtime = None
        self.load()

    def load(self):
        vals = {}
        subs = []
        screens = []
        cur = None
        try:
            with open(self.path) as f:
                for raw in f:
                    # UCI uses shell-style quoting; # inside quotes is data.
                    parts = shlex.split(raw, comments=True, posix=True)
                    if not parts:
                        continue
                    if parts[0] == "config" and len(parts) >= 2:
                        if parts[1] in ("sub", "screen"):
                            cur = {"__type": parts[1],
                                   "__name": parts[2] if len(parts) >= 3 else ""}
                            (subs if parts[1] == "sub" else screens).append(cur)
                        else:
                            cur = None
                        continue
                    if parts[0] == "option" and len(parts) == 3:
                        key, val = parts[1:]
                        if cur is not None:
                            cur[key] = val
                        else:
                            vals[key] = val
        except Exception:
            pass
        try:
            cur = None
            with open("/etc/config/displaydash-screen") as f:
                for raw in f:
                    parts = shlex.split(raw, comments=True, posix=True)
                    if not parts:
                        continue
                    if parts[0] == "config" and len(parts) >= 2:
                        if parts[1] == "screen":
                            cur = {"__type": "screen",
                                   "__name": parts[2] if len(parts) >= 3 else ""}
                            screens.append(cur)
                        else:
                            cur = None
                        continue
                    if parts[0] == "option" and len(parts) == 3 and cur is not None:
                        cur[parts[1]] = parts[2]
        except Exception:
            pass
        self.vals = vals
        self.subs = subs
        self.screens = screens
        profile_name = vals.get("screen_profile", "")
        self.screen = next((s for s in screens
                            if s.get("__name") == profile_name or
                            s.get("profile_name") == profile_name), {})
        try:
            self._mtime = os.path.getmtime(self.path)
        except Exception:
            self._mtime = None
        try:
            self._screen_mtime = os.path.getmtime(
                "/etc/config/displaydash-screen")
        except Exception:
            self._screen_mtime = None

    def reload_if_changed(self, interval=2.0, last_check=None):
        """调用方每 interval 检查一次文件 mtime，有变化则重载。"""
        try:
            mt = os.path.getmtime(self.path)
        except Exception:
            mt = None
        try:
            screen_mt = os.path.getmtime("/etc/config/displaydash-screen")
        except Exception:
            screen_mt = None
        if mt != self._mtime or screen_mt != self._screen_mtime:
            self.load()
            return True
        return False

    def get(self, key, default=None):
        if key in SCREEN_PROFILE_KEYS and self.screen.get(key) not in (None, ""):
            return self.screen[key]
        v = self.vals.get(key)
        return default if v in (None, "") else v

    def getint(self, key, default=0):
        try:
            return int(float(self.get(key, default)))
        except Exception:
            return default

    def getfloat(self, key, default=0.0):
        try:
            return float(self.get(key, default))
        except Exception:
            return default

    def sub_for(self, url):
        """按订阅 URL 匹配 config sub 段（url_match 是 URL 子串）。"""
        if not url:
            return {}
        for s in self.subs:
            frag = (s.get("url_match") or "").strip()
            if frag and frag in url:
                return s
        return {}

    def getbool(self, key, default=False):
        return self.get(key, "1" if default else "0") in ("1", "true", "yes", "on")
