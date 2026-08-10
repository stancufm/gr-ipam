#!/usr/bin/env python3
import contextlib
import importlib.machinery
import io
import ipaddress
import unittest

GR = importlib.machinery.SourceFileLoader("gr_find_test_module", "bin/gr").load_module()


class FindDetailsTests(unittest.TestCase):
    def test_standard_table_places_last_seen_after_status(self):
        row = {
            "_ip": ipaddress.ip_address("192.0.2.10"),
            "_hostname": "core-switch",
            "lastSeen": "2026-08-10 12:00:00",
            "tag": "2",
            "description": "Core device",
            "custom_fields": {},
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GR.print_table([row])
        lines = output.getvalue().splitlines()
        self.assertRegex(lines[0], r"STATUS\s+LASTSEEN\s+SSH")
        self.assertIn("2026-08-10 12:00:00", output.getvalue())

    def test_brief_table_contains_only_requested_columns(self):
        row = {
            "_ip": ipaddress.ip_address("192.0.2.10"),
            "_hostname": "core-switch",
            "lastSeen": "2026-08-10 12:00:00",
            "tag": "2",
            "description": "Core device",
            "custom_fields": {},
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GR.print_table([row], brief=True)
        header = output.getvalue().splitlines()[0]
        self.assertRegex(header, r"^IP\s+HOSTNAME\s+SSH\s+DESCRIPTION$")
        self.assertNotIn("STATUS", header)
        self.assertNotIn("LASTSEEN", header)

    def test_brief_table_allows_wider_ssh_column(self):
        long_profile = "profile-" + ("x" * 35)
        row = {
            "_ip": ipaddress.ip_address("192.0.2.10"),
            "_hostname": "core-switch",
            "description": "Core device",
            "custom_fields": {
                "ssh_enabled": "1",
                "ssh_user": "administrator",
                "ssh_port": "2222",
                "ssh_profile": long_profile,
                "device_driver": "cisco-ios",
            },
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GR.print_table([row], brief=True)
        self.assertIn(long_profile, output.getvalue())
        self.assertNotIn("…", output.getvalue())

    def test_details_prints_all_phpipam_fields_and_hides_internal_keys(self):
        row = {
            "ip": "3221225994",
            "hostname": "core-switch",
            "description": "Core device",
            "empty": "",
            "custom_fields": {"ssh_enabled": "1", "ssh_port": "22"},
            "_ip": ipaddress.ip_address("192.0.2.10"),
            "_hostname": "core-switch",
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GR.print_address_details([row])
        text = output.getvalue()
        self.assertIn("Details 1/1: core-switch (192.0.2.10)", text)
        self.assertRegex(text, r"ip\s+: 192\.0\.2\.10")
        self.assertIn("hostname", text)
        self.assertIn("description", text)
        self.assertIn("custom_fields", text)
        self.assertIn('"ssh_enabled": "1"', text)
        self.assertRegex(text, r"empty\s+: -")
        self.assertNotIn("_hostname", text)

    def test_parser_accepts_details_with_and_without_ssh(self):
        parser = GR.build_parser()
        self.assertTrue(parser.parse_args(["find", "switch", "--details"]).details)
        combined = parser.parse_args(["find", "switch", "--details", "--ssh"])
        self.assertTrue(combined.details)
        self.assertTrue(combined.ssh)

    def test_parser_accepts_brief_and_rejects_details_combination(self):
        parser = GR.build_parser()
        self.assertTrue(parser.parse_args(["find", "switch", "--brief"]).brief)
        with self.assertRaises(SystemExit):
            parser.parse_args(["find", "switch", "--brief", "--details"])

    def test_parser_accepts_independent_profile_and_driver(self):
        args = GR.build_parser().parse_args([
            "find", "switch", "--ssh", "--profile", "shared",
            "--driver", "cisco-small-business",
        ])
        self.assertEqual(args.profile, "shared")
        self.assertEqual(args.driver, "cisco-small-business")

    def test_update_accepts_device_driver(self):
        args = GR.build_parser().parse_args([
            "update", "192.0.2.10", "--device-driver", "cisco-ios",
        ])
        self.assertEqual(args.device_driver, "cisco-ios")

    def test_update_accepts_device_vendor(self):
        args = GR.build_parser().parse_args([
            "update", "192.0.2.10", "--device-vendor", "hpe-comware",
        ])
        self.assertEqual(args.device_vendor, "hpe-comware")


if __name__ == "__main__":
    unittest.main()
