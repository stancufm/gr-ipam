#!/usr/bin/env python3
import contextlib
import io
import ipaddress
import json
import os
import tempfile
import unittest
from unittest import mock

from support import load_source


GR = load_source("gr_config_test_module", "bin/gr")


class ConfigShowTests(unittest.TestCase):
    def test_snmp_and_monitoring_profiles_merge_per_profile(self):
        merged = GR.merge_config(
            {"snmp_profiles": {"old": {"username": "old"}},
             "monitoring_profiles": {"one": {"type": "librenms"}}},
            {"snmp_profiles": {"new": {"username": "new"}},
             "monitoring_profiles": {"two": {"type": "librenms"}}})
        self.assertEqual(sorted(merged["snmp_profiles"]), ["new", "old"])
        self.assertEqual(sorted(merged["monitoring_profiles"]), ["one", "two"])

    def test_configuration_collection_objects_merge_and_parse_as_json(self):
        merged = GR.merge_config(
            {"config_collection": {"pools": {"one": {}}, "scheduler_enabled": False}},
            {"config_collection": {"scheduler_enabled": True}})
        self.assertEqual(merged["config_collection"]["pools"], {"one": {}})
        self.assertTrue(merged["config_collection"]["scheduler_enabled"])
        parsed = GR.parse_config_setting(
            "config_collection", '{"scheduler_enabled": false, "pools": {}}')
        self.assertEqual(parsed, {"scheduler_enabled": False, "pools": {}})

    def test_snmp_profile_sources_are_validated_as_ip_list(self):
        value = GR.parse_config_setting("snmp_profiles.monitor.sources",
                                        '["192.0.2.20", "2001:db8::20"]')
        self.assertEqual(value, ["192.0.2.20", "2001:db8::20"])
        with self.assertRaises(GR.GrError):
            GR.parse_config_setting("snmp_profiles.monitor.sources", '["not-an-ip"]')

    def test_snmp_profile_source_address_is_validated(self):
        self.assertEqual(
            GR.parse_config_setting("snmp_profiles.monitor.source_address", "192.0.2.20"),
            "192.0.2.20")
        with self.assertRaises(GR.GrError):
            GR.parse_config_setting("snmp_profiles.monitor.source_address", "not-an-ip")

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
        self.assertIs(GR.device_login_driver("dell-os10"), GR.CiscoIosLogin)

    def test_sudo_secret_defaults_to_ssh_secret_and_can_be_separate(self):
        cfg = {"ssh_profiles": {
            "same": {"password_secret": "gr/same"},
            "separate": {"password_secret": "gr/ssh", "sudo_password_secret": "gr/sudo"},
        }}
        self.assertEqual(GR.sudo_vault_secret_name(cfg, "same"), "gr/same")
        self.assertEqual(GR.sudo_vault_secret_name(cfg, "separate"), "gr/sudo")

    def test_exec_parser_requires_explicit_remote_command(self):
        parser = GR.build_parser()
        args = parser.parse_args(["exec", "server.example", "--sudo"])
        self.assertTrue(args.sudo)
        with self.assertRaises(GR.GrError):
            GR.main(["exec", "server.example", "--sudo"])

    def test_device_probe_accepts_only_safe_command_language(self):
        self.assertEqual(
            GR.normalize_device_probe_commands([
                "terminal datadump", "show logging", "configure terminal",
                "logging ?", "end",
            ]),
            ["terminal datadump", "show logging", "configure terminal",
             "logging ?\x03", "end"])
        for unsafe in ("logging host 192.0.2.1", "write", "copy running startup",
                       "show logging\nwrite", "show logging; write",
                       "show logging | include host", "show logging\x1awrite"):
            with self.assertRaises(GR.GrError):
                GR.normalize_device_probe_commands([unsafe])

    def test_device_probe_parser_and_dispatch(self):
        args = GR.build_parser().parse_args([
            "device", "probe", "legacy-switch", "--command", "show logging",
            "--command", "logging ?", "--command-timeout", "90",
        ])
        self.assertEqual(args.device_action, "probe")
        self.assertEqual(args.commands, ["show logging", "logging ?"])
        self.assertEqual(args.command_timeout, 90)
        with mock.patch.object(GR, "load_config", return_value={}), \
                mock.patch.object(GR, "command_device_probe", return_value=0) as probe:
            self.assertEqual(GR.main([
                "device", "probe", "legacy-switch", "--command", "show logging"]), 0)
        probe.assert_called_once()

    def test_snmp_help_is_forwarded_to_the_real_helper(self):
        with mock.patch.object(GR, "load_config", side_effect=AssertionError("help loaded config")), \
                mock.patch.object(GR, "command_helper", return_value=0) as helper:
            self.assertEqual(GR.main(["snmp", "--help"]), 0)
        helper.assert_called_once_with(GR.SNMP_MANAGER, ["--help"])
        with mock.patch.object(GR, "load_config", side_effect=AssertionError("help loaded config")), \
                mock.patch.object(GR, "command_helper", return_value=0) as helper:
            self.assertEqual(GR.main(["snmp"]), 0)
        helper.assert_called_once_with(GR.SNMP_MANAGER, ["--help"])

    def test_documentation_topics_resolve_installed_language_files(self):
        with tempfile.TemporaryDirectory() as root:
            old_root = GR.DEFAULT_DOCUMENTATION_ROOT
            try:
                GR.DEFAULT_DOCUMENTATION_ROOT = root
                for filename in ("CLI.md", "CLI.ro.md"):
                    with open(os.path.join(root, filename), "w", encoding="utf-8") as handle:
                        handle.write(filename)
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(GR.command_docs_topic("cli", "ro"), 0)
                self.assertEqual(output.getvalue(), "CLI.ro.md")
            finally:
                GR.DEFAULT_DOCUMENTATION_ROOT = old_root

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
        fortigate = GR.device_driver_spec("fortigate-fortios")
        self.assertFalse(ios["interactive_cli"])
        self.assertTrue(ios["config_interactive_cli"])
        self.assertEqual(ios["version_commands"], ("show version",))
        self.assertEqual(ios["config_commands"],
                         ("enable", "terminal length 0", "show running-config"))
        self.assertIs(GR.device_login_driver("cisco-ios"), GR.CiscoIosLogin)
        self.assertTrue(smb["interactive_cli"])
        self.assertIn("show system", smb["version_commands"])
        smb_login = GR.CiscoSmallBusinessLogin("cisco", "secret")
        smb_login.state = "ready"
        self.assertEqual(smb_login.feed(b"--More--"), [("credential", b" ")])
        smb_login.state = "prompt"
        self.assertEqual(
            smb_login.feed(
                b"Do you want to change the password now (Y/N)[N] \x1b[30;120R?"),
            [("credential", b"n\n")])
        self.assertEqual(smb_login.state, "prompt")
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
        self.assertTrue(fortigate["interactive_cli"])
        self.assertEqual(fortigate["version_commands"], ("get system status",))
        self.assertEqual(fortigate["config_commands"], ("show full-configuration",))
        self.assertIs(GR.device_login_driver("fortigate-fortios"),
                      GR.FortiGateFortiOsLogin)

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
        self.assertEqual(GR.detect_device_driver(
            {"custom_device_vendor": "fortinet"}, {})[0], "fortigate-fortios")

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

    def test_config_set_and_unset_manage_user_json(self):
        with tempfile.TemporaryDirectory() as root:
            old_user = GR.USER_CONFIG
            try:
                GR.USER_CONFIG = os.path.join(root, "config.json")
                GR.command_config_change("set", "ssh_audit_enabled", "true", scope="user")
                GR.command_config_change(
                    "set", "ssh_profiles.linux.sudo_password_secret", "gr/linux-sudo", scope="user")
                with open(GR.USER_CONFIG, encoding="utf-8") as handle:
                    saved = json.load(handle)
                self.assertIs(saved["ssh_audit_enabled"], True)
                self.assertEqual(saved["ssh_profiles"]["linux"]["sudo_password_secret"],
                                 "gr/linux-sudo")
                self.assertEqual(os.stat(GR.USER_CONFIG).st_mode & 0o777, 0o600)
                GR.command_config_change(
                    "unset", "ssh_profiles.linux.sudo_password_secret", scope="user")
                with open(GR.USER_CONFIG, encoding="utf-8") as handle:
                    saved = json.load(handle)
                self.assertNotIn("ssh_profiles", saved)
            finally:
                GR.USER_CONFIG = old_user

    def test_config_setting_validation_and_list_parsing(self):
        self.assertEqual(GR.parse_config_setting("include_tags", '[2, 4]'), [2, 4])
        with self.assertRaises(GR.GrError):
            GR.parse_config_setting("ssh_audit_enabled", "perhaps")
        with self.assertRaises(GR.GrError):
            GR.validate_config_setting_name("unknown_setting")


if __name__ == "__main__":
    unittest.main()
