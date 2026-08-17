#!/usr/bin/env python3
import datetime
import json
import os
import tempfile
import unittest
from unittest import mock


from support import load_source


POOLS = load_source(
    "gr_config_collection_pools_test_module", "libexec/config-collection-pools")


class FakeGr:
    class GrError(Exception):
        pass

    @staticmethod
    def normalize_ip(value):
        return value

    @staticmethod
    def custom_value(row, name):
        return row.get("custom_" + name)

    @staticmethod
    def resolve_device_driver(row):
        return row.get("custom_device_driver", "generic")

    @staticmethod
    def phpipam_ssh_metadata(row):
        return {"enabled": row.get("custom_ssh_enabled", False),
                "profile": row.get("custom_ssh_profile", "")}

    @staticmethod
    def device_driver_spec(driver):
        return {"config_commands": ("show running-config",) if driver != "generic" else ()}


def configuration(**overrides):
    value = {
        "state_dir": "~/.local/state/gr/config-collection",
        "scheduler_enabled": False,
        "pools": {"switches": {
            "interval": "24h", "retry_interval": "30m", "workers": 3,
            "hostname_regex": "^sw[0-9]+$",
        }},
    }
    value.update(overrides)
    return {"config_collection": value}


class ConfigCollectionPoolTests(unittest.TestCase):
    def test_configuration_is_normalized_and_unknown_keys_fail_closed(self):
        parsed = POOLS.validate_configuration(configuration())
        self.assertEqual(parsed["pools"]["switches"]["interval"], 86400)
        self.assertEqual(parsed["pools"]["switches"]["retry_interval"], 1800)
        self.assertFalse(parsed["scheduler_enabled"])
        bad = configuration()
        bad["config_collection"]["pools"]["switches"]["command"] = "show run"
        with self.assertRaises(POOLS.PoolError):
            POOLS.validate_configuration(bad)

    def test_interval_and_worker_bounds_are_enforced(self):
        for interval in ("14m", "0h", "forever"):
            bad = configuration()
            bad["config_collection"]["pools"]["switches"]["interval"] = interval
            with self.assertRaises(POOLS.PoolError):
                POOLS.validate_configuration(bad)
        bad = configuration()
        bad["config_collection"]["pools"]["switches"]["workers"] = 13
        with self.assertRaises(POOLS.PoolError):
            POOLS.validate_configuration(bad)

    def test_boolean_and_ip_types_fail_closed(self):
        bad = configuration(scheduler_enabled="false")
        with self.assertRaises(POOLS.PoolError):
            POOLS.validate_configuration(bad)
        bad = configuration(pools={"one": {"interval": "1h", "ips": ["not-an-ip"]}})
        with self.assertRaises(POOLS.PoolError):
            POOLS.validate_configuration(bad)

    def test_pool_requires_a_selector(self):
        bad = configuration(pools={"empty": {"interval": "1h"}})
        with self.assertRaises(POOLS.PoolError):
            POOLS.validate_configuration(bad)

    def test_resolution_uses_phpipam_and_rejects_ineligible_targets(self):
        pool = POOLS.validate_configuration(configuration())["pools"]["switches"]
        rows = [
            {"ip": "192.0.2.10", "hostname": "sw10",
             "custom_device_driver": "cisco-ios", "custom_ssh_enabled": True,
             "custom_ssh_profile": "network"},
            {"ip": "192.0.2.11", "hostname": "sw11",
             "custom_device_driver": "generic", "custom_ssh_enabled": True,
             "custom_ssh_profile": "network"},
            {"ip": "192.0.2.20", "hostname": "server20",
             "custom_device_driver": "cisco-ios", "custom_ssh_enabled": True,
             "custom_ssh_profile": "network"},
        ]
        selected, rejected = POOLS.resolve_pool(FakeGr, rows, pool)
        self.assertEqual([item["ip"] for item in selected], ["192.0.2.10"])
        self.assertEqual(rejected[0]["reasons"], ["generic-driver"])

    def test_explicit_missing_ip_is_rejected(self):
        cfg = configuration(pools={"one": {"interval": "1h", "ips": ["192.0.2.99"]}})
        pool = POOLS.validate_configuration(cfg)["pools"]["one"]
        selected, rejected = POOLS.resolve_pool(FakeGr, [], pool)
        self.assertEqual(selected, [])
        self.assertEqual(rejected[0]["reasons"], ["not-in-phpipam"])

    def test_due_state_uses_interval_after_success_and_retry_after_failure(self):
        pool = POOLS.validate_configuration(configuration())["pools"]["switches"]
        now = datetime.datetime(2026, 8, 16, 12, 0, 0)
        due, reason, next_due = POOLS.due_status(pool, {
            "last_status": "success", "last_success": "2026-08-16T00:00:00Z"}, now)
        self.assertFalse(due)
        self.assertEqual(reason, "waiting")
        self.assertEqual(next_due, datetime.datetime(2026, 8, 17, 0, 0, 0))
        due, _reason, next_due = POOLS.due_status(pool, {
            "last_status": "failed", "last_attempt": "2026-08-16T11:00:00Z"}, now)
        self.assertTrue(due)
        self.assertEqual(next_due, datetime.datetime(2026, 8, 16, 11, 30, 0))

    def test_overnight_maintenance_window_includes_following_day(self):
        window = POOLS.validate_window(
            {"days": ["mon"], "start": "22:00", "end": "06:00"}, "window")
        self.assertTrue(POOLS.in_window(window, datetime.datetime(2026, 8, 17, 23, 0)))
        self.assertTrue(POOLS.in_window(window, datetime.datetime(2026, 8, 18, 5, 0)))
        self.assertFalse(POOLS.in_window(window, datetime.datetime(2026, 8, 18, 7, 0)))

    def test_state_is_atomic_and_private(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "state", "state.json")
            POOLS.atomic_json(path, {"version": 1, "pools": {}})
            self.assertEqual(POOLS.read_state(path)["version"], 1)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            self.assertEqual(os.stat(os.path.dirname(path)).st_mode & 0o777, 0o700)

    def test_collector_receives_only_targets_workers_and_config_path(self):
        selected = [{"ip": "192.0.2.10", "hostname": "sw10", "driver": "cisco-ios"}]
        pool = {"workers": 2}
        result = mock.Mock(returncode=0, stdout='SUMMARY={"success": 1}\n', stderr="")
        with mock.patch.object(POOLS.subprocess, "run", return_value=result) as run:
            returncode, summary = POOLS.run_collector("one", pool, selected, "/tmp/gr.json")
        self.assertEqual(returncode, 0)
        self.assertEqual(summary, {"success": 1})
        command = run.call_args[0][0]
        self.assertIn("--ip", command)
        self.assertIn("192.0.2.10", command)
        self.assertIn("--config", command)
        self.assertNotIn("password", " ".join(command).lower())

    def test_disabled_scheduler_exits_without_api_or_state_write(self):
        fake_gr = mock.Mock()
        fake_gr.load_config.return_value = configuration()
        fake_gr.GrError = FakeGr.GrError
        with mock.patch.object(POOLS, "load_module", return_value=fake_gr):
            self.assertEqual(POOLS.main(["--due"]), 0)
        fake_gr.api_session.assert_not_called()


if __name__ == "__main__":
    unittest.main()
