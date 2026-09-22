import datetime
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

sys.path.insert(0, str(Path(__file__).resolve().parent / "service/usr/lib"))
from displaydash.cfg import Cfg
from displaydash import proxyinfo, render

class Regressions(unittest.TestCase):
    def test_month_boundaries(self):
        cases = [(datetime.date(2026,9,8), "2026-12-31", "09-30", 22),
                 (datetime.date(2026,2,1), "2026-12-31", "02-28", 27),
                 (datetime.date(2028,2,1), "2028-12-31", "02-29", 28),
                 (datetime.date(2026,12,20), "2027-06-15", "01-15", 26)]
        for now, expiry, reset_date, days in cases:
            with self.subTest(now=now):
                self.assertEqual(render._exp_line(None, expiry, None, now, "expire_day"),
                                 "重置:%s 剩余%d天" % (reset_date, days))
        self.assertEqual(render._exp_line(None, "2026-09-30", None,
                         datetime.date(2026,9,8), "expire_day"), "重置:09-30 剩余22天")

        self.assertEqual(render._exp_line(None, "2026-09-30", None,
                         datetime.date(2026,9,8), "month_start"),
                         "重置:09-30 剩余22天")
        self.assertEqual(render._exp_line(None, "2026-12-31", None,
                         datetime.date(2026,9,8), "month_start"),
                         "重置:10-01 剩余23天")

    def test_uci_quoted_values(self):
        sample = "config main 'main'\n option qr_password 'abc#123' # comment\n option qr_ssid \"Cafe # 1\"\nconfig sub 'one'\n option url_match 'https://example.test/sub#First'\n"
        with patch("builtins.open", mock_open(read_data=sample)), patch("os.path.getmtime", return_value=1):
            cfg = Cfg()
        self.assertEqual(cfg.get("qr_password"), "abc#123")
        self.assertEqual(cfg.get("qr_ssid"), "Cafe # 1")
        self.assertEqual(cfg.sub_for("https://example.test/sub#First")["url_match"],
                         "https://example.test/sub#First")
        self.assertEqual(cfg.sub_for("https://example.test/sub#Second"), {})

    def test_screen_profile_overrides_mapping(self):
        files = {
            "/etc/config/displaydash":
                "config main 'main'\n"
                " option screen_profile '28TN-320240H-overlay2'\n"
                " option brightness_day '33'\n"
                " option id_clock '99'\n",
            "/etc/config/displaydash-screen":
                "config screen 'overlay2'\n"
                " option profile_name '28TN-320240H-overlay2'\n"
                " option id_clock '17'\n"
                " option page_data '3'\n",
        }
        def fake_open(path, *args, **kwargs):
            return io.StringIO(files[path])
        with patch("builtins.open", side_effect=fake_open), \
                patch("os.path.getmtime", return_value=1):
            cfg = Cfg()
        self.assertEqual(cfg.get("screen_profile"), "28TN-320240H-overlay2")
        self.assertEqual(cfg.getint("id_clock"), 17)
        self.assertEqual(cfg.getint("page_data"), 3)

        with patch("builtins.open", side_effect=fake_open), \
                patch("os.path.getmtime", return_value=1):
            cfg = Cfg()
        self.assertEqual(cfg.getint("brightness_day"), 33)

    def test_qr_disabled_uses_management_url(self):
        cfg = Cfg.__new__(Cfg)
        cfg.vals = {"qr_enable": "0"}
        cfg.screen = {"id_qr": "4"}
        cmds = render.build_cmds(cfg, {}, {}, "系统正常")
        self.assertIn("QBAR(4,http://192.168.22.1)", cmds)

    def test_qr_payload_escapes_wifi_delimiters(self):
        cfg = Cfg.__new__(Cfg)
        cfg.vals = {"qr_enable": "1", "qr_ssid": "A;B:C,D",
                    "qr_password": r"p;:,\\"}
        cfg.screen = {}
        self.assertEqual(render.qr_content(cfg),
                         r"WIFI:T:WPA;S:A\;B\:C\,D;P:p\;\:\,\\\\;;")
        self.assertEqual([x for x in render.build_cmds(
            cfg, {}, {}, "系统正常", qr=render.qr_content(cfg),
            qr_update=False) if x.startswith("QBAR")], [])

    def test_periodic_subscription_refresh(self):
        cfg = Cfg.__new__(Cfg)
        cfg.vals = {"sub_refresh_sec": "3600"}
        cfg.subs = [{"url_match": "https://example.test/sub",
                     "sub_refresh_sec": "60"}]
        pc = proxyinfo.ProxyCollector(cfg)
        cur = {"hash": "hash1", "url": "https://example.test/sub"}
        with patch.object(proxyinfo, "uci_get", return_value="node1"), patch.object(proxyinfo, "_current_sub", return_value=cur), patch.object(proxyinfo, "_hp_urls", return_value=[cur["url"]]), patch.object(pc, "refresh_sub", return_value=True) as refresh, patch.object(pc, "refresh_net") as net:
            pc.check_change(100)
            pc.last_sub = 100
            refresh.reset_mock()
            pc.check_change(159)
            refresh.assert_not_called()
            pc.check_change(160)
            refresh.assert_called_once()
            net.assert_not_called()
            refresh.reset_mock()
            pc.sub_running = True
            pc.check_change(300)
            refresh.assert_not_called()

if __name__ == "__main__":
    unittest.main()
