#!/usr/bin/env python3
import importlib.machinery
import importlib.util
import json
import os
import tempfile
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

    def test_reviewed_planet_build_suffix_selects_apply_handler(self):
        template, _source = SNMP.resolve_template(
            self.templates,
            row("planet-sgs", "SGS-6310-16S8C4XR", version="2.2.0E Build 97938"))
        self.assertEqual(template["id"], "planet-sgs-6310-2.2-v3")
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
                       "privacy_password": "priv-secret", "source_address": "192.0.2.20"}

        def run(command, **kwargs):
            joined = " ".join(command)
            self.assertNotIn("auth-secret", joined)
            self.assertNotIn("priv-secret", joined)
            config = os.path.join(kwargs["env"]["SNMPCONFPATH"], "snmp.conf")
            self.assertEqual(os.stat(config).st_mode & 0o777, 0o600)
            with open(config, encoding="utf-8") as handle:
                self.assertIn("clientaddr 192.0.2.20", handle.read())
            return types.SimpleNamespace(returncode=0, stderr="")

        with mock.patch.object(SNMP.subprocess, "run", side_effect=run):
            self.assertEqual(SNMP.snmpget("192.0.2.10", credentials), (0, ""))

    def test_profile_source_address_must_be_an_approved_source(self):
        cfg = {"snmp_profiles": {"monitor": {
            "username": "snmp-user", "auth_protocol": "SHA", "privacy_protocol": "AES",
            "sources": ["192.0.2.20"], "source_address": "192.0.2.21"}}}
        args = types.SimpleNamespace(profile="monitor", username=None,
                                     prompt_credentials=False)
        with self.assertRaises(SNMP.gr.GrError):
            SNMP.profile_values(cfg, row(), args, need_secrets=False)

    def test_authentication_failure_takes_priority_over_timeout_text(self):
        detail = "Timeout while discovering engine ID\nsnmpget: Authentication failure (incorrect password or key)"
        self.assertEqual(SNMP.snmp_test_status(1, detail), "failed")
        self.assertEqual(SNMP.snmp_test_status(1, "Timeout: No Response"), "timeout")
        self.assertEqual(SNMP.snmp_test_status(0, ""), "success")

    def test_parser_supports_all_report_modes(self):
        for mode in ("inventory", "live", "offline", "ports"):
            args = SNMP.build_parser().parse_args(["report", "--ip", "192.0.2.10", "--mode", mode])
            self.assertEqual(args.mode, mode)

    def test_ports_report_accepts_source_profile(self):
        args = SNMP.build_parser().parse_args([
            "report", "--ip", "192.0.2.10", "--mode", "ports", "--profile", "monitor"])
        self.assertEqual(args.profile, "monitor")

    def test_managed_report_and_duplicate_exclusion_options(self):
        args = SNMP.build_parser().parse_args([
            "report", "--all", "--managed-only",
            "--exclude-ip", "192.0.2.20", "--exclude-ip", "192.0.2.21"])
        self.assertTrue(args.managed_only)
        self.assertEqual(args.exclude_ip, ["192.0.2.20", "192.0.2.21"])

    def test_select_rows_excludes_duplicate_paths(self):
        args = types.SimpleNamespace(all=True, ip=None, subnet=None, ip_range=None,
                                     file=None, exclude_ip=["192.0.2.11"])
        selected = SNMP.select_rows(
            [row(), dict(row(), ip="192.0.2.11")], args)
        self.assertEqual([SNMP.row_ip(item) for item in selected], ["192.0.2.10"])

    def test_managed_row_requires_driver_or_explicit_intent(self):
        self.assertFalse(SNMP.managed_row({"ip": "192.0.2.1"}))
        self.assertTrue(SNMP.managed_row(row()))
        self.assertTrue(SNMP.managed_row({"ip": "192.0.2.2", "custom_snmp_enabled": 1}))

    def test_phpipam_response_row_accepts_unwrapped_and_enveloped_data(self):
        value = {"id": "10", "custom_device_model": "model"}
        self.assertEqual(SNMP.response_row(value), value)
        self.assertEqual(SNMP.response_row({"data": value}), value)
        self.assertEqual(SNMP.response_row({"data": [value]}), value)
        self.assertEqual(SNMP.response_row(None), {})

    def test_inventory_sync_accepts_multiple_reports(self):
        args = SNMP.build_parser().parse_args([
            "inventory-sync", "--report", "old.json", "--report", "new.json"])
        self.assertEqual(args.report, ["old.json", "new.json"])

    def test_inventory_sync_is_idempotent_and_later_report_wins(self):
        address = dict(row(), id="10", custom_device_model="new-model",
                       custom_os_version="new-version")

        class Api:
            patches = []
            def addresses(self):
                return [address]
            def request(self, method, path, payload=None):
                if path == "devices/":
                    return {"data": []}
                if method == "PATCH":
                    self.patches.append(payload)
                return {"data": address}

        class Session:
            def __enter__(self):
                return Api()
            def __exit__(self, *_args):
                return False

        paths = []
        try:
            for model, version in (("old-model", "old-version"),
                                   ("new-model", "new-version")):
                handle = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
                json.dump({"results": [{"ip": "192.0.2.10", "model": model,
                                         "firmware": version, "result": "success"}]}, handle)
                handle.close(); paths.append(handle.name)
            args = types.SimpleNamespace(report=paths, apply=True)
            with mock.patch.object(SNMP.gr, "api_session", return_value=Session()):
                self.assertEqual(SNMP.command_inventory_sync({}, args), 0)
            self.assertEqual(Api.patches, [])
        finally:
            for path in paths:
                os.unlink(path)

    def test_inventory_sync_verifies_applied_metadata(self):
        address = dict(row(), id="10", custom_device_model="", custom_os_version="")

        class Api:
            patches = []
            def addresses(self):
                return [address]
            def request(self, method, path, payload=None):
                if path == "devices/":
                    return {"data": []}
                if method == "PATCH":
                    address.update(payload); self.patches.append(payload)
                return address

        class Session:
            def __enter__(self):
                return Api()
            def __exit__(self, *_args):
                return False

        handle = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        try:
            json.dump({"results": [{"ip": "192.0.2.10", "model": "verified-model",
                                     "firmware": "verified-version", "result": "success"}]}, handle)
            handle.close()
            args = types.SimpleNamespace(report=[handle.name], apply=True)
            with mock.patch.object(SNMP.gr, "api_session", return_value=Session()):
                self.assertEqual(SNMP.command_inventory_sync({}, args), 0)
            self.assertEqual(len(Api.patches), 1)
            self.assertEqual(address["custom_device_model"], "verified-model")
        finally:
            if not handle.closed:
                handle.close()
            os.unlink(handle.name)

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

    def test_monitor_poll_runs_lnms_from_application_directory(self):
        completed = types.SimpleNamespace(returncode=0, stdout="poll complete\n", stderr="")
        with mock.patch.object(SNMP.subprocess, "run", return_value=completed) as run:
            rc, detail = SNMP.monitoring_poll({"host": "192.0.2.20"}, "40")
        self.assertEqual(rc, 0)
        self.assertEqual(detail, "poll complete")
        command = run.call_args[0][0]
        self.assertEqual(command[:4], ["gr", "exec", "192.0.2.20", "--sudo"])
        self.assertEqual(command[-2], "-lc")
        self.assertEqual(command[-1],
                         "cd /opt/librenms && exec ./lnms device:poll 40 --no-interaction")

    def test_monitor_poll_rejects_non_numeric_device_id(self):
        with self.assertRaises(SNMP.gr.GrError):
            SNMP.monitoring_poll({"host": "192.0.2.20"}, "40; unsafe")

    def test_poll_error_summary_ignores_buffered_exec_banner(self):
        detail = "poller reported a failure\nExecuting on user@192.0.2.20:22 using profile linux"
        self.assertEqual(SNMP.poll_error_summary(detail), "poller reported a failure")

    def test_unauthenticated_unknown_user_proves_agent_response(self):
        completed = types.SimpleNamespace(returncode=1, stdout="",
                                          stderr="Unknown user name")
        with mock.patch.object(SNMP.subprocess, "run", return_value=completed):
            status, _detail = SNMP.unauthenticated_probe("192.0.2.10")
        self.assertEqual(status, "responsive")

    def test_unauthenticated_probe_binds_configured_source(self):
        def run(_command, **kwargs):
            config = os.path.join(kwargs["env"]["SNMPCONFPATH"], "snmp.conf")
            with open(config, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "clientaddr 192.0.2.20\n")
            return types.SimpleNamespace(returncode=1, stdout="", stderr="Unknown user name")

        with mock.patch.object(SNMP.subprocess, "run", side_effect=run):
            status, _detail = SNMP.unauthenticated_probe(
                "192.0.2.10", source_address="192.0.2.20")
        self.assertEqual(status, "responsive")


if __name__ == "__main__":
    unittest.main()
