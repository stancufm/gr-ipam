#!/usr/bin/env python3
import argparse
import ipaddress
import os
import re
import tempfile
import unittest
from unittest import mock

from support import load_source


VALIDATE = load_source("gr_validate_ssh_test_module", "libexec/validate-ssh")


class FakeGr:
    DEVICE_DRIVERS = ("generic", "cisco-ios", "fortigate-fortios")
    DEVICE_CLI_ERROR_RE = re.compile(r"% Invalid input")
    SPECS = {
        "generic": {"vendor": "", "interactive_cli": False,
                    "validation_commands": ()},
        "cisco-ios": {"vendor": "cisco", "interactive_cli": False,
                      "validation_commands": ("show version",)},
        "fortigate-fortios": {"vendor": "fortinet", "interactive_cli": True,
                              "validation_commands": ("get system status",),
                              "cleanup_commands": ("exit",)},
    }

    @staticmethod
    def normalize_ip(value):
        try:
            return ipaddress.ip_address(str(value))
        except ValueError:
            return None

    @staticmethod
    def phpipam_ssh_metadata(row):
        return {"enabled": row.get("ssh_enabled", True),
                "user": row.get("ssh_user", "admin"),
                "port": row.get("ssh_port", "22"),
                "profile": row.get("ssh_profile", "network"),
                "jump": row.get("ssh_jump", ""),
                "client": row.get("ssh_client", "normal")}

    @staticmethod
    def custom_value(row, name):
        return row.get("custom_" + name)

    @classmethod
    def resolve_device_driver(cls, row):
        value = row.get("custom_device_driver", "generic")
        if value not in cls.SPECS:
            raise ValueError("unsupported driver")
        return value

    @classmethod
    def device_driver_spec(cls, driver):
        return cls.SPECS[driver]

    @staticmethod
    def vault_secret_name(_cfg, profile):
        return "gr/" + profile if profile else ""

    @staticmethod
    def vault_secret_exists(_secret):
        return True

    @staticmethod
    def expand(value):
        return value

    @staticmethod
    def ssh_connection_options(_client):
        return []

    @staticmethod
    def device_login_driver(_driver):
        return object

    @staticmethod
    def run_interactive_device(*_args, **_kwargs):
        return 0, "FortiGate status", "", False, True


def args(**overrides):
    value = {"ips": None, "ip_range": None, "subnet": None,
             "pool": None, "all": False}
    value.update(overrides)
    return argparse.Namespace(**value)


def row(ip, hostname="device", driver="cisco-ios", vendor="cisco", **overrides):
    value = {"id": ip, "ip": ip, "hostname": hostname,
             "custom_device_driver": driver, "custom_device_vendor": vendor}
    value.update(overrides)
    return value


