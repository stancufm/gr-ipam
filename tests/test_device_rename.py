#!/usr/bin/env python3
import contextlib
import io
import unittest
from unittest import mock

from support import load_source


GR = load_source("gr_device_rename_test_module", "bin/gr")


def device(ip="192.0.2.10", hostname="edge-switch", driver="cisco-ios",
           model="C9200-24T", enabled=1, profile="network-admin"):
    return {
        "id": "10",
        "ip": ip,
        "hostname": hostname,
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


def api_session_for(rows):
    @contextlib.contextmanager
    def session(*_args, **_kwargs):
        yield FakeApi(rows)
    return session


class DeviceRenameTests(unittest.TestCase):
    def test_driver_registry_owns_rename_commands(self):
        expected = {
            "cisco-ios": "hostname {hostname}",
            "cisco-small-business": "hostname {hostname}",
            "planet-sgs": "hostname {hostname}",
            "dell-os10": "hostname {hostname}",
            "hpe-arubaos-switch": "hostname {hostname}",
            "hpe-comware7": "sysname {hostname}",
            "fortigate-fortios": "set hostname {hostname}",
        }
        for driver, command in expected.items():
            self.assertIn(command, GR.device_driver_spec(driver)["rename_commands"])

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(GR.command_driver_list(), 0)
        self.assertIn("RENAME COMMANDS", output.getvalue())
        self.assertIn("set hostname {hostname}", output.getvalue())

    def test_model_rules_replace_address_specific_quoting(self):
        old_cbs = GR.normalized_addresses([
            device(driver="cisco-small-business", model="SG220-26")])[0]
        commands = GR.device_rename_commands(old_cbs, "cisco-small-business", "edge-switch")
        self.assertIn('hostname "edge-switch"', commands)

        current_cbs = GR.normalized_addresses([
            device(driver="cisco-small-business", model="SG350-28P")])[0]
        commands = GR.device_rename_commands(
            current_cbs, "cisco-small-business", "edge-switch")
        self.assertIn("hostname edge-switch", commands)
        self.assertNotIn('hostname "edge-switch"', commands)

    def test_aruba_quotes_hostname_and_comware_uses_system_view(self):
        aruba = GR.normalized_addresses([
            device(driver="hpe-arubaos-switch", model="Aruba 2930F")])[0]
        self.assertIn(
            'hostname "edge-switch"',
            GR.device_rename_commands(aruba, "hpe-arubaos-switch", "edge-switch"))
        comware = GR.normalized_addresses([
            device(driver="hpe-comware7", model="HPE 5520")])[0]
        self.assertEqual(
            GR.device_rename_commands(comware, "hpe-comware7", "edge-switch"),
            ["screen-length disable", "system-view", "sysname edge-switch", "return"])

    def test_parser_is_dry_run_and_optional_hostname_is_only_an_assertion(self):
        parser = GR.build_parser()
        args = parser.parse_args(["device", "rename", "192.0.2.10"])
        self.assertFalse(args.apply)
        self.assertIsNone(args.new_hostname)
        asserted = parser.parse_args([
            "device", "rename", "192.0.2.10", "edge-switch", "--apply"])
        self.assertTrue(asserted.apply)
        self.assertEqual(asserted.new_hostname, "edge-switch")

    def test_phpipam_hostname_is_authoritative(self):
        row = GR.normalized_addresses([device()])[0]
        plan = GR.device_rename_plan(configuration(), row)
        self.assertEqual(plan["hostname"], "edge-switch")
        with self.assertRaisesRegex(GR.GrError, "update phpIPAM first"):
            GR.device_rename_plan(configuration(), row, "other-switch")
        with self.assertRaisesRegex(GR.GrError, "phpIPAM has no hostname"):
            GR.device_rename_plan(
                configuration(), GR.normalized_addresses([device(hostname="")])[0])

    def test_invalid_hostname_is_rejected_before_any_connection(self):
        row = GR.normalized_addresses([device()])[0]
        with self.assertRaisesRegex(GR.GrError, "letters, digits and hyphens"):
            GR.device_hostname_cli_value(row, "cisco-ios", "bad name")

    def test_prompt_verification_is_driver_aware(self):
        self.assertTrue(GR.device_hostname_prompt_seen(
            "old#hostname edge-switch\r\nedge-switch(config)#\r\nedge-switch#\r\n",
            "cisco-ios", "edge-switch"))
        self.assertTrue(GR.device_hostname_prompt_seen(
            "[edge-switch]\r\n<edge-switch>\r\n", "hpe-comware7", "edge-switch"))
        self.assertFalse(GR.device_hostname_prompt_seen(
            "old#hostname edge-switch\r\nold#\r\n", "cisco-ios", "edge-switch"))

    def test_comware_login_accepts_command_and_system_view_prompts(self):
        login = GR.HpeComwareLogin("operator", "secret")
        self.assertEqual(login.feed(b"<edge-switch>"), [("ready", b"")])
        self.assertEqual(login.feed(b"\r\n[edge-switch]"), [("prompt", b"")])

    def test_preview_never_backs_up_connects_or_reads_vault(self):
        args = GR.build_parser().parse_args([
            "device", "rename", "192.0.2.10"])
        output = io.StringIO()
        with mock.patch.object(GR, "api_session", api_session_for([device()])), \
                mock.patch.object(GR, "command_helper") as backup, \
                mock.patch.object(GR, "apply_device_rename") as rename, \
                mock.patch.object(GR, "read_vault_password") as vault, \
                contextlib.redirect_stdout(output):
            self.assertEqual(GR.command_device_rename(configuration(), args), 0)
        backup.assert_not_called()
        rename.assert_not_called()
        vault.assert_not_called()
        self.assertIn("DRY_RUN=True", output.getvalue())

    def test_backup_failure_aborts_before_device_change(self):
        args = GR.build_parser().parse_args([
            "device", "rename", "192.0.2.10", "--apply"])
        with mock.patch.object(GR, "api_session", api_session_for([device()])), \
                mock.patch.object(GR, "command_helper", return_value=2) as backup, \
                mock.patch.object(GR, "apply_device_rename") as rename:
            self.assertEqual(GR.command_device_rename(configuration(), args), 2)
        backup.assert_called_once_with(
            GR.CONFIG_COLLECTOR,
            ["--workers", "1", "--ip", "192.0.2.10", "--driver", "cisco-ios"])
        rename.assert_not_called()

    def test_save_runs_only_after_verified_rename(self):
        args = GR.build_parser().parse_args([
            "device", "rename", "192.0.2.10", "--apply"])
        rename_result = {
            "success": True, "returncode": -15, "complete": True,
            "timeout": False, "cli_errors": 0, "prompt_verified": True,
            "stdout": "edge-switch#", "stderr": "", "audit": "/tmp/rename.ses",
        }
        save_result = {
            "success": True, "returncode": -15, "complete": True,
            "timeout": False, "cli_errors": 0, "stdout": "", "stderr": "",
            "audit": "/tmp/save.ses",
        }
        order = []
        with mock.patch.object(GR, "api_session", api_session_for([device()])), \
                mock.patch.object(
                    GR, "command_helper", side_effect=lambda *_args: order.append("backup") or 0), \
                mock.patch.object(
                    GR, "apply_device_rename",
                    side_effect=lambda *_args: order.append("rename") or rename_result), \
                mock.patch.object(
                    GR, "apply_device_save",
                    side_effect=lambda *_args: order.append("save") or save_result):
            self.assertEqual(GR.command_device_rename(configuration(), args), 0)
        self.assertEqual(order, ["backup", "rename", "save"])

    def test_failed_prompt_verification_never_saves(self):
        args = GR.build_parser().parse_args([
            "device", "rename", "192.0.2.10", "--apply"])
        rename_result = {
            "success": False, "returncode": -15, "complete": True,
            "timeout": False, "cli_errors": 0, "prompt_verified": False,
            "stdout": "old-switch#", "stderr": "", "audit": "/tmp/rename.ses",
        }
        with mock.patch.object(GR, "api_session", api_session_for([device()])), \
                mock.patch.object(GR, "command_helper", return_value=0), \
                mock.patch.object(GR, "apply_device_rename", return_value=rename_result), \
                mock.patch.object(GR, "apply_device_save") as save:
            self.assertEqual(GR.command_device_rename(configuration(), args), 2)
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
