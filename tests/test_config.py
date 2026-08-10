#!/usr/bin/env python3
import contextlib
import importlib.machinery
import io
import json
import os
import tempfile
import unittest

GR = importlib.machinery.SourceFileLoader("gr_config_test_module", "bin/gr").load_module()


class ConfigShowTests(unittest.TestCase):
    def test_device_driver_is_independent_from_credential_profile(self):
        row = {"custom_ssh_profile": "shared-credential",
               "custom_device_driver": "cisco-small-business"}
        self.assertEqual(GR.phpipam_ssh_metadata(row)["profile"], "shared-credential")
        self.assertEqual(GR.resolve_device_driver(row), "cisco-small-business")
        self.assertEqual(GR.resolve_device_driver(row, "generic"), "generic")
        with self.assertRaises(GR.GrError):
            GR.normalize_device_driver("unknown")

    def test_device_driver_fallback_uses_vendor_not_profile(self):
        row = {"custom_ssh_profile": "cisco", "custom_device_vendor": "cisco"}
        self.assertEqual(GR.resolve_device_driver(row), "cisco-ios")
        row["custom_device_vendor"] = "dell"
        self.assertEqual(GR.resolve_device_driver(row), "generic")

    def test_driver_registry_owns_commands_and_cli_behavior(self):
        ios = GR.device_driver_spec("cisco-ios")
        smb = GR.device_driver_spec("cisco-small-business")
        hpe = GR.device_driver_spec("hpe-arubaos-switch")
        comware = GR.device_driver_spec("hpe-comware7")
        self.assertFalse(ios["interactive_cli"])
        self.assertEqual(ios["version_commands"], ("show version",))
        self.assertTrue(smb["interactive_cli"])
        self.assertIn("show system", smb["version_commands"])
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