class ValidateSshTests(unittest.TestCase):
    def test_explicit_ip_selector_reports_missing_targets(self):
        rows = [row("192.0.2.10"), row("192.0.2.11")]
        selected, missing, label = VALIDATE.select_rows(
            FakeGr, {}, rows, args(ips=["192.0.2.10", "192.0.2.99"]))
        self.assertEqual([item["ip"] for item in selected], ["192.0.2.10"])
        self.assertEqual(missing, ["192.0.2.99"])
        self.assertEqual(label, "ip:192.0.2.10,192.0.2.99")

    def test_range_and_subnet_selectors_are_inclusive(self):
        rows = [row("192.0.2.9"), row("192.0.2.10"), row("192.0.2.12"),
                row("192.0.2.13")]
        selected, _missing, _label = VALIDATE.select_rows(
            FakeGr, {}, rows,
            args(ip_range=VALIDATE.parse_ip_range("192.0.2.10-192.0.2.12")))
        self.assertEqual([item["ip"] for item in selected],
                         ["192.0.2.10", "192.0.2.12"])
        selected, _missing, _label = VALIDATE.select_rows(
            FakeGr, {}, rows, args(subnet=VALIDATE.parse_subnet("192.0.2.8/30")))
        self.assertEqual([item["ip"] for item in selected],
                         ["192.0.2.9", "192.0.2.10"])

    def test_pool_selector_reuses_pool_matching(self):
        class Pools:
            @staticmethod
            def validate_configuration(_cfg, allowed_drivers=None):
                self.assertIn("cisco-ios", allowed_drivers)
                return {"pools": {"edge": {"driver": "cisco-ios"}}}

            @staticmethod
            def matches_pool(_gr, candidate, pool):
                return candidate["custom_device_driver"] == pool["driver"]

        rows = [row("192.0.2.10"),
                row("192.0.2.11", driver="fortigate-fortios", vendor="fortinet")]
        selected, missing, label = VALIDATE.select_rows(
            FakeGr, {}, rows, args(pool="edge"), pool_manager=Pools)
        self.assertEqual([item["ip"] for item in selected], ["192.0.2.10"])
        self.assertEqual(missing, [])
        self.assertEqual(label, "pool:edge")

    def test_driver_selects_command_and_vendor_mismatch_fails_closed(self):
        cfg = {"ssh_profiles": {"network": {"password_secret": "gr/network"}}}
        item = VALIDATE.prepare_item(FakeGr, cfg, row("192.0.2.10"))
        self.assertEqual(item["result"], "ready")
        self.assertEqual(item["validation_commands"], ["show version"])
        self.assertEqual(item["driver"], "cisco-ios")
        mismatch = VALIDATE.prepare_item(
            FakeGr, cfg, row("192.0.2.11", vendor="fortinet"))
        self.assertEqual(mismatch["result"], "vendor_driver_mismatch")

    def test_missing_driver_and_vendor_are_not_connected(self):
        cfg = {"ssh_profiles": {"network": {"password_secret": "gr/network"}}}
        missing_driver = VALIDATE.prepare_item(
            FakeGr, cfg, row("192.0.2.10", driver="generic", vendor=""))
        self.assertEqual(missing_driver["result"], "driver_missing")
        missing_vendor = VALIDATE.prepare_item(
            FakeGr, cfg, row("192.0.2.11", vendor=""))
        self.assertEqual(missing_vendor["result"], "vendor_missing")

    def test_selector_is_required_and_exclusive(self):
        with self.assertRaises(SystemExit):
            VALIDATE.build_parser().parse_args([])
        with self.assertRaises(SystemExit):
            VALIDATE.build_parser().parse_args(["--all", "--ip", "192.0.2.1"])

    def test_key_profile_is_supported_without_vault(self):
        with tempfile.NamedTemporaryFile() as key:
            cfg = {"ssh_profiles": {"network": {"identity_file": key.name}}}
            fake = mock.Mock(wraps=FakeGr)
            fake.vault_secret_name.return_value = ""
            item = VALIDATE.prepare_item(fake, cfg, row("192.0.2.10"))
            self.assertEqual(item["result"], "ready")
            self.assertEqual(item["auth_mode"], "key")

    @mock.patch.object(VALIDATE.shutil, "which", return_value="/usr/bin/ssh")
    @mock.patch.object(VALIDATE.subprocess, "run")
    def test_noninteractive_validation_runs_driver_command(self, run, _which):
        run.return_value = mock.Mock(returncode=0, stdout="Cisco IOS", stderr="")
        item = VALIDATE.prepare_item(
            FakeGr, {"ssh_profiles": {"network": {"identity_file": __file__}}},
            row("192.0.2.10"))
        result = VALIDATE.validate_one(FakeGr, item, {}, tempfile.gettempdir())
        command = run.call_args.args[0]
        self.assertEqual(command[-1], "show version")
        self.assertEqual(result["result"], "success")

    @mock.patch.object(VALIDATE, "build_ssh_command",
                       return_value=["ssh", "host", "placeholder"])
    def test_interactive_validation_runs_full_driver_sequence(self, _build):
        fake = mock.Mock(wraps=FakeGr)
        fake.run_interactive_device.return_value = (0, "FortiGate status", "", False, True)
        item = VALIDATE.prepare_item(
            fake, {"ssh_profiles": {"network": {"identity_file": __file__}}},
            row("192.0.2.20", driver="fortigate-fortios", vendor="fortinet"))
        result = VALIDATE.validate_one(fake, item, {}, tempfile.gettempdir())
        call = fake.run_interactive_device.call_args
        self.assertEqual(call.args[5], ["get system status"])
        self.assertEqual(call.args[6], ("exit",))
        self.assertEqual(result["result"], "success")


if __name__ == "__main__":
    unittest.main()
