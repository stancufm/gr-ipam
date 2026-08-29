#!/usr/bin/env python3
import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest

from support import load_source


GR = load_source("gr_archive_test_module", "bin/gr")
COLLECTOR = load_source("gr_config_collector_test_module", "libexec/collect-config")


class ConfigurationArchiveTests(unittest.TestCase):
    def test_failure_reason_classifies_ssh_negotiation_without_raw_stderr(self):
        item = {"result": "failed", "returncode": 255, "configuration": "",
                "stderr": "Unable to negotiate: no matching key exchange method found"}
        self.assertEqual(COLLECTOR.failure_reason(item), "ssh-key-exchange")
        item["stderr"] = "Permission denied, please try again."
        self.assertEqual(COLLECTOR.failure_reason(item), "ssh-authentication")
        item.update({"result": "timeout", "stderr": "configuration command timed out"})
        self.assertEqual(COLLECTOR.failure_reason(item), "timeout")

    def test_normalization_removes_command_echo_prompt_and_ansi(self):
        raw = ("banner\r\nSw1#show running-config\r\n\x1b[2Jversion 1\r\n"
               "hostname Sw1\r\n!\r\nSw1#\r\n")
        self.assertEqual(COLLECTOR.normalize_configuration(raw, "show running-config"),
                         "version 1\nhostname Sw1\n!\n")

    def test_git_archive_commits_only_changed_content(self):
        with tempfile.TemporaryDirectory() as archive:
            item = {"hostname": "sw1", "ip": "192.0.2.1", "result": "success",
                    "configuration": "hostname sw1\n",
                    "collected_at": "2026-08-10T10:00:00Z"}
            commit, changed = COLLECTOR.archive_configurations(archive, [item], "20260810T100000Z")
            self.assertTrue(commit)
            self.assertEqual(changed, 1)
            second = dict(item)
            second["collected_at"] = "2026-08-10T11:00:00Z"
            commit2, changed2 = COLLECTOR.archive_configurations(
                archive, [second], "20260810T110000Z")
            self.assertEqual(commit2, "")
            self.assertEqual(changed2, 0)
            self.assertEqual(second["archive_status"], "unchanged")
            self.assertEqual(subprocess.check_output(
                ["git", "--git-dir=" + os.path.join(archive, ".git"),
                 "--work-tree=" + archive, "config", "user.name"],
                universal_newlines=True).strip(), "gr configuration collector")
            self.assertEqual(subprocess.check_output(
                ["git", "--git-dir=" + os.path.join(archive, ".git"),
                 "--work-tree=" + archive, "config", "core.sharedRepository"],
                universal_newlines=True).strip(), "group")
            self.assertEqual(subprocess.check_output(
                ["git", "--git-dir=" + os.path.join(archive, ".git"),
                 "--work-tree=" + archive, "status", "--porcelain"],
                universal_newlines=True), "")
            self.assertTrue(os.path.isfile(os.path.join(
                archive, ".git", "gr-collect.lock")))
            state_path = os.path.join(
                archive, ".git", "gr-collection-state.json")
            with open(state_path, encoding="utf-8") as handle:
                state = json.load(handle)
            self.assertEqual(
                state["devices"]["192.0.2.1"]["last_success"],
                "2026-08-10T11:00:00Z")
            self.assertEqual(
                state["devices"]["192.0.2.1"]["last_status"], "success")
            failed = {
                "hostname": "sw1", "ip": "192.0.2.1", "result": "failed",
                "returncode": 255, "stderr": "Permission denied",
                "configuration": "", "collected_at": "2026-08-10T12:00:00Z",
            }
            COLLECTOR.archive_configurations(archive, [failed], "20260810T120000Z")
            with open(state_path, encoding="utf-8") as handle:
                state = json.load(handle)
            device = state["devices"]["192.0.2.1"]
            self.assertEqual(device["last_attempt"], "2026-08-10T12:00:00Z")
            self.assertEqual(device["last_success"], "2026-08-10T11:00:00Z")
            self.assertEqual(device["last_status"], "failed")
            self.assertEqual(device["last_error"], "ssh-authentication")

    def test_archive_browsing_lists_history_and_latest(self):
        with tempfile.TemporaryDirectory() as archive:
            item = {"hostname": "sw1", "ip": "192.0.2.1", "result": "success",
                    "configuration": "hostname sw1\n",
                    "collected_at": "2026-08-10T10:00:00Z"}
            COLLECTOR.archive_configurations(archive, [item], "20260810T100000Z")
            old_archive = GR.GLOBAL_CONFIG_ARCHIVE
            GR.GLOBAL_CONFIG_ARCHIVE = archive
            try:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    GR.command_config_devices()
                self.assertIn("sw1", output.getvalue())
                self.assertIn("LAST EXTRACTED", output.getvalue())
                self.assertIn("LAST CHANGED", output.getvalue())
                self.assertIn("2026-08-10 13:00:00", output.getvalue())
                self.assertIn("success", output.getvalue())
                shown = io.StringIO()
                with contextlib.redirect_stdout(shown):
                    GR.command_config_view("192.0.2.1", use_pager=False)
                self.assertIn("hostname sw1", shown.getvalue())
            finally:
                GR.GLOBAL_CONFIG_ARCHIVE = old_archive

    def test_archive_recovers_staged_files_after_interrupted_commit(self):
        with tempfile.TemporaryDirectory() as archive:
            COLLECTOR.git_call(archive, ["init", "--quiet"])
            COLLECTOR.git_call(archive, ["config", "user.name", "collector"])
            COLLECTOR.git_call(archive, ["config", "user.email", "gr@localhost"])
            devices = os.path.join(archive, "devices")
            os.makedirs(devices)
            target = os.path.join(devices, "sw1--192.0.2.1.cfg")
            with open(target, "w", encoding="utf-8") as handle:
                handle.write("hostname sw1\n")
            COLLECTOR.git_call(archive, ["add", "--", "devices/sw1--192.0.2.1.cfg"])
            item = {"hostname": "sw1", "ip": "192.0.2.1", "result": "success",
                    "configuration": "hostname sw1\n"}
            commit, changed = COLLECTOR.archive_configurations(archive, [item], "recovery")
            self.assertTrue(commit)
            self.assertEqual(changed, 1)

    def test_parser_accepts_collection_and_archive_navigation(self):
        parser = GR.build_parser()
        self.assertTrue(parser.parse_args(["collect", "config", "--all"]).all)
        self.assertEqual(parser.parse_args([
            "collect", "config", "--ip", "192.0.2.1", "--driver", "cisco-ios"]).driver,
            "cisco-ios")
        args = parser.parse_args(["config", "view", "sw1", "latest", "--no-more"])
        self.assertEqual(args.config_values, ["sw1", "latest"])
        self.assertTrue(args.no_more)


if __name__ == "__main__":
    unittest.main()
