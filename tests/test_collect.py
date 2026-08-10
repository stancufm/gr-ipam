#!/usr/bin/env python3
import importlib.machinery
import contextlib
import io
import json
import os
import tempfile
import unittest

GR = importlib.machinery.SourceFileLoader("gr_collect_test_module", "bin/gr").load_module()


class CollectVersionCliTests(unittest.TestCase):
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
                     "model": "C1000", "system_image": "flash:image.bin", "rom": "ROM1"},
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

            raw = io.StringIO()
            with contextlib.redirect_stdout(raw):
                GR.command_collect_reports(cfg, report_id, use_pager=False, raw=True)
            self.assertEqual(raw.getvalue(), raw_content)
            self.assertIn('"stderr": "denied"', raw.getvalue())

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
