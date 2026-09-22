"""HF028 看板常驻服务（OpenWrt）。

职责：定时采集（系统/代理订阅各自独立）→ 渲染 → 串口发布。
不再调用 subinfo.sh，也不包含任何 OpenClash 逻辑。
同一技术串口屏可复制配置 + 以 --config <name> 启动第二实例。
"""

import os
import signal
import sys
import time

from . import render
from .cfg import Cfg
from .proxyinfo import ProxyCollector
from .sysinfo import SysCollector, _net_counters
from .hfd import HFDScreen

LOG = "/tmp/displaydash.log"


def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + str(msg)
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line, flush=True)


def _grace_exit(signum, frame):
    try:
        if _scr:
            _scr.cmd("BL(153)", read_timeout=1.0)
            _scr.jump(_cfg.getint("page_logo_plain", 0))
    except Exception:
        pass
    log("signal %s, back to logo page" % signum)
    os._exit(0)


_scr = None
_cfg = None


def _open_screen(cfg):
    return HFDScreen(cfg.get("port", "/dev/ttyUSB0"),
                     baudrate=cfg.getint("baud", 115200))


def _brightness(cfg, current):
    h = time.localtime().tm_hour
    ds = cfg.getint("day_start_hour", 7)
    ns = cfg.getint("night_start_hour", 22)
    day = ds <= h < ns
    pct = cfg.getint("brightness_day", 60) if day else \
        cfg.getint("brightness_night", 20)
    bl = max(0, min(255, round(255 - pct * 2.55)))
    return bl, pct, day


def _try_open(cfg):
    """尝试打开串口屏；失败返回 None（服务继续采集，网页仍可看数据）。"""
    global _scr
    scr = None
    try:
        scr = _open_screen(cfg)
        _scr = scr
        scr.jump(cfg.getint("page_logo_plain", 0))
        d = cfg.getint("direction", 1)
        if d >= 0:
            scr.cmd("DIR(%d)" % d, read_timeout=5.0)
            time.sleep(0.4)
            scr.jump(0)
            time.sleep(0.4)
            log("direction applied DIR(%d)" % d)
        scr.jump(cfg.getint("page_progress", 1))
        try:
            scr.cmd("BL(153)", read_timeout=2.0)
        except Exception:
            pass
        log("screen opened: %s (progress page)" %
            cfg.get("port", "/dev/ttyUSB0"))
        return scr
    except Exception as e:
        log("open screen failed: %s" % e)
        try:
            if scr is not None:
                scr.close()
        except Exception:
            pass
        _scr = None
        return None


