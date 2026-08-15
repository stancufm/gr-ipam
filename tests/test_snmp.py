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

    def test_template_match_supports_an_explicit_ip_allowlist(self):
        template = {"match": {"driver": "cisco-ios",
                              "ip_in": ["192.0.2.10", "192.0.2.11"]}}
        self.assertTrue(SNMP.template_matches(template, row()))
        other = row()
        other["ip"] = "192.0.2.12"
        self.assertFalse(SNMP.template_matches(template, other))

    def test_environment_template_override_precedes_persistent_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            stale_path = os.path.join(temporary, "stale-templates.json")
            with open(stale_path, "w", encoding="utf-8") as handle:
                json.dump({"schema_version": 1, "catalog_version": 999,
                           "templates": [{"id": "stale-only", "match": {}}]}, handle)
            source, templates = SNMP.load_templates({"snmp_template_file": stale_path})
            self.assertEqual(os.path.abspath(source),
                             os.path.abspath(os.environ["GR_SNMP_TEMPLATES"]))
            self.assertIn("cisco-business-sx2xx-sx3xx-2x-v3",
                          {item["id"] for item in templates})
            self.assertNotIn("stale-only", {item["id"] for item in templates})

    def test_implicit_privacy_probe_requires_all_non_privacy_checks(self):
        template = {"privacy_protocol_implicit": "AES128", "verify_server_enabled": True}
        checks = {"engine": True, "view": True, "group": True, "user": True,
                  "auth_sha": True, "privacy_aes128": False,
                  "privacy_explicit_non_aes": True, "server_enabled": True}
        self.assertTrue(SNMP.implicit_privacy_probe_candidate(template, checks))
        checks["auth_sha"] = False
        self.assertFalse(SNMP.implicit_privacy_probe_candidate(template, checks))

    def test_implicit_privacy_probe_requires_explicit_template_policy(self):
        checks = {"engine": True, "view": True, "group": True, "user": True,
                  "auth_sha": True}
        self.assertFalse(SNMP.implicit_privacy_probe_candidate({}, checks))

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

    def test_unreviewed_cisco_business_2x_selects_family_candidate(self):
        template, _source = SNMP.resolve_template(
            self.templates, row("cisco-small-business", "SF350-24P", version="2.4.0.94"))
        self.assertEqual(template["id"], "cisco-business-sx2xx-sx3xx-2x-v3")
        self.assertEqual(template["handler"], "cisco-business-2x")
        self.assertFalse(template["apply_supported"])
        self.assertEqual(template["pilot_status"], "blocked-unclassified-privacy-dialect")
        self.assertEqual(template["pilot_evidence"]["os_version"], "2.5.0.83")

    def test_validated_24094_models_select_sha_des_template(self):
        for ip, model in (("10.22.10.23", "SG350-28P"),
                          ("10.22.10.36", "SG250X-24P"),
                          ("10.22.10.47", "SG250-08HP")):
            device = row("cisco-small-business", model, version="2.4.0.94")
            device["ip"] = ip
            template, source = SNMP.resolve_template(self.templates, device)
            self.assertEqual(
                template["id"],
                "cisco-business-2.4.0.94-des-pilot-v3")
            self.assertEqual(source, "selector")
            self.assertEqual(template["privacy_protocol_required"], "DES")
            self.assertEqual(template["pilot_status"], "transactionally-validated")
            self.assertTrue(template["apply_supported"])
            self.assertTrue(template["require_monitoring_test"])
            self.assertTrue(template["preserve_preexisting_engine"])
            self.assertTrue(template["preserve_preexisting_server"])

            self.assertIn("cleanup", template["supported_actions"])
            self.assertEqual(
                template["cleanup_inspect_commands"],
                ["terminal datadump", "show running-config"])

    def test_cisco_business_250_des_candidate_precedes_generic_family(self):
        for model in ("SG350XG-2F10", "SG350X-48MP"):
            template, _source = SNMP.resolve_template(
                self.templates, row("cisco-small-business", model, version="2.5.0.83"))
            self.assertEqual(template["id"], "cisco-business-sg350x-2.5.0-des-v3")
            self.assertEqual(template["privacy_protocol_required"], "DES")
            self.assertTrue(template["apply_supported"])
            self.assertEqual(template["pilot_status"], "transactionally-validated")

    def test_sg350x_24091_selects_validated_exact_template(self):
        template, _source = SNMP.resolve_template(
            self.templates,
            row("cisco-small-business", "SG350X-48MP", version="2.4.0.91"))
        self.assertEqual(template["id"], "cisco-business-sg350x-2.4.0.91-des-v3")
        self.assertEqual(template["privacy_protocol_required"], "DES")
        self.assertTrue(template["apply_supported"])
        self.assertEqual(template["pilot_status"], "transactionally-validated")
        self.assertTrue(template["preserve_preexisting_engine"])

    def test_sg350x_230130_selects_narrow_des_pilot(self):
        template, _source = SNMP.resolve_template(
            self.templates,
            row("cisco-small-business", "SG350X-24PD", version="2.3.0.130"))
        self.assertEqual(template["id"], "cisco-business-sg350x-2.3.0.130-des-v3")
        self.assertEqual(template["privacy_protocol_required"], "DES")
        self.assertTrue(template["apply_supported"])
        self.assertEqual(template["pilot_status"], "transactionally-validated")

    def test_cisco_business_220_selects_distinct_candidate(self):
        template, _source = SNMP.resolve_template(
            self.templates, row("cisco-small-business", "SG220-50P", version="1.1.3.1"))
        self.assertEqual(template["id"], "cisco-business-sg-sf220-1.1.3-aes-v3")
        self.assertEqual(template["handler"], "cisco-business-220")
        self.assertFalse(template["apply_supported"])
        self.assertEqual(template["pilot_status"], "blocked-privacy-des")

    def test_cisco_business_220_other_firmware_remains_blocked(self):
        template, _source = SNMP.resolve_template(
            self.templates, row("cisco-small-business", "SG220-50P", version="1.1.2.0"))
        self.assertEqual(template["id"], "cisco-business-sg-sf220-1.1-v3")
        self.assertFalse(template["apply_supported"])

    def test_cbs_220_pilot_uses_user_syntax_without_v3_or_aes_token(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-sg-sf220-1.1.3-aes-v3")
        command = next(item for item in template["configure_commands"]
                       if item.startswith("snmp-server user "))
        self.assertIn(" auth sha {auth_cli} priv {privacy_cli}", command)
        self.assertNotIn(" v3 auth ", command)
        self.assertNotIn(" priv aes ", command)
        self.assertTrue(template["preserve_preexisting_engine"])
        self.assertTrue(template["preserve_preexisting_server"])

    def test_preexisting_cbs_server_and_engine_are_not_owned_by_rollback(self):
        template = {"preserve_preexisting_engine": True,
                    "preserve_preexisting_server": True}
        commands = ["configure terminal", "snmp-server engineid default",
                    "snmp-server", "end"]
        rollback = ["configure terminal", "no snmp-server",
                    "no snmp-server engineid", "end"]
        output = "SNMP agent is enabled\nLocal SNMP engineID: 800000090300001122334455\n"
        actual, undo = SNMP.preserve_preexisting_snmp_state(
            template, output, commands, rollback)
        self.assertNotIn("snmp-server engineid default", actual)
        self.assertNotIn("snmp-server", actual)
        self.assertNotIn("no snmp-server engineid", undo)
        self.assertNotIn("no snmp-server", undo)

    def test_unknown_cisco_business_remains_report_only(self):
        template, _source = SNMP.resolve_template(
            self.templates, row("cisco-small-business", "Unknown", version=""))
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
                         [("credential", b"y\n")])

    def test_cbs_handler_answers_save_prompts_only_in_save_session(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-sx2xx-sx3xx-2x-v3")
        driver = SNMP.snmp_handlers.login_driver(
            SNMP.gr, template,
            {"driver": "cisco-small-business", "values": {"save_session": True}})
        session = driver("operator", "ssh-password")
        self.assertEqual(session.feed(b"Destination filename [startup-config]?"),
                         [("credential", b"\n")])
        self.assertEqual(session.feed(b"Overwrite file [startup-config] ? [Y/N]:"),
                         [("credential", b"y\n")])

        ordinary_driver = SNMP.snmp_handlers.login_driver(
            SNMP.gr, template, {"driver": "cisco-small-business", "values": {}})
        ordinary = ordinary_driver("operator", "ssh-password")
        self.assertEqual(ordinary.feed(b"Overwrite file [startup-config] ? [Y/N]:"), [])

    def test_cbs_capability_handler_clears_retained_help_line(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-sx2xx-sx3xx-2x-v3")
        driver = SNMP.snmp_handlers.login_driver(
            SNMP.gr, template,
            {"driver": "cisco-small-business", "values": {"capability_probe": True}})
        self.assertTrue(driver.GR_RAW_PTY)
        session = driver("operator", "ssh-password")
        session.state = "ready"
        self.assertEqual(
            session.feed(b"read  Specify a read view\r\nSw(config)#snmp-server group X v3 priv \x03"),
            [("credential", b"\x03")])

    def test_cbs_capability_handler_accepts_repainted_inline_prompt(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-sx2xx-sx3xx-2x-v3")
        driver = SNMP.snmp_handlers.login_driver(
            SNMP.gr, template,
            {"driver": "cisco-small-business", "values": {"capability_probe": True}})
        session = driver("operator", "ssh-password")
        session.state = "ready"
        self.assertEqual(
            session.feed(
                b"SW-64(config)#snmp-server group GR_CAP_GROUP v3 priv SW-64(config)#"),
            [("prompt", b"")])

    def test_cbs_handler_declines_expired_ssh_password_change(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-sx2xx-sx3xx-2x-v3")
        driver = SNMP.snmp_handlers.login_driver(
            SNMP.gr, template, {"driver": "cisco-small-business", "values": {}})
        session = driver("operator", "ssh-password")
        session.state = "prompt"
        self.assertEqual(driver.GR_PTY_COLUMNS, 512)
        self.assertEqual(
            session.feed(b"Do you want to change it now (Y/N)[N] \x1b[30;120R?"),
            [("credential", b"n\n")])

    def test_capability_output_removes_terminal_cursor_controls(self):
        output = "before\x1b[30;120Rafter\rnext\x03"
        self.assertEqual(SNMP.sanitized_capability_output(output), "beforeafter\nnext")

    def test_safe_apply_diagnostics_redacts_both_snmp_secrets(self):
        output = ("Sw(config)#$ user monitor group v3 auth sha AuthSecret9 "
                  "priv PrivSec\n"
                  "Sw(config)#$ret9\n"
                  "Warning: privacy password failed complexity")
        lines = SNMP.safe_apply_diagnostics(
            output, {"auth_password": "AuthSecret9", "privacy_password": "PrivSecret9"})
        rendered = "\n".join(lines)
        self.assertNotIn("AuthSecret9", rendered)
        self.assertNotIn("PrivSecret9", rendered)
        self.assertNotIn("PrivSec", rendered)
        self.assertNotIn("ret9", rendered)
        self.assertIn("failed complexity", rendered)

    def test_cbs_2x_handler_does_not_quote_cli_secrets(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-sx2xx-sx3xx-2x-v3")
        prepared = SNMP.snmp_handlers.prepare(
            template, row("cisco-small-business", "SG350X-48MP", version="2.5.0.83"),
            {"auth_password": "AuthSecret9", "privacy_password": "PrivSecret9"},
            applying=True)
        self.assertEqual(prepared["auth_cli"], "AuthSecret9")
        self.assertEqual(prepared["privacy_cli"], "PrivSecret9")

    def test_cbs_authpriv_verifier_requires_reported_sha_and_aes128(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-sx2xx-sx3xx-2x-v3")
        values = {"username": "monitor", "group": "SNMP_DEFAULT_GROUP",
                  "view": "SNMP_DEFAULT_VIEW"}
        output = """SNMP is enabled
Local SNMP engineID is 800000090300001122334455
SNMP_DEFAULT_VIEW iso included
SNMP_DEFAULT_GROUP V3 priv
User name : monitor
Authentication Method : SHA
Privacy Method : AES-128
"""
        ok, checks = SNMP.snmp_handlers.verify(template, output, values, "configure")
        self.assertTrue(ok)
        self.assertTrue(checks["privacy_aes128"])

    def test_cbs_authpriv_verifier_accepts_template_declared_implicit_aes128(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-sx2xx-sx3xx-2x-v3")
        values = {"username": "monitor", "group": "SNMP_DEFAULT_GROUP",
                  "view": "SNMP_DEFAULT_VIEW"}
        output = """SNMP is enabled
Local SNMP engineID is 800000090300001122334455
SNMP_DEFAULT_VIEW iso included
SNMP_DEFAULT_GROUP V3 priv
User name : monitor
Authentication Method : SHA
"""
        ok, checks = SNMP.snmp_handlers.verify(template, output, values, "configure")
        self.assertTrue(ok)
        self.assertTrue(checks["privacy_aes128"])

    def test_cbs_server_verifier_accepts_agent_word_and_punctuation(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-sx2xx-sx3xx-2x-v3")
        values = {"username": "monitor", "group": "SNMP_DEFAULT_GROUP",
                  "view": "SNMP_DEFAULT_VIEW"}
        output = """SNMP agent is enabled.
Local SNMP engineID is 800000090300001122334455
SNMP_DEFAULT_VIEW iso included
SNMP_DEFAULT_GROUP V3 priv
User name : monitor
Authentication Method : SHA
Privacy Method : AES-128
"""
        ok, checks = SNMP.snmp_handlers.verify(template, output, values, "configure")
        self.assertTrue(ok)
        self.assertTrue(checks["server_enabled"])
        self.assertFalse(checks["server_disabled_explicit"])

    def test_cbs_authpriv_verifier_rejects_explicit_des(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-sx2xx-sx3xx-2x-v3")
        values = {"username": "monitor", "group": "SNMP_DEFAULT_GROUP",
                  "view": "SNMP_DEFAULT_VIEW"}
        output = """SNMP is enabled
Local SNMP engineID is 800000090300001122334455
SNMP_DEFAULT_VIEW iso included
SNMP_DEFAULT_GROUP V3 priv
User name : monitor
Authentication Method : SHA
Privacy Method : DES
"""
        ok, checks = SNMP.snmp_handlers.verify(template, output, values, "configure")
        self.assertFalse(ok)
        self.assertFalse(checks["privacy_aes128"])

    def test_cbs_des_candidate_accepts_reported_sha_and_des(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-sg350x-2.5.0-des-v3")
        values = {"username": "monitor", "group": "SNMP_DEFAULT_GROUP",
                  "view": "SNMP_DEFAULT_VIEW"}
        output = """SNMP is enabled
Local SNMP engineID is 800000090300001122334455
SNMP_DEFAULT_VIEW iso included
SNMP_DEFAULT_GROUP V3 priv
User name : monitor
Authentication Protocol : SHA
Privacy Protocol : DES
"""
        ok, checks = SNMP.snmp_handlers.verify(template, output, values, "configure")
        self.assertTrue(ok)
        self.assertTrue(checks["privacy_des"])
        self.assertTrue(checks["privacy_expected"])
        self.assertEqual(checks["privacy_required"], "DES")

    def test_cbs_des_candidate_has_transactional_commands(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-sg350x-2.5.0-des-v3")
        self.assertTrue(template["apply_supported"])
        self.assertEqual(template["workflow"], "transactional-cli-v1")
        self.assertTrue(template["require_monitoring_test"])
        self.assertEqual(template["privacy_protocol_required"], "DES")
        self.assertIn("configure", template["supported_actions"])
        self.assertIn("rotate", template["supported_actions"])
        create_user = next(command for command in template["configure_commands"]
                           if command.startswith("snmp-server user "))
        self.assertIn(" auth sha {auth_cli} priv {privacy_cli}", create_user)
        self.assertNotIn(" priv aes ", create_user)
        self.assertTrue(template["configure_rollback_commands"])
        self.assertTrue(template["save_commands"])

    def test_sw51_exact_des_template_is_transactional_after_live_pilot(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-sg350x-2.4.0.91-des-v3")
        self.assertTrue(template["apply_supported"])
        self.assertEqual(template["pilot_status"], "transactionally-validated")
        self.assertEqual(template["privacy_protocol_required"], "DES")
        self.assertEqual(template["post_apply_settle_seconds"], 2)
        self.assertTrue(template["require_monitoring_test"])

    def test_generic_cbs_2x_apply_remains_blocked(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-sx2xx-sx3xx-2x-v3")
        self.assertFalse(template["apply_supported"])

    def test_cbs_authpriv_verifier_scopes_privacy_to_target_user(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-sx2xx-sx3xx-2x-v3")
        values = {"username": "monitor", "group": "SNMP_DEFAULT_GROUP",
                  "view": "SNMP_DEFAULT_VIEW"}
        output = """SNMP is enabled
Local SNMP engineID is 800000090300001122334455
SNMP_DEFAULT_VIEW iso included
SNMP_DEFAULT_GROUP V3 priv
User name : unrelated
Authentication Method : None
Privacy Method : None
User name : monitor
Authentication Method : SHA
"""
        ok, checks = SNMP.snmp_handlers.verify(template, output, values, "configure")
        self.assertTrue(ok)
        self.assertFalse(checks["privacy_explicit_non_aes"])
        self.assertTrue(checks["privacy_implicit_policy"])

    def test_auth_no_priv_config_omits_privacy_credentials(self):
        credentials = {"security_level": "authNoPriv", "username": "monitor",
                       "auth_protocol": "SHA", "auth_password": "AuthSecret9",
                       "privacy_protocol": "AES", "privacy_password": "PrivSecret9"}
        output = SNMP.snmp_config_text(credentials)
        self.assertIn("defSecurityLevel authNoPriv", output)
        self.assertNotIn("defPrivType", output)
        self.assertNotIn("PrivSecret9", output)

    def test_cbs_2x_rollback_removes_view_without_create_qualifiers(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-sx2xx-sx3xx-2x-v3")
        self.assertIn("no snmp-server view {view}",
                      template["configure_rollback_commands"])
        self.assertNotIn("no snmp-server view {view} iso included",
                         template["configure_rollback_commands"])

    def test_capability_probe_rejects_mutating_template_command(self):
        with self.assertRaises(SNMP.gr.GrError):
            SNMP.validate_capability_commands([
                "configure terminal", "snmp-server engineID local default", "end"])

    def test_capability_probe_accepts_only_incomplete_snmp_commands(self):
        SNMP.validate_capability_commands([
            "terminal datadump", "configure terminal",
            "snmp-server user GRcapProbe GR_CAP_GROUP v3 auth sha ?", "end"])

    def test_cbs_2x_capability_normalizer_does_not_guess_implicit_algorithm(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-sx2xx-sx3xx-2x-v3")
        output = """default -- Create default engine ID
read -- Specify a read view
sha -- Use HMAC SHA algorithm
WORD<1-32> Specify the authentication password
WORD<1-32> Specify the privacy password
"""
        checks = SNMP.snmp_handlers.capabilities(template, output)
        self.assertTrue(checks["confirmed"])
        self.assertEqual(checks["privacy_algorithm"], "implicit-unverified")

    def test_cbs_220_capability_normalizer_matches_live_help(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-sg-sf220-1.1-v3")
        output = """default local engine ID default octet string (mac address)
read-view specify a read view for the group
md5 Use HMAC MD5 algorithm for authentication
sha Use HMAC SHA algorithm for authentication
AUTHPASSWD Authentication password for user (length 8~32)
PRIVPASSWD Privacy password for user (length 8~64)
"""
        checks = SNMP.snmp_handlers.capabilities(template, output)
        self.assertTrue(checks["confirmed"])
        self.assertEqual(checks["syntax_family"], "cisco-business-220-1.1")

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

    def test_cisco_business_cleanup_removes_only_community_token(self):
        template = next(item for item in self.templates
                        if item["id"] == "cisco-business-2.4.0.94-des-pilot-v3")
        apply_commands, rollback_commands = SNMP.snmp_handlers.cleanup_plan(
            template, 'snmp-server community "legacy value" ro view Default\n', {})
        self.assertIn('no snmp-server community "legacy value"', apply_commands)
        self.assertNotIn(
            'no snmp-server community "legacy value" ro view Default', apply_commands)
        self.assertIn(
            'snmp-server community "legacy value" ro view Default', rollback_commands)

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

    def test_parser_supports_read_only_capability_probe(self):
        args = SNMP.build_parser().parse_args([
            "capabilities", "--ip", "192.0.2.10"])
        self.assertEqual(args.action, "capabilities")

    def test_configure_pilot_options_are_explicit(self):
        args = SNMP.build_parser().parse_args([
            "configure", "--ip", "192.0.2.10", "--include-disabled",
            "--monitoring-profile", "librenms"])
        self.assertTrue(args.include_disabled)
        self.assertEqual(args.monitoring_profile, "librenms")

    def test_remote_snmpget_keeps_secrets_out_of_argv(self):
        monitor = {"ip": "192.0.2.20", "hostname": "monitor",
                   "custom_ssh_enabled": 1, "custom_ssh_user": "operator",
                   "custom_ssh_port": "22", "custom_ssh_profile": "linux",
                   "custom_ssh_client": "normal"}

        class Api:
            def addresses(self):
                return [monitor]
            def request(self, _method, _path, payload=None):
                return {"data": []}

        class Session:
            def __enter__(self):
                return Api()
            def __exit__(self, *_args):
                return False

        credentials = {"username": "snmp-user", "auth_protocol": "SHA",
                       "privacy_protocol": "AES", "auth_password": "auth-secret",
                       "privacy_password": "priv-secret"}

        class Process:
            returncode = 0
            def communicate(self, payload, timeout=None):
                self.payload = payload
                self.assert_payload(payload)
                return b"", b""
            def assert_payload(self, payload):
                self_test.assertIn(b"auth-secret", payload)
                self_test.assertIn(b"priv-secret", payload)

        self_test = self
        def popen(command, **_kwargs):
            joined = " ".join(command)
            self.assertNotIn("auth-secret", joined)
            self.assertNotIn("priv-secret", joined)
            self.assertEqual(command[-2:], ["/bin/sh", "-s"])
            return Process()

        cfg = {"monitoring_profiles": {"librenms": {"host": "192.0.2.20"}}}
        with mock.patch.object(SNMP.gr, "api_session", return_value=Session()), \
                mock.patch.object(SNMP.gr, "read_vault_password", return_value="ssh-secret"), \
                mock.patch.object(SNMP.gr, "ensure_known_hosts", return_value="/tmp/known"), \
                mock.patch.object(SNMP.subprocess, "Popen", side_effect=popen):
            self.assertEqual(
                SNMP.remote_snmpget(cfg, "librenms", "192.0.2.10", credentials),
                (0, ""))

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
                mock.patch.object(SNMP.subprocess, "run", return_value=completed), \
                mock.patch.object(SNMP.time, "sleep"):
            with self.assertRaises(SNMP.gr.GrError):
                SNMP.backup_configuration("192.0.2.10")

    def test_configuration_backup_retries_transient_collection_failure(self):
        failed = types.SimpleNamespace(returncode=2, stdout="RESULT test failed\n", stderr="")
        passed = types.SimpleNamespace(
            returncode=0,
            stdout='SUMMARY={"success": 1}\nARCHIVE=/archive\nCOMMIT=unchanged\n',
            stderr="")
        with mock.patch.object(SNMP.os.path, "isfile", return_value=True), \
                mock.patch.object(SNMP.subprocess, "run", side_effect=[failed, passed]) as run, \
                mock.patch.object(SNMP.time, "sleep") as sleep:
            SNMP.backup_configuration("192.0.2.10")
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(2)

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
