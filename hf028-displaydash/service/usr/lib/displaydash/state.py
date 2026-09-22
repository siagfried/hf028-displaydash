"""运行状态存取：系统采集与代理/订阅采集分开写，互不依赖。"""

import json
import os
import tempfile


STATE_DIR = "/tmp/displaydash"
SYS_FILE = STATE_DIR + "/sys.json"       # 系统采集（温度/负载/网络/AP…）
PROXY_FILE = STATE_DIR + "/proxy.json"   # 代理/订阅采集（节点/出口/订阅…）


def _ensure_dir():
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
    except Exception:
        pass


def write_json(path, data):
    _ensure_dir()
    try:
        fd, tmp = tempfile.mkstemp(dir=STATE_DIR, prefix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass


def read_json(path, default=None):
    if default is None:
        default = {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def read_sys():
    return read_json(SYS_FILE)


def read_proxy():
    return read_json(PROXY_FILE)
