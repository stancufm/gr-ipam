#!/usr/bin/env python3
import importlib.machinery
import contextlib
import io
import json
import os
import tempfile
import unittest

GR = importlib.machinery.SourceFileLoader("gr_collect_test_module", "bin/gr").load_module()
COLLECTOR = importlib.machinery.SourceFileLoader(
    "gr_collect_helper_test_module", "libexec/collect-version").load_module()


class CollectVersionCliTests(unittest.TestCase):
    def test_host_key_status_is_classified(self):
        self.assertEqual(COLLECTOR.host_key_status(
            "Warning: Permanently added '192.0.2.1'"), "added")
        self.assertEqual(COLLECTOR.host_key_status(
            "REMOTE HOST IDENTIFICATION HAS CHANGED!"), "changed")
        self.assertEqual(COLLECTOR.host_key_status(""), "verified")
    def test_collector_redacts_vault_password(self):
        self.assertEqual(COLLECTOR.redact_secret(
            b"User Name: cisco\r\nPassword: super-secret\r\nsw36#", "super-secret"),
            b"User Name: cisco\r\nPassword: [REDACTED]\r\nsw36#")

    def test_cleanup_disconnect_does_not_invalidate_completed_collection(self):
        data_commands = [b"show version\n", b"show system\n"]
        cleanup_commands = [b"exit\n", b"exit\n"]
        command, complete = COLLECTOR.next_prompt_command(data_commands, cleanup_commands)
        self.assertEqual(command, b"show version\n")
        self.assertFalse(complete)
        command, complete = COLLECTOR.next_prompt_command(data_commands, cleanup_commands)
        self.assertEqual(command, b"show system\n")
        self.assertFalse(complete)
        command, complete = COLLECTOR.next_prompt_command(data_commands, cleanup_commands)
        self.assertEqual(command, b"exit\n")
        self.assertTrue(complete)
        self.assertEqual(cleanup_commands, [b"exit\n"])

    def test_small_business_show_system_fields_are_parsed(self):
        parsed = COLLECTOR.parse_version(
            "Active-image: flash://image.bin\n  Version: 2.4.0.94\n"
            "\rSystem Description: SG350-28 28-Port Gigabit Managed Switch\n"
            "\rSystem Up Time (days,hour:min:sec): 51,12:05:36\n"
            "System Serial Number: DNI12345678\n")
        self.assertEqual(parsed["firmware"], "2.4.0.94")
        self.assertEqual(parsed["model"], "SG350-28")
        self.assertEqual(parsed["uptime"], "51,12:05:36")
        self.assertEqual(parsed["serial"], "DNI12345678")

    def test_sx220_show_version_fields_are_parsed(self):
        parsed = COLLECTOR.parse_version(
            "Cisco Sx220 Series Switch Software, Version 1.1.3.1, RELEASE SOFTWARE\n"
            "Sw-17 uptime is 0 days, 0 hours, 2 mins, 40 secs\n"
            "Model Number     : SF220-24P\n"
            "Serial Number    : DNI00000000\n"
            "PID              : SF220-24P-K9\n")
        self.assertEqual(parsed["firmware"], "1.1.3.1")
        self.assertEqual(parsed["model"], "SF220-24P")
        self.assertEqual(parsed["serial"], "DNI00000000")
        self.assertEqual(parsed["os_family"], "cisco-small-business")

    def test_dell_os10_show_version_fields_are_parsed(self):
        parsed = COLLECTOR.parse_version(
            "Dell SmartFabric OS10 Enterprise\n"
            "OS Version: 10.5.5.6\n"
            "Build Version: 10.5.5.6.226\n"
            "System Type: S5224F-ON\n"
            "Architecture: x86_64\n")
        self.assertEqual(parsed["firmware"], "10.5.5.6")
        self.assertEqual(parsed["model"], "S5224F-ON")
        self.assertEqual(parsed["os_family"], "dell-os10")

    def test_hpe_arubaos_switch_banner_and_version_are_parsed(self):
        parsed = COLLECTOR.parse_version(
            "HP J9726A 2920-24G Switch\n"
            "Software revision WB.16.10.0025\n")
        self.assertEqual(parsed["firmware"], "WB.16.10.0025")
        self.assertEqual(parsed["model"], "J9726A 2920-24G")
        self.assertEqual(parsed["os_family"], "hpe-arubaos-switch")

    def test_hpe_login_passes_continue_banner_and_detects_prompts(self):
        driver = GR.HpeArubaOsSwitchLogin("manager", "unused")
        self.assertEqual(driver.feed(b"Press any key to continue\x1b[13;1H\x1b[?25h"),
                         [("credential", b" ")])
        self.assertEqual(driver.feed(b"\r\nSw-11# \x1b[24;8H"), [("ready", b"")])
        self.assertEqual(driver.feed(b"output\r\nSw-11# \x1b[?25h"), [("prompt", b"")])
        self.assertEqual(driver.feed(b"Do you want to log out (y/n)? \x1b[24;31H"),
                         [("credential", b"y\n")])
        self.assertEqual(driver.feed(b"Do you want to log out [y/n]? \x1b[24;31H"),
                         [("credential", b"y\n")])

    def test_all_uses_documented_defaults(self):
        args = GR.build_parser().parse_args(["collect", "version", "--all"])
        self.assertTrue(args.all)
        self.assertEqual(args.vendor, "cisco")
        self.assertEqual(args.workers, 4)

    def test_ip_is_repeatable_and_accepts_overrides(self):
        args = GR.build_parser().parse_args([
            "collect", "version", "--ip", "192.0.2.10", "--ip", "192.0.2.11",
            "--vendor", "cisco", "--workers", "8",
        ])
        self.assertEqual(args.ips, ["192.0.2.10", "192.0.2.11"])
        self.assertEqual(args.vendor, "cisco")
        self.assertEqual(args.workers, 8)

    def test_report_browser_lists_and_displays_complete_run(self):
        with tempfile.TemporaryDirectory() as root:
            report_id = "20260810T100000Z"
            directory = os.path.join(root, report_id)
            os.makedirs(directory)
            data = {
                "generated_utc": report_id,
                "command": "show version",
                "results": [
                    {"hostname": "sw1", "ip": "192.0.2.1", "result": "success",
                     "model": "C1000", "uptime": "3 weeks",
                     "system_image": "flash:image.bin", "rom": "ROM1"},
                    {"hostname": "sw2", "ip": "192.0.2.2", "result": "failed",
                     "stderr": "denied", "raw_report": "/private/report.txt"},
                ],
            }
            raw_content = json.dumps(data, ensure_ascii=False, indent=2)
            with open(os.path.join(directory, "cisco-show-version-report.json"),
                      "w", encoding="utf-8") as handle:
                handle.write(raw_content)
            cfg = {"device_version_dir": root}

            listing = io.StringIO()
            with contextlib.redirect_stdout(listing):
                GR.command_collect_reports(cfg)
            self.assertIn(report_id, listing.getvalue())
            self.assertRegex(listing.getvalue(), r"2\s+1\s+1\s+0")

            shown = io.StringIO()
            with contextlib.redirect_stdout(shown):
                GR.command_collect_reports(cfg, "latest", use_pager=False)
            self.assertIn("HOSTNAME", shown.getvalue())
            self.assertIn("sw1", shown.getvalue())
            self.assertIn("C1000", shown.getvalue())
            self.assertNotIn("STDERR", shown.getvalue())
            self.assertNotIn("denied", shown.getvalue())
            self.assertNotIn("RAW_REPORT", shown.getvalue())
            self.assertNotIn("SYSTEM_IMAGE", shown.getvalue())
            self.assertNotIn("ROM1", shown.getvalue())
            self.assertNotIn("UPTIME", shown.getvalue())
            self.assertNotIn("3 weeks", shown.getvalue())

            raw = io.StringIO()
            with contextlib.redirect_stdout(raw):
                GR.command_collect_reports(cfg, report_id, use_pager=False, raw=True)
            self.assertEqual(raw.getvalue(), raw_content)
            self.assertIn('"stderr": "denied"', raw.getvalue())
            self.assertIn('"uptime": "3 weeks"', raw.getvalue())

            completed = io.StringIO()
            with contextlib.redirect_stdout(completed):
                GR.command_completion(cfg, "collect-reports")
            self.assertEqual(completed.getvalue().splitlines(), ["latest", report_id])

    def test_reports_parser_accepts_selector_and_no_more(self):
        args = GR.build_parser().parse_args([
            "collect", "reports", "20260810T100000Z", "--raw", "--no-more",
        ])
        self.assertEqual(args.report, "20260810T100000Z")
        self.assertTrue(args.raw)
        self.assertTrue(args.no_more)


if __name__ == "__main__":
    unittest.main()
