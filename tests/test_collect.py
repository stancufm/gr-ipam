#!/usr/bin/env python3
import importlib.machinery
import unittest

GR = importlib.machinery.SourceFileLoader("gr_collect_test_module", "bin/gr").load_module()


class CollectVersionCliTests(unittest.TestCase):
    def test_all_uses_documented_defaults(self):
        args = GR.build_parser().parse_args(["collect", "version", "--all"])
        self.assertTrue(args.all)
        self.assertEqual(args.vendor, "cisco")
        self.assertEqual(args.workers, 4)

    def test_ip_is_repeatable_and_accepts_overrides(self):
        args = GR.build_parser().parse_args([
            "collect", "version", "--ip", "192.0.2.10", "--ip", "192.0.2.11",
            "--vendor", "cisco", "--workers", "8",
        ])
        self.assertEqual(args.ips, ["192.0.2.10", "192.0.2.11"])
        self.assertEqual(args.vendor, "cisco")
        self.assertEqual(args.workers, 8)


if __name__ == "__main__":
    unittest.main()
