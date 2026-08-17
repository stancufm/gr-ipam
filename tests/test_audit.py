#!/usr/bin/env python3
import base64
import contextlib
import io
import ipaddress
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

from support import load_source


GR = load_source("gr_test_module", "bin/gr")


class AuditTests(unittest.TestCase):
    def test_vault_decryption_refreshes_pinentry_tty_for_current_session(self):
        class InteractiveInput:
            @staticmethod
            def isatty():
                return True

            @staticmethod
            def fileno():
                return 9

        def which(name):
            return "/usr/bin/{}".format(name)

        with mock.patch.object(GR.sys, "stdin", InteractiveInput()), \
                mock.patch.object(GR.os, "ttyname", return_value="/dev/pts/42"), \
                mock.patch.object(GR.shutil, "which", side_effect=which), \
                mock.patch.object(GR.subprocess, "call", return_value=0) as agent, \
                mock.patch.object(GR.subprocess, "check_output",
                                  return_value="vault-password\n") as decrypt:
            self.assertEqual(GR.read_vault_password("gr/example"), "vault-password")
        agent.assert_called_once_with(
            ["/usr/bin/gpg-connect-agent", "updatestartuptty", "/bye"],
            env=mock.ANY, stdout=GR.subprocess.DEVNULL, stderr=GR.subprocess.DEVNULL)
        self.assertEqual(decrypt.call_args[1]["env"]["GPG_TTY"], "/dev/pts/42")

    def test_vault_timeout_explains_safe_agent_recovery(self):
        with mock.patch.object(GR.shutil, "which", return_value="/usr/bin/pass"), \
                mock.patch.object(GR.subprocess, "check_output",
                                  side_effect=GR.subprocess.TimeoutExpired(["pass"], 120)):
            with self.assertRaises(GR.GrError) as raised:
                GR.read_vault_password("gr/example")
        self.assertIn("gr vault reset-agent", str(raised.exception))

    def test_reset_agent_is_scoped_and_can_skip_vault_decryption(self):
        calls = []

        def which(name):
            return "/usr/bin/{}".format(name)

        def call(command, **_kwargs):
            calls.append(command)
            return 0

        with mock.patch.object(GR.shutil, "which", side_effect=which), \
                mock.patch.object(GR.subprocess, "call", side_effect=call), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(GR.command_vault({}, "reset-agent"), 0)
        self.assertEqual(calls, [["gpgconf", "--kill", "gpg-agent"]])

    def test_rejected_vault_password_can_retry_without_saving(self):
        callback = mock.Mock(return_value=0)
        stderr = io.StringIO()
        with mock.patch("builtins.input", return_value="y"), \
                contextlib.redirect_stderr(stderr):
            result = GR.retry_rejected_vault_password(
                5, "192.0.2.10", "operator", callback)
        self.assertEqual(result, 0)
        callback.assert_called_once_with()
        self.assertIn("Vault password was rejected", stderr.getvalue())
        self.assertIn("will not be saved", stderr.getvalue())

    def test_rejected_vault_password_stops_for_interactive_driver(self):
        callback = mock.Mock(return_value=0)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = GR.retry_rejected_vault_password(
                5, "192.0.2.10", "switch", callback,
                prompt_retry_supported=False)
        self.assertEqual(result, 5)
        callback.assert_not_called()
        self.assertIn("gr vault test switch", stderr.getvalue())

    def test_ssh_connection_options_bound_stalls_and_accept_only_new_keys(self):
        normal = GR.ssh_connection_options("normal")
        self.assertIn("StrictHostKeyChecking=accept-new", normal)
        self.assertIn("ConnectTimeout=20", normal)
        self.assertIn("ConnectionAttempts=1", normal)
        self.assertIn("ServerAliveInterval=30", normal)
        self.assertIn("ServerAliveCountMax=3", normal)
        self.assertIn("StrictHostKeyChecking=no", GR.ssh_connection_options("legacy"))

    def test_ssh_failure_classification_uses_evidence_before_exit_code(self):
        self.assertEqual(GR.classify_ssh_failure(
            6, b"Permission denied", used_sshpass=True), "authentication-rejected")
        self.assertEqual(GR.classify_ssh_failure(
            6, b"", used_sshpass=True), "sshpass-exit-6-ambiguous")
        self.assertEqual(GR.classify_ssh_failure(
            6, b"", remote_command=True, used_sshpass=True), "remote-command-exit")
        self.assertEqual(GR.classify_ssh_failure(
            255, b"Connection timed out", used_sshpass=True), "timeout")
        self.assertEqual(GR.classify_ssh_failure(
            255, b"REMOTE HOST IDENTIFICATION HAS CHANGED!", used_sshpass=True),
            "host-key-changed")
        self.assertEqual(GR.classify_ssh_failure(
            255, b"Failed to add the host to the list of known hosts", used_sshpass=True),
            "host-key-verification")
        self.assertEqual(GR.classify_ssh_failure(
            255, b"Load key /tmp/id: invalid format", used_sshpass=False),
            "local-identity")
        self.assertEqual(GR.classify_ssh_failure(
            255, b"No supported authentication methods available", used_sshpass=False),
            "authentication-unavailable")
        self.assertEqual(GR.classify_ssh_failure(
            255, b"channel 0: open failed: administratively prohibited", used_sshpass=False),
            "policy-rejected")
        self.assertEqual(GR.classify_ssh_failure(
            255, b"Over maximum CLI session", used_sshpass=False),
            "resource-exhausted")

    def test_ambiguous_exit_six_does_not_blame_vault_password(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            category = GR.report_ssh_failure(
                6, "192.0.2.10", "operator", "/tmp/gr-known-hosts",
                used_sshpass=True)
        self.assertEqual(category, "sshpass-exit-6-ambiguous")
        message = stderr.getvalue()
        self.assertIn("SSH_DIAGNOSTIC", message)
        self.assertIn("Status 6 alone is ambiguous", message)
        self.assertIn("password is not classified as rejected", message)

    def test_no_vault_session_stays_in_relay_and_reports_failure(self):
        with tempfile.TemporaryDirectory() as root:
            cfg = {
                "ssh_known_hosts": os.path.join(root, "known_hosts"),
                "ssh_audit_dir": os.path.join(root, "audit"),
                "ssh_audit_enabled": False,
                "ssh_legacy_fallback": True,
                "ssh_profiles": {},
            }
            row = {
                "_hostname": "server",
                "_ip": ipaddress.ip_address("192.0.2.10"),
                "custom_fields": {
                    "ssh_enabled": "1", "ssh_user": "operator", "ssh_port": "22",
                    "ssh_profile": "", "ssh_client": "normal",
                    "device_driver": "generic",
                },
            }

            def failed_relay(_command, diagnostics=None, **_kwargs):
                diagnostics["stderr"] = b"Connection refused"
                return 255

            stderr = io.StringIO()
            with mock.patch.object(GR.shutil, "which", return_value="/usr/bin/ssh"), \
                    mock.patch.object(GR, "run_pty_ssh", side_effect=failed_relay) as relay, \
                    mock.patch.object(GR.os, "execvp") as execvp, \
                    contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(stderr):
                result = GR.connect_ssh(cfg, row, no_vault=True, audit=False)
            self.assertEqual(result, 255)
            relay.assert_called_once()
            execvp.assert_not_called()
            self.assertIn("category=connection-refused", stderr.getvalue())

    def test_interactive_cli_stdout_is_used_as_diagnostic_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            cfg = {
                "ssh_known_hosts": os.path.join(root, "known_hosts"),
                "ssh_audit_dir": os.path.join(root, "audit"),
                "ssh_audit_enabled": False,
                "ssh_legacy_fallback": True,
                "ssh_profiles": {},
            }
            row = {
                "_hostname": "switch", "_ip": ipaddress.ip_address("192.0.2.10"),
                "custom_fields": {
                    "ssh_enabled": "1", "ssh_user": "operator", "ssh_port": "22",
                    "ssh_profile": "", "ssh_client": "normal",
                    "device_driver": "generic",
                },
            }

            def failed_relay(_command, diagnostics=None, **_kwargs):
                diagnostics["stdout"] = b"Over maximum CLI session"
                return 255

            stderr = io.StringIO()
            with mock.patch.object(GR.shutil, "which", return_value="/usr/bin/ssh"), \
                    mock.patch.object(GR, "run_pty_ssh", side_effect=failed_relay), \
                    contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(stderr):
                result = GR.connect_ssh(cfg, row, no_vault=True, audit=False)
            self.assertEqual(result, 255)
            self.assertIn("category=resource-exhausted", stderr.getvalue())

    def test_cisco_small_business_login_handles_fragmented_prompts(self):
        driver = GR.CiscoSmallBusinessLogin("cisco", "vault-secret")
        self.assertEqual(driver.feed(b"Welcome\r\nUser Na"), [])
        self.assertEqual(driver.feed(b"me: "), [("credential", b"cisco\n")])
        self.assertEqual(driver.feed(b"Pass"), [])
        self.assertEqual(driver.feed(b"word: "), [("credential", b"vault-secret\n")])
        self.assertEqual(driver.feed(b"\r\nsw36#"), [("ready", b"")])
        self.assertEqual(driver.state, "ready")
        self.assertEqual(driver.feed(b"show version\r\noutput\r\nsw36#"), [("prompt", b"")])

    def test_cisco_small_business_login_accepts_direct_cli_prompt(self):
        driver = GR.CiscoSmallBusinessLogin("cisco", "vault-secret")
        self.assertEqual(driver.feed(b"\r\n\r\nSw-25#"), [("ready", b"")])
        self.assertEqual(driver.state, "ready")
        self.assertEqual(driver.feed(b"show version\r\noutput\r\nSw-25#"), [("prompt", b"")])

    def test_lossless_records_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as root:
            row = {"_hostname": "switch/example", "_ip": ipaddress.ip_address("192.0.2.10")}
            audit = GR.SshSessionAudit({"ssh_audit_dir": root}, row, ["ssh", "192.0.2.10"])
            audit.record("stdin", b"secret\x00\n")
            audit.record("stdout", b"output\xff")
            audit.record("stderr", b"warning\r\n")
            path = audit.path
            audit.close(23)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            self.assertEqual(os.stat(os.path.dirname(path)).st_mode & 0o777, 0o700)
            with open(path, encoding="ascii") as handle:
                records = [json.loads(line) for line in handle]
            self.assertEqual(records[0]["format"], "gr-ssh-session-v1")
            frames = records[1:-1]
            self.assertEqual([frame["stream"] for frame in frames], ["stdin", "stdout", "stderr"])
            self.assertEqual([base64.b64decode(frame["data"]) for frame in frames],
                             [b"secret\x00\n", b"output\xff", b"warning\r\n"])
            self.assertEqual(records[-1]["exit_status"], 23)

            class BinaryCapture:
                def __init__(self):
                    self.buffer = io.BytesIO()

                def isatty(self):
                    return False

            old_stdout, old_stderr = sys.stdout, sys.stderr
            stdout, stderr = BinaryCapture(), BinaryCapture()
            try:
                sys.stdout, sys.stderr = stdout, stderr
                GR.command_audit_replay(path, GR.audit_replay_streams())
            finally:
                sys.stdout, sys.stderr = old_stdout, old_stderr
            self.assertEqual(stdout.buffer.getvalue(), b"output\xff")
            self.assertEqual(stderr.buffer.getvalue(), b"warning\r\n")

            stdout, stderr = BinaryCapture(), BinaryCapture()
            try:
                sys.stdout, sys.stderr = stdout, stderr
                GR.command_audit_replay(path, GR.audit_replay_streams(include_stdin=True))
            finally:
                sys.stdout, sys.stderr = old_stdout, old_stderr
            self.assertEqual(stdout.buffer.getvalue(), b"secret\x00\noutput\xff")

    def test_empty_rejected_session_has_actionable_replay(self):
        with tempfile.TemporaryDirectory() as root:
            audit = GR.SshSessionAudit(
                {"ssh_audit_dir": root},
                {"_hostname": "server", "_ip": ipaddress.ip_address("192.0.2.10")},
                ["sshpass", "-d", "4", "ssh", "192.0.2.10"])
            path = audit.path
            audit.close(5)

            class BinaryCapture:
                def __init__(self):
                    self.buffer = io.BytesIO()

                def isatty(self):
                    return False

            old_stdout, old_stderr = sys.stdout, sys.stderr
            stdout, stderr = BinaryCapture(), BinaryCapture()
            try:
                sys.stdout, sys.stderr = stdout, stderr
                GR.command_audit_replay(path, GR.audit_replay_streams())
            finally:
                sys.stdout, sys.stderr = old_stdout, old_stderr
            self.assertEqual(stdout.buffer.getvalue(), b"")
            self.assertIn(b"sshpass exit 5", stderr.buffer.getvalue())
            self.assertIn(b"Vault profile", stderr.buffer.getvalue())

    def test_empty_exit_six_session_has_nonmisleading_replay(self):
        with tempfile.TemporaryDirectory() as root:
            audit = GR.SshSessionAudit(
                {"ssh_audit_dir": root},
                {"_hostname": "server", "_ip": ipaddress.ip_address("192.0.2.10")},
                ["sshpass", "-d", "4", "ssh", "192.0.2.10"])
            path = audit.path
            audit.close(6)

            class BinaryCapture:
                def __init__(self):
                    self.buffer = io.BytesIO()

                def isatty(self):
                    return False

            old_stdout, old_stderr = sys.stdout, sys.stderr
            stdout, stderr = BinaryCapture(), BinaryCapture()
            try:
                sys.stdout, sys.stderr = stdout, stderr
                GR.command_audit_replay(path, GR.audit_replay_streams())
            finally:
                sys.stdout, sys.stderr = old_stdout, old_stderr
            self.assertEqual(stdout.buffer.getvalue(), b"")
            self.assertIn(b"exit status 6", stderr.buffer.getvalue())
            self.assertIn(b"ambiguous", stderr.buffer.getvalue())
            self.assertIn(b"not classified as rejected", stderr.buffer.getvalue())

    def test_cli_audit_overrides(self):
        parser = GR.build_parser()
        self.assertIs(parser.parse_args(["find", "switch", "--ssh", "--audit"]).audit, True)
        self.assertIs(parser.parse_args(["find", "switch", "--ssh", "--no-audit"]).audit, False)
        direct = parser.parse_args(["audit", "show", "x.ses"])
        self.assertEqual(direct.audit_action, "show")
        self.assertEqual(direct.target, "x.ses")
        browse = parser.parse_args(["audit", "show", "sw50", "latest"])
        self.assertEqual((browse.target, browse.session), ("sw50", "latest"))
        self.assertEqual(GR.audit_replay_streams(), {"stdout", "stderr"})
        self.assertEqual(GR.audit_replay_streams(include_stdin=True),
                         {"stdin", "stdout", "stderr"})
        self.assertEqual(GR.audit_replay_streams(stream="stdin"), {"stdin"})
        stream = parser.parse_args(["audit", "show", "sw50", "latest", "--stream", "stderr"])
        self.assertEqual(stream.stream, "stderr")
        direct = parser.parse_args(["audit", "show", "sw50", "latest", "--no-more"])
        self.assertTrue(direct.no_more)

    def test_audit_browse_by_hostname_and_ip(self):
        with tempfile.TemporaryDirectory() as root:
            cfg = {"ssh_audit_dir": root}
            first = GR.SshSessionAudit(
                cfg, {"_hostname": "sw50", "_ip": ipaddress.ip_address("192.0.2.50")},
                ["ssh", "192.0.2.50"])
            first.close(0)
            second = GR.SshSessionAudit(
                cfg, {"_hostname": "sw50", "_ip": ipaddress.ip_address("192.0.2.50")},
                ["ssh", "192.0.2.50"])
            second.close(5)

            by_hostname = GR.resolve_audit_sessions(cfg, "sw50")
            by_ip = GR.resolve_audit_sessions(cfg, "192.0.2.50")
            self.assertEqual(len(by_hostname), 2)
            self.assertEqual({item["path"] for item in by_hostname},
                             {item["path"] for item in by_ip})

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                GR.command_audit_show(cfg)
            self.assertIn("sw50", output.getvalue())
            self.assertIn("192.0.2.50", output.getvalue())

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                GR.command_audit_show(cfg, "sw50")
            self.assertIn("SESSION", output.getvalue())
            self.assertIn("latest", output.getvalue())

    def test_completion_candidates_follow_audit_filter(self):
        with tempfile.TemporaryDirectory() as root:
            cfg = {"ssh_audit_dir": root, "ssh_profiles": {"cisco": {}, "local": {}}}
            audit = GR.SshSessionAudit(
                cfg, {"_hostname": "sw11", "_ip": ipaddress.ip_address("192.0.2.11")},
                ["ssh", "192.0.2.11"])
            audit.close(0)

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                GR.command_completion(cfg, "audit-targets")
            self.assertEqual(set(output.getvalue().splitlines()), {"sw11", "192.0.2.11"})

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                GR.command_completion(cfg, "audit-sessions", "sw11")
            values = output.getvalue().splitlines()
            self.assertEqual(values[0], "latest")
            self.assertEqual(values[1], GR.audit_session_summary(audit.path)["session"])


if __name__ == "__main__":
    unittest.main()
