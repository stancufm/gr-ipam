#!/usr/bin/env python3
import contextlib
import io
import unittest
from unittest import mock

from support import load_source


GR = load_source("gr_device_save_test_module", "bin/gr")


def device(ip, driver="cisco-ios", model="C9200-24T", enabled=1,
           profile="network-admin"):
    return {
        "id": ip.rsplit(".", 1)[-1],
        "ip": ip,
        "hostname": "sw{}".format(ip.rsplit(".", 1)[-1]),
        "custom_ssh_enabled": enabled,
        "custom_ssh_user": "operator",
        "custom_ssh_port": "22",
        "custom_ssh_profile": profile,
        "custom_ssh_client": "normal",
        "custom_device_driver": driver,
        "custom_device_model": model,
    }


def configuration():
    return {"ssh_profiles": {
        "network-admin": {"password_secret": "gr/network-admin"},
    }}


class FakeApi:
    def __init__(self, rows):
        self.rows = rows

    def addresses(self):
        return self.rows


class DeviceSaveTests(unittest.TestCase):
    def test_driver_registry_owns_save_commands(self):
        self.assertEqual(
            GR.device_driver_spec("cisco-ios")["save_commands"],
            ("enable", "write memory"))
        self.assertEqual(
            GR.device_driver_spec("cisco-small-business")["save_commands"],
            ("terminal datadump", "copy running-config startup-config"))
        self.assertEqual(
            GR.device_driver_spec("planet-sgs")["save_commands"],
            ("enable", "write"))
        self.assertEqual(
            GR.device_driver_spec("dell-os10")["save_commands"],
            ("write memory",))
        self.assertEqual(
            GR.device_driver_spec("hpe-arubaos-switch")["save_commands"],
            ("write memory",))
        self.assertEqual(
            GR.device_driver_spec("hpe-comware7")["save_commands"],
            ("save force",))
        self.assertEqual(
            GR.device_driver_spec("fortigate-fortios")["save_mode"],
            "automatic")

    def test_validated_sf250_uses_short_write_dialect(self):
        row = device("192.0.2.10", "cisco-small-business", "SF250-24P")
        self.assertEqual(
            GR.device_save_commands(row, "cisco-small-business"),
            ["terminal datadump", "write"])
        other = device("192.0.2.11", "cisco-small-business", "SG350-28P")
        self.assertEqual(
            GR.device_save_commands(other, "cisco-small-business"),
            ["terminal datadump", "copy running-config startup-config"])

    def test_save_login_confirms_only_save_prompts(self):
        login = GR.CiscoSmallBusinessSaveLogin("operator", "secret")
        login.state = "ready"
        self.assertEqual(
            login.feed(b"Destination filename [startup-config]?"),
            [("credential", b"\n")])
        self.assertEqual(
            login.feed(b"Overwrite file [startup-config].... (Y/N)[N] ?"),
            [("credential", b"y\n")])
        self.assertEqual(login.feed(b"Do you want to erase flash? [Y/N]:"), [])

    def test_parser_requires_ip_model_or_all_and_apply_is_explicit(self):
        parser = GR.build_parser()
        args = parser.parse_args([
            "device", "save", "--ip", "192.0.2.10", "--ip", "192.0.2.11"])
        self.assertEqual(args.ips, ["192.0.2.10", "192.0.2.11"])
        self.assertFalse(args.apply)
        models = parser.parse_args([
            "device", "save", "--model", "SG350*", "--model", "SF250-24P",
            "--apply"])
        self.assertEqual(models.models, ["SG350*", "SF250-24P"])
        self.assertTrue(models.apply)
        with self.assertRaises(SystemExit):
            parser.parse_args(["device", "save"])
        with self.assertRaises(SystemExit):
            parser.parse_args(["device", "save", "--all", "--ip", "192.0.2.10"])

    def test_selectors_are_exact_for_ip_and_case_insensitive_globs_for_model(self):
        rows = [
            device("192.0.2.10", model="C9200-24T"),
            device("192.0.2.11", "cisco-small-business", "SG350-28P"),
            device("192.0.2.12", "generic", "Linux VM"),
        ]
        ip_args = GR.build_parser().parse_args([
            "device", "save", "--ip", "192.0.2.11"])
        self.assertEqual(
            [str(row["_ip"]) for row in GR.select_device_save_rows(rows, ip_args)],
            ["192.0.2.11"])
        model_args = GR.build_parser().parse_args([
            "device", "save", "--model", "sg350*"])
        self.assertEqual(
            [str(row["_ip"]) for row in GR.select_device_save_rows(rows, model_args)],
            ["192.0.2.11"])
        all_args = GR.build_parser().parse_args(["device", "save", "--all"])
        self.assertEqual(
            [str(row["_ip"]) for row in GR.select_device_save_rows(rows, all_args)],
            ["192.0.2.10", "192.0.2.11"])

    def test_ip_selector_reports_unknown_addresses(self):
        args = GR.build_parser().parse_args([
            "device", "save", "--ip", "192.0.2.99"])
        with self.assertRaisesRegex(GR.GrError, "192.0.2.99"):
            GR.select_device_save_rows([device("192.0.2.10")], args)

    def test_plan_blocks_incomplete_ssh_and_marks_fortios_automatic(self):
        blocked = GR.normalized_addresses([
            device("192.0.2.10", enabled=0)])[0]
        plan = GR.device_save_plan(configuration(), blocked)
        self.assertEqual(plan["status"], "blocked")
        self.assertIn("ssh_enabled", plan["detail"])

        fortigate = GR.normalized_addresses([
            device("192.0.2.11", "fortigate-fortios", "FortiGate-100F", enabled=0,
                   profile="")])[0]
        plan = GR.device_save_plan(configuration(), fortigate)
        self.assertEqual(plan["status"], "automatic")
        self.assertEqual(plan["commands"], [])

    def test_preview_never_executes_or_reads_vault(self):
        args = GR.build_parser().parse_args([
            "device", "save", "--ip", "192.0.2.10"])

        @contextlib.contextmanager
        def session(*_args, **_kwargs):
            yield FakeApi([device("192.0.2.10")])

        output = io.StringIO()
        with mock.patch.object(GR, "api_session", session), \
                mock.patch.object(GR, "apply_device_save") as apply_save, \
                mock.patch.object(GR, "read_vault_password") as vault, \
                contextlib.redirect_stdout(output):
            self.assertEqual(GR.command_device_save(configuration(), args), 0)
        apply_save.assert_not_called()
        vault.assert_not_called()
        self.assertIn("DRY_RUN=True", output.getvalue())
        self.assertIn("write memory", output.getvalue())

    def test_apply_continues_after_one_failure_and_reports_summary(self):
        args = GR.build_parser().parse_args([
            "device", "save", "--all", "--apply"])
        rows = [device("192.0.2.10"), device("192.0.2.11")]

        @contextlib.contextmanager
        def session(*_args, **_kwargs):
            yield FakeApi(rows)

        success = {"success": True, "returncode": -15, "complete": True,
                   "timeout": False, "cli_errors": 0, "stdout": "", "stderr": "",
                   "audit": "/tmp/success.ses"}
        output = io.StringIO()
        with mock.patch.object(GR, "api_session", session), \
                mock.patch.object(
                    GR, "apply_device_save",
                    side_effect=[GR.GrError("connection failed"), success]) as apply_save, \
                contextlib.redirect_stdout(output):
            self.assertEqual(GR.command_device_save(configuration(), args), 2)
        self.assertEqual(apply_save.call_count, 2)
        self.assertIn('"failed": 1', output.getvalue())
        self.assertIn('"success": 1', output.getvalue())

    def test_failure_detail_prefers_device_cli_error(self):
        self.assertEqual(
            GR.device_save_failure_detail(
                "% Invalid input detected", "transport detail", False, 1),
            "% Invalid input detected")
        self.assertEqual(
            GR.device_save_failure_detail("", "", True, 0), "timeout")


if __name__ == "__main__":
    unittest.main()
