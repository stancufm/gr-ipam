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
os.environ["GR_SNMP_HANDLERS"] = os.path.join(ROOT, "libexec", "snmp-handlers")
loader = importlib.machinery.SourceFileLoader("snmp_manager_test", os.path.join(ROOT, "libexec", "snmp-manager"))
spec = importlib.util.spec_from_loader(loader.name, loader)
SNMP = importlib.util.module_from_spec(spec)
loader.exec_module(SNMP)


def row(driver="cisco-ios", model="C9200-24T", explicit=None, version="17.9", mac="02:00:00:00:00:10"):
    value = {"ip": "192.0.2.10", "hostname": "example-switch",
             "custom_device_driver": driver, "custom_device_model": model,
             "custom_device_vendor": "Example", "custom_os_version": version, "mac": mac}
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

    def test_reviewed_cbs_model_and_firmware_select_apply_handler(self):
        template, _source = SNMP.resolve_template(
            self.templates, row("cisco-small-business", "CBS250-8T-D", version="3.1.1.7"))
        self.assertEqual(template["id"], "cisco-business-cbs250-8td-3.1-v3")
        self.assertEqual(template["handler"], "cisco-business-3x")
        self.assertTrue(template["apply_supported"])

    def test_unreviewed_cbs_firmware_remains_report_only(self):
        template, _source = SNMP.resolve_template(
            self.templates, row("cisco-small-business", "SG350X-48MP", version="2.5.0.83"))
        self.assertEqual(template["id"], "cisco-business-report-only")
        self.assertFalse(template["apply_supported"])

    def test_rendered_plan_redacts_both_passphrases(self):
        template = next(item for item in self.templates if item["id"] == "cisco-ios-v3")
        values = {"view": "VIEW", "acl": "ACL", "source_1": "192.0.2.1",
                  "source_2": "192.0.2.2", "source_3": "192.0.2.3", "group": "GROUP",
                  "username": "snmp-user", "auth_protocol": "SHA", "auth_password": "auth-secret",
                  "privacy_password": "priv-secret", "privacy_protocol": "AES",
                  "auth_cli": "auth-secret", "privacy_cli": "priv-secret"}
        output = "\n".join(SNMP.render_commands(template, "configure", values))
        self.assertNotIn("auth-secret", output)
        self.assertNotIn("priv-secret", output)
        self.assertIn("[REDACTED]", output)

    def test_plan_without_credentials_uses_secret_placeholders(self):
        template = next(item for item in self.templates if item["id"] == "cisco-ios-v3")
        values = {"auth_password": "", "privacy_password": ""}
        prepared = SNMP.snmp_handlers.prepare(template, row(), values, applying=False)
        self.assertEqual(prepared["auth_cli"], "[AUTH_SECRET]")
        self.assertEqual(prepared["privacy_cli"], "[PRIV_SECRET]")

    def test_planet_engine_id_is_derived_from_inventory_mac(self):
        template = next(item for item in self.templates
                        if item["id"] == "planet-sgs-6310-2.2-v3")
        prepared = SNMP.snmp_handlers.prepare(
            template, row("planet-sgs", "SGS-6310", mac="02:11:22:33:44:55"),
            {"auth_password": "", "privacy_password": ""}, applying=False)
        self.assertEqual(prepared["engine_id"], "800028D803021122334455")

    def test_aruba_normalizer_requires_v3_only_and_no_initial_user(self):
        template = next(item for item in self.templates if item["id"] == "hpe-aruba-2920-wb16-v3")
        output = """SNMP v3 enabled : Yes
Accept SNMP v3 messages only : Yes
monitoringUser SHA AES
monitoringUser ver3 ManagerPriv
"""
        ok, checks = SNMP.snmp_handlers.verify(
            template, output, {"username": "monitoringUser", "group": "ManagerPriv"}, "configure")
        self.assertTrue(ok)
        self.assertTrue(checks["initial_absent"])

    def test_aruba_handler_uses_ephemeral_wizard_credentials(self):
        template = next(item for item in self.templates if item["id"] == "hpe-aruba-2920-wb15-v3")
        context = {"driver": "hpe-arubaos-switch"}
        driver = SNMP.snmp_handlers.login_driver(SNMP.gr, template, context)
        session = driver("manager", "ssh-password")
        action = session.feed(b"Enter authentication password:")
        self.assertEqual(action[0][0], "credential")
        self.assertNotEqual(action[0][1].strip(), b"ssh-password")
        self.assertGreaterEqual(len(action[0][1].strip()), 8)
        self.assertIn("temporary_auth", context)

    def test_cbs_handler_answers_engine_confirmation_as_prompt(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-cbs250-8td-3.1-v3")
        driver = SNMP.snmp_handlers.login_driver(
            SNMP.gr, template, {"driver": "cisco-small-business"})
        session = driver("operator", "ssh-password")
        self.assertEqual(session.feed(b"Do you wish to continue ? (Y/N)[N]"),
                         [("credential", b"y")])

    def test_comware_normalizer_checks_process_acl_sources(self):
        template = next(item for item in self.templates if item["id"] == "hpe-comware7-v3")
        values = {"username": "monitor", "group": "GROUP", "source_1": "192.0.2.1",
                  "source_2": "192.0.2.2", "source_3": "192.0.2.3"}
        output = """snmp-agent sys-info version v3
snmp-agent group v3 GROUP privacy
snmp-agent usm-user v3 monitor GROUP
rule 10 permit source 192.0.2.1 0
rule 20 permit source 192.0.2.2 0
rule 30 permit source 192.0.2.3 0
"""
        ok, checks = SNMP.snmp_handlers.verify(template, output, values, "configure")
        self.assertTrue(ok)
        self.assertTrue(checks["sources"])

    def test_dell_template_does_not_claim_blank_state_configuration(self):
        template = next(item for item in self.templates if item["id"] == "dell-os10-v3")
        self.assertEqual(template["supported_actions"], ["rotate"])

    def test_cleanup_plan_preserves_exact_legacy_line_for_rollback(self):
        template = next(item for item in self.templates if item["id"] == "cisco-ios-v3")
        apply_commands, rollback_commands = SNMP.snmp_handlers.cleanup_plan(
            template, "snmp-server community encrypted-value RO\n", {})
        self.assertIn("no snmp-server community encrypted-value RO", apply_commands)
        self.assertIn("snmp-server community encrypted-value RO", rollback_commands)

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
