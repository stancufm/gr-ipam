#!/usr/bin/env python3
import importlib.machinery
import importlib.util
import json
import os
import types
import unittest
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["GR_PATH"] = os.path.join(ROOT, "bin", "gr")
os.environ["GR_SNMP_TEMPLATES"] = os.path.join(ROOT, "snmp", "templates.json")
loader = importlib.machinery.SourceFileLoader("snmp_manager_test", os.path.join(ROOT, "libexec", "snmp-manager"))
spec = importlib.util.spec_from_loader(loader.name, loader)
SNMP = importlib.util.module_from_spec(spec)
loader.exec_module(SNMP)


def row(driver="cisco-ios", model="C9200-24T", explicit=None):
    value = {"ip": "192.0.2.10", "hostname": "example-switch",
             "custom_device_driver": driver, "custom_device_model": model,
             "custom_device_vendor": "Example", "custom_os_version": "17.9"}
    if explicit:
        value["custom_snmp_template"] = explicit
    return value


class SnmpManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.environ["GR_SNMP_TEMPLATES"], encoding="utf-8") as handle:
            cls.templates = json.load(handle)["templates"]

    def test_template_resolution_prefers_explicit_ip_assignment(self):
        template, source = SNMP.resolve_template(self.templates, row(explicit="cisco-ios-v3"))
        self.assertEqual(template["id"], "cisco-ios-v3")
        self.assertEqual(source, "ip-override")

    def test_template_resolution_uses_driver_and_model(self):
        template, source = SNMP.resolve_template(self.templates, row())
        self.assertEqual(template["id"], "cisco-ios-v3")
        self.assertEqual(source, "selector")

    def test_rendered_plan_redacts_both_passphrases(self):
        template = next(item for item in self.templates if item["id"] == "cisco-ios-v3")
        values = {"view": "VIEW", "acl": "ACL", "source_1": "192.0.2.1",
                  "source_2": "192.0.2.2", "source_3": "192.0.2.3", "group": "GROUP",
                  "username": "snmp-user", "auth_protocol": "SHA", "auth_password": "auth-secret",
                  "privacy_password": "priv-secret", "privacy_protocol": "AES"}
        output = "\n".join(SNMP.render_commands(template, "configure", values))
        self.assertNotIn("auth-secret", output)
        self.assertNotIn("priv-secret", output)
        self.assertIn("[REDACTED]", output)

    def test_snmpget_does_not_put_secrets_in_process_argv(self):
        credentials = {"username": "snmp-user", "auth_protocol": "SHA",
                       "privacy_protocol": "AES", "auth_password": "auth-secret",
                       "privacy_password": "priv-secret"}

        def run(command, **kwargs):
            joined = " ".join(command)
            self.assertNotIn("auth-secret", joined)
            self.assertNotIn("priv-secret", joined)
            config = os.path.join(kwargs["env"]["SNMPCONFPATH"], "snmp.conf")
            self.assertEqual(os.stat(config).st_mode & 0o777, 0o600)
            return types.SimpleNamespace(returncode=0, stderr="")

        with mock.patch.object(SNMP.subprocess, "run", side_effect=run):
            self.assertEqual(SNMP.snmpget("192.0.2.10", credentials), (0, ""))

    def test_parser_supports_all_report_modes(self):
        for mode in ("inventory", "live", "offline", "ports"):
            args = SNMP.build_parser().parse_args(["report", "--ip", "192.0.2.10", "--mode", mode])
            self.assertEqual(args.mode, mode)

    def test_applied_change_requires_successful_configuration_backup(self):
        completed = types.SimpleNamespace(returncode=2, stdout="", stderr="collector failed")
        with mock.patch.object(SNMP.os.path, "isfile", return_value=True), \
                mock.patch.object(SNMP.subprocess, "run", return_value=completed):
            with self.assertRaises(SNMP.gr.GrError):
                SNMP.backup_configuration("192.0.2.10")

    def test_monitor_poll_is_explicit_and_applied(self):
        args = SNMP.build_parser().parse_args([
            "monitor", "--ip", "192.0.2.10", "--monitoring-profile", "librenms",
            "--poll", "--apply"])
        self.assertTrue(args.poll)
        self.assertTrue(args.apply)

    def test_unauthenticated_unknown_user_proves_agent_response(self):
        completed = types.SimpleNamespace(returncode=1, stdout="",
                                          stderr="Unknown user name")
        with mock.patch.object(SNMP.subprocess, "run", return_value=completed):
            status, _detail = SNMP.unauthenticated_probe("192.0.2.10")
        self.assertEqual(status, "responsive")


if __name__ == "__main__":
    unittest.main()
