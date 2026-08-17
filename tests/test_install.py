#!/usr/bin/env python3
import os
import json
import subprocess
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALLER = os.path.join(ROOT, "install.sh")


class InstallDependencyTests(unittest.TestCase):
    def test_destdir_install_skips_host_dependency_policy(self):
        with tempfile.TemporaryDirectory() as root:
            result = subprocess.run(
                ["sh", INSTALLER, "--destdir", root,
                 "--base-url", "https://inventory.example.net", "--username", "api-test"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(os.path.isfile(os.path.join(root, "usr/local/bin/gr")))
            self.assertTrue(os.path.isfile(os.path.join(
                root, "usr/local/libexec/gr/collect-config")))
            self.assertTrue(os.path.isfile(os.path.join(
                root, "usr/local/libexec/gr/config-collection-pools")))
            self.assertTrue(os.path.isfile(os.path.join(
                root, "usr/local/libexec/gr/snmp-manager")))
            self.assertTrue(os.path.isfile(os.path.join(
                root, "usr/local/libexec/gr/snmp-handlers")))
            self.assertTrue(os.path.isfile(os.path.join(
                root, "etc/gr/snmp-templates.json")))
            self.assertTrue(os.path.isfile(os.path.join(
                root, "etc/systemd/system/gr-config-collect.service")))
            self.assertTrue(os.path.isfile(os.path.join(
                root, "etc/systemd/system/gr-config-collect.timer")))
            self.assertTrue(os.path.isfile(os.path.join(
                root, "etc/systemd/system/gr-config-collect@.service")))
            self.assertTrue(os.path.isfile(os.path.join(root, "etc/gr/collector.json")))
            with open(os.path.join(root, "etc/gr/collector.json"), encoding="utf-8") as handle:
                collector = json.load(handle)
            self.assertEqual(collector["base_url"], "https://inventory.example.net")
            self.assertEqual(collector["config_collection"]["state_dir"],
                             "/var/lib/gr-collector/config-collection")
            self.assertFalse(collector["config_collection"]["scheduler_enabled"])
            with open(os.path.join(
                    root, "etc/systemd/system/gr-config-collect.service"),
                    encoding="utf-8") as handle:
                service = handle.read()
            self.assertIn("User=gr-collector", service)
            self.assertIn("Group=gr-collector", service)
            self.assertIn("SupplementaryGroups=gr-config", service)
            self.assertIn("--config /etc/gr/collector.json", service)

    def test_prepared_collector_config_is_installed_verbatim(self):
        with tempfile.TemporaryDirectory() as root:
            prepared = os.path.join(root, "prepared.json")
            content = '{"marker": "dedicated-collector"}\n'
            with open(prepared, "w", encoding="utf-8") as handle:
                handle.write(content)
            destination = os.path.join(root, "stage")
            result = subprocess.run(
                ["sh", INSTALLER, "--destdir", destination,
                 "--base-url", "https://inventory.example.net", "--username", "api-test",
                 "--collector-config", prepared],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with open(os.path.join(destination, "etc/gr/collector.json"),
                      encoding="utf-8") as handle:
                self.assertEqual(handle.read(), content)

    def test_missing_packages_abort_before_installation(self):
        with tempfile.TemporaryDirectory() as root:
            fake_bin = os.path.join(root, "bin")
            os.mkdir(fake_bin)
            for name, body in {
                    "id": "#!/bin/sh\necho 0\n",
                    "dpkg-query": "#!/bin/sh\nexit 1\n",
            }.items():
                path = os.path.join(fake_bin, name)
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(body)
                os.chmod(path, 0o755)
            environment = os.environ.copy()
            environment["PATH"] = fake_bin + os.pathsep + environment["PATH"]
            result = subprocess.run(
                ["sh", INSTALLER, "--base-url", "https://ipam.example.net",
                 "--username", "api-test"], env=environment,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("Missing required Debian packages:", result.stderr)
            self.assertIn("bash-completion", result.stderr)
            self.assertIn("snmp", result.stderr)
            self.assertIn("--install-dependencies", result.stderr)


if __name__ == "__main__":
    unittest.main()