def main(argv=None):
    global _scr, _cfg
    argv = argv if argv is not None else sys.argv
    once = "--once" in argv
    cfg_name = "displaydash"
    debug_interval = 0
    if "--config" in argv:
        cfg_name = argv[argv.index("--config") + 1]
    if "--interval" in argv:
        try:
            debug_interval = int(argv[argv.index("--interval") + 1])
        except Exception:
            debug_interval = 0

    _cfg = cfg = Cfg(cfg_name)
    scr = None
    fast_reload = False
    signal.signal(signal.SIGTERM, _grace_exit)
    signal.signal(signal.SIGINT, _grace_exit)
    while True:
        scr = _try_open(cfg)
        if scr is None:
            fast_reload = False
        boot = None
        if scr is not None:
            if fast_reload:
                # 配置热重启：跳过开机动画，直接回数据页
                boot = {"start": time.monotonic(), "done": True,
                        "waited": True, "jumped": True}
                try:
                    scr.jump(cfg.getint("page_data", 2))
                    log("config hot reload -> data page")
                except Exception as e:
                    log("hot reload jump err: %s" % e)
                fast_reload = False
            else:
                boot = {"start": time.monotonic(), "done": False,
                        "waited": False, "jumped": False}
        last_open_try = time.monotonic()

        sc = SysCollector(cfg)
        pc = ProxyCollector(cfg)
        pc.refresh_net()
        pc.refresh_sub()
        grace_end = time.monotonic() + cfg.getint("boot_grace_sec", 180)
        # 热重启后立即发布一帧（boot.done=True 时为快速路径）
        last_pub = -10.0 if (boot and boot.get("done")) else 0.0
        last_key = 0.0
        last_cfg = 0.0
        bl_now = None
        qr_last = None
        sysd = {}
        px = {}
        start = time.monotonic()
        once_done = False
        log("service started (%s)" % cfg_name)

        while True:
            now = time.monotonic()
            # 屏幕未就绪时每 10 秒尝试重连，不影响采集
            if scr is None and now - last_open_try >= 10:
                last_open_try = now
                scr = _try_open(cfg)
                if scr is not None:
                    boot = {"start": now, "done": False,
                            "waited": False, "jumped": False}
            sc.tick(now)
            pc.tick(now)
            if now - last_cfg >= 2:
                last_cfg = now
                if cfg.reload_if_changed():
                    log("config changed -> hot restart: %s" % cfg_name)
                    fast_reload = True
                    try:
                        if scr is not None:
                            scr.close()
                    except Exception:
                        pass
                    scr = None
                    _scr = None
                    break
            if now - last_key >= cfg.getint("node_check_sec", 5):
                last_key = now
                pc.check_change(now)

            do_pub = False
            if once and not once_done and now - start > 6:
                do_pub = True
            elif debug_interval > 0:
                if now - last_pub >= debug_interval:
                    do_pub = True
            elif last_pub == 0 and now - start > 6:
                do_pub = True
            elif now - last_pub >= cfg.getint("refresh_sec", 10):
                do_pub = True

            # 节点切换：出口刷新成功前暂停发布，保证节点名与出口同帧
            if do_pub:
                px = pc.frame()
                if px.get("net_hold") and not px.get("net_synced"):
                    do_pub = False

            # 开机 logo 页进度
            if boot is not None and not boot["done"]:
                period = max(2.0, float(cfg.getint("boot_prog_sec", 30)))
                pv = int((now % period) * 100.0 / period)
                try:
                    if scr is not None:
                        scr.cmd("SET_PROG(%d,%d)"
                                % (cfg.getint("id_prog_logo", 0),
                                   max(0, min(100, pv))), read_timeout=1.0)
                except Exception:
                    pass

            if do_pub and boot is not None and not boot["done"]:
                ready = (sc.temp_now is not None and sc.mem_now is not None
                         and sc.gw_ok is True
                         and _net_counters(sc._iface) is not None)
                elapsed = now - boot["start"]
                boot_min = cfg.getint("boot_logo_sec", 8)
                boot_max = cfg.getint("boot_logo_timeout", 180)
                if (elapsed < boot_min) or (not ready and elapsed < boot_max):
                    do_pub = False
                    if not boot["waited"]:
                        log("logo progress: waiting...")
                        boot["waited"] = True
                elif not boot["jumped"]:
                    try:
                        if scr is not None:
                            scr.jump(cfg.getint("page_data", 2))
                    except Exception as e:
                        log("jump data page err: %s" % e)
                    boot["jumped"] = boot["done"] = True
                    log("logo -> data page")

            if do_pub:
                last_pub = now
                sysd = sc.frame(now)
                px = pc.frame()
                in_grace = time.monotonic() < grace_end
                ap_pending = in_grace and sysd.get("ap_ok") is not True and \
                    bool(cfg.get("ap_ip", ""))
                text, level, code = render.status_text(
                    cfg, sysd, px, in_grace, ap_pending)
                kind = 0 if level == "OK" else 1
                if scr is not None:
                    qr_now = render.qr_content(cfg)
                    qr_changed = qr_now != qr_last
                    # Some HF028 firmware keeps the last QR bitmap when an
                    # empty QBAR payload is received.  Reload the data page
                    # once on a transition to disabled so the control is
                    # restored from the sGUI project's empty default state.
                    if qr_changed and not qr_now:
                        try:
                            scr.jump(cfg.getint("page_data", 2))
                            log("qr disabled: data page reset")
                        except Exception as e:
                            log("qr page reset err: %s" % e)
                    cmds = render.build_cmds(cfg, sysd, px, text,
                                             qr=qr_now,
                                             qr_update=qr_changed)
                    try:
                        if getattr(sc, "_last_kind", None) != kind:
                            cmds.insert(0, "SET_FCOLOR(%d,%d)"
                                        % (cfg.getint("id_status", 1),
                                           1 if kind else cfg.getint(
                                               "color_normal", 19)))
                            sc._last_kind = kind
                        # 分批发送，避免单帧超长
                        cur, size = [], 0
                        for c in cmds:
                            cur.append(c)
                            size += len(c.encode("gb2312")) + 1
                            if size > 900:
                                scr.cmd(*cur, read_timeout=10.0)
                                cur, size = [], 0
                        if cur:
                            scr.cmd(*cur, read_timeout=10.0)
                        if qr_changed:
                            qr_last = qr_now
                            qr_mode = ("custom" if cfg.getbool("qr_enable", False)
                                        and bool(cfg.get("qr_ssid", ""))
                                        else "default")
                            log("qr updated: %s (%d bytes)" %
                                (qr_mode,
                                 len(qr_now.encode("ascii", "backslashreplace"))))
                        new_bl, pct, day = _brightness(cfg, bl_now)
                        if new_bl != bl_now:
                            scr.cmd("BL(%d)" % new_bl, read_timeout=5.0)
                            bl_now = new_bl
                            log("backlight %d%% -> BL(%d) %s"
                                % (pct, bl_now, "day" if day else "night"))
                        log("publish OK status=%s node=%s exit=%s temp=%s"
                            % (text, px.get("node_label") or "-",
                               px.get("exit_ip") or "-", sysd.get("temp")))
                    except Exception as e:
                        log("publish error: %s" % e)
                        try:
                            scr.close()
                        except Exception:
                            pass
                        scr = None
                        _scr = None
                else:
                    log("state ready (no screen): status=%s node=%s "
                        "exit=%s temp=%s"
                        % (text, px.get("node_label") or "-",
                           px.get("exit_ip") or "-", sysd.get("temp")))
                if once:
                    once_done = True
                    try:
                        if scr is not None:
                            scr.close()
                    except Exception:
                        pass
                    return 0
            time.sleep(0.35)

        try:
            if scr is not None:
                scr.close()
        except Exception:
            pass
        scr = None
        _scr = None
        if not fast_reload:
            time.sleep(10)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("stopped")
