#!/usr/bin/env python3
import contextlib
import importlib.machinery
import io
import ipaddress
import json
import os
import tempfile
import unittest

GR = importlib.machinery.SourceFileLoader("gr_config_test_module", "bin/gr").load_module()


class ConfigShowTests(unittest.TestCase):
    def test_required_phpipam_custom_fields_are_validated(self):
        complete = {name: None for name in GR.REQUIRED_ADDRESS_CUSTOM_FIELDS}
        self.assertEqual(GR.missing_address_custom_fields([complete]), [])
        del complete["custom_device_driver"]
        self.assertEqual(GR.missing_address_custom_fields([complete]),
                         ["custom_device_driver"])

    def test_nested_phpipam_custom_fields_are_validated(self):
        nested = {"custom_fields": {
            name[len("custom_"):]: None for name in GR.REQUIRED_ADDRESS_CUSTOM_FIELDS
        }}
        self.assertEqual(GR.missing_address_custom_fields([nested]), [])

    def test_device_driver_is_independent_from_credential_profile(self):
        row = {"custom_ssh_profile": "shared-credential",
               "custom_device_driver": "cisco-small-business"}
        self.assertEqual(GR.phpipam_ssh_metadata(row)["profile"], "shared-credential")
        self.assertEqual(GR.resolve_device_driver(row), "cisco-small-business")
        self.assertEqual(GR.resolve_device_driver(row, "generic"), "generic")
        with self.assertRaises(GR.GrError):
            GR.normalize_device_driver("unknown")

    def test_device_driver_fallback_is_always_generic(self):
        row = {"custom_ssh_profile": "cisco", "custom_device_vendor": "cisco"}
        self.assertEqual(GR.resolve_device_driver(row), "generic")
        row["custom_device_vendor"] = "dell"
        self.assertEqual(GR.resolve_device_driver(row), "generic")

    def test_driver_registry_owns_commands_and_cli_behavior(self):
        ios = GR.device_driver_spec("cisco-ios")
        smb = GR.device_driver_spec("cisco-small-business")
        planet = GR.device_driver_spec("planet-sgs")
        hpe = GR.device_driver_spec("hpe-arubaos-switch")
        comware = GR.device_driver_spec("hpe-comware7")
        self.assertFalse(ios["interactive_cli"])
        self.assertEqual(ios["version_commands"], ("show version",))
        self.assertTrue(smb["interactive_cli"])
        self.assertIn("show system", smb["version_commands"])
        self.assertTrue(planet["interactive_cli"])
        self.assertEqual(planet["version_commands"], ("enable", "show version"))
        self.assertIs(GR.device_login_driver("planet-sgs"), GR.PlanetSgsLogin)
        planet_login = GR.PlanetSgsLogin("admin", "secret")
        planet_login.state = "ready"
        self.assertEqual(planet_login.feed(b"--More--"), [("credential", b" ")])
        self.assertTrue(hpe["interactive_cli"])
        self.assertEqual(hpe["version_commands"],
                         ("no page", "show version", "show system"))
        self.assertIs(GR.device_login_driver("hpe-arubaos-switch"),
                      GR.HpeArubaOsSwitchLogin)
        self.assertEqual(comware["version_commands"],
                         ("screen-length disable", "display version",
                          "display device manuinfo"))
        self.assertIs(GR.device_login_driver("hpe-comware7"), GR.HpeComwareLogin)

    def test_legacy_profile_driver_is_migration_only(self):
        cfg = {"ssh_profiles": {"credential": {
            "password_secret": "gr/credential", "session_driver": "cisco-small-business"}}}
        self.assertEqual(GR.legacy_profile_driver(cfg, "credential"), "cisco-small-business")

    def test_driver_detection_uses_inventory_and_safe_generic_fallback(self):
        cisco = {"custom_device_vendor": "cisco"}
        self.assertEqual(GR.detect_device_driver(
            cisco, {"model": "SG350-28P", "result": "success"})[0],
            "cisco-small-business")
        self.assertEqual(GR.detect_device_driver(
            cisco, {"model": "C9200-24T", "result": "success"})[0],
            "cisco-ios")
        self.assertEqual(GR.detect_device_driver(cisco, {})[0], "generic")
        self.assertEqual(GR.detect_device_driver(
            {"custom_device_vendor": "hpe-comware"}, {})[0], "hpe-comware7")
        self.assertEqual(GR.detect_device_driver(
            {"custom_device_vendor": "planet-technology"}, {})[0], "planet-sgs")
        self.assertEqual(GR.detect_device_driver(
            {}, {"model": "SGS-6310-16S8C4XR", "result": "success"})[0],
            "planet-sgs")

    def test_driver_detection_range_and_parser_selectors(self):
        start, end = GR.driver_detection_range("10.22.10.10-69")
        self.assertEqual(start, ipaddress.ip_address("10.22.10.10"))
        self.assertEqual(end, ipaddress.ip_address("10.22.10.69"))
        parser = GR.build_parser()
        args = parser.parse_args(["driver", "detect", "--range", "10.22.10.10-69"])
        self.assertEqual(args.ip_range, (start, end))
        self.assertEqual(parser.parse_args(
            ["driver", "detect", "--find", "sw", "--apply"]).find, "sw")

    def test_driver_list_is_available_and_describes_commands(self):
        args = GR.build_parser().parse_args(["driver", "list"])
        self.assertEqual(args.driver_action, "list")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GR.command_driver_list()
        self.assertIn("cisco-small-business", output.getvalue())
        self.assertIn("show system", output.getvalue())

    def test_show_compares_default_global_user_and_effective_values(self):
        with tempfile.TemporaryDirectory() as root:
            system_path = os.path.join(root, "system.json")
            user_path = os.path.join(root, "user.json")
            required = {
                "base_url": "https://ipam.example.net",
                "app_id": "gr-app",
                "username": "operator",
                "ca_file": os.path.join(root, "ca.pem"),
                "credential_file": os.path.join(root, "credentials"),
                "ssh_audit_enabled": False,
            }
            with open(system_path, "w", encoding="utf-8") as handle:
                required["ssh_profiles"] = {"global-admin": {"password_secret": "gr/global-admin"}}
                json.dump(required, handle)
            with open(user_path, "w", encoding="utf-8") as handle:
                json.dump({"ssh_audit_enabled": True, "include_tags": [2, 4],
                           "ssh_profiles": {"user-admin": {"identity_file": "~/.ssh/id_user"}}}, handle)

            old_system, old_user = GR.SYSTEM_CONFIG, GR.USER_CONFIG
            try:
                GR.SYSTEM_CONFIG, GR.USER_CONFIG = system_path, user_path
                cfg = GR.load_config()
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    GR.command_config_show(cfg)
            finally:
                GR.SYSTEM_CONFIG, GR.USER_CONFIG = old_system, old_user

            text = output.getvalue()
            self.assertIn("OPTION", text)
            self.assertIn("DEFAULT", text)
            self.assertIn("GLOBAL", text)
            self.assertIn("USER", text)
            self.assertIn("EFFECTIVE", text)
            self.assertIn("SOURCE", text)
            self.assertRegex(text, r"ssh_audit_enabled\s+false\s+false\s+true\s+true\s+user")
            self.assertRegex(text, r"ssh_legacy_fallback\s+true\s+-\s+-\s+true\s+default")
            self.assertIn("ssh_profiles.global-admin.password_secret", text)
            self.assertIn("ssh_profiles.user-admin.identity_file", text)
            self.assertNotIn('{"global-admin"', text)
            self.assertIn("<required>", text)

    def test_parser_defaults_to_config_show(self):
        parser = GR.build_parser()
        implicit = parser.parse_args(["config"])
        explicit = parser.parse_args(["config", "show"])
        self.assertEqual(implicit.config_action, "show")
        self.assertEqual(explicit.config_action, "show")


if __name__ == "__main__":
    unittest.main()
