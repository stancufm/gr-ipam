#!/usr/bin/env python3
import importlib.machinery
import pathlib
import unittest
from unittest import mock


GR = importlib.machinery.SourceFileLoader("gr_self_update_test_module", "bin/gr").load_module()


class SelfUpdateTests(unittest.TestCase):
    def test_source_version_matches_package_version(self):
        self.assertEqual(GR.GR_VERSION, pathlib.Path("VERSION").read_text(encoding="ascii").strip())

    def test_parser_supports_check_and_release_selection(self):
        parser = GR.build_parser()
        args = parser.parse_args(["self-update", "check", "--version", "v1.2.3", "--dry-run"])
        self.assertEqual(args.command, "self-update")
        self.assertEqual(args.update_action, "check")
        self.assertEqual(args.version, "v1.2.3")
        self.assertTrue(args.dry_run)

    def test_unprivileged_update_uses_sudo_and_installed_helper(self):
        args = GR.build_parser().parse_args(["self-update", "--version", "v1.2.3", "--yes"])
        with mock.patch.object(GR.os.path, "isfile", return_value=True), \
                mock.patch.object(GR.os, "geteuid", return_value=1000), \
                mock.patch.object(GR.shutil, "which", return_value="/usr/bin/sudo"), \
                mock.patch.object(GR.subprocess, "call", return_value=0) as call:
            self.assertEqual(GR.command_self_update(args), 0)
        call.assert_called_once_with([
            "/usr/bin/sudo", GR.SELF_UPDATER, "--tag", "v1.2.3", "--yes"
        ])

    def test_self_update_does_not_require_phpipam_configuration(self):
        with mock.patch.object(GR, "command_self_update", return_value=0) as update, \
                mock.patch.object(GR, "load_config", side_effect=AssertionError("must not load config")):
            self.assertEqual(GR.main(["self-update", "check"]), 0)
        self.assertEqual(update.call_args[0][0].update_action, "check")

    def test_check_does_not_use_sudo(self):
        args = GR.build_parser().parse_args(["self-update", "check"])
        with mock.patch.object(GR.os.path, "isfile", return_value=True), \
                mock.patch.object(GR.os, "geteuid", return_value=1000), \
                mock.patch.object(GR.shutil, "which") as which, \
                mock.patch.object(GR.subprocess, "call", return_value=0) as call:
            self.assertEqual(GR.command_self_update(args), 0)
        which.assert_not_called()
        call.assert_called_once_with([GR.SELF_UPDATER, "check"])


if __name__ == "__main__":
    unittest.main()
