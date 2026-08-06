#!/usr/bin/env python3
import base64
import importlib.machinery
import ipaddress
import json
import os
import tempfile
import unittest

GR = importlib.machinery.SourceFileLoader("gr_test_module", "bin/gr").load_module()


class AuditTests(unittest.TestCase):
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

    def test_cli_audit_overrides(self):
        parser = GR.build_parser()
        self.assertIs(parser.parse_args(["find", "switch", "--ssh", "--audit"]).audit, True)
        self.assertIs(parser.parse_args(["find", "switch", "--ssh", "--no-audit"]).audit, False)
        self.assertEqual(parser.parse_args(["audit", "show", "x.ses"]).audit_action, "show")


if __name__ == "__main__":
    unittest.main()
