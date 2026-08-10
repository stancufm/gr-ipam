#!/usr/bin/env python3
import os
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
                 "--base-url", "https://ipam.example.net", "--username", "api-test"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(os.path.isfile(os.path.join(root, "usr/local/bin/gr")))

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
            self.assertIn("--install-dependencies", result.stderr)


if __name__ == "__main__":
    unittest.main()
