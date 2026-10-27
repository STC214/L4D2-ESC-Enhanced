"""Integration deployment fault tests; isolated fixtures, never real game files."""

import argparse
import json
import unittest
from unittest.mock import patch

import deploy_c_integrated as integration
import test_c_session_deploy as fixtures
import c_session_release as release


class IntegratedTests(unittest.TestCase):
    target = fixtures.DeploymentTests.target
    journal = fixtures.DeploymentTests.journal

    def setUp(self):
        fixtures.DeploymentTests.setUp(self)
        release.deploy()
        self.pair_before = {key: self.target(key).read_bytes() for key in release.TARGETS}
        self.sources["vpk"].write_bytes(b"integrated C")
        self.sources["helper"].write_bytes(b"integrated helper")
        self.test = self.game / integration.TEST_REL
        self.test.write_bytes(b"verified standalone shader")
        report = self.root / "reports/flashlight_gain2x_test/deployment.json"
        release.save(report, {"status": "DEPLOYED_RUNTIME_PENDING", "target": str(self.test),
                              "after_sha256": release.sha(self.test)})
        for name, value in (("WORK", self.work / "integrated"), ("JOURNAL", self.work / "integrated/current.json")):
            item = patch.object(integration, name, value)
            item.start()
            self.addCleanup(item.stop)

    def assert_previous(self):
        for key, data in self.pair_before.items():
            self.assertEqual(self.target(key).read_bytes(), data)
        self.assertEqual(self.test.read_bytes(), b"verified standalone shader")

    def test_install_and_full_three_file_rollback(self):
        integration.deploy()
        integration.verify()
        self.assertFalse(self.test.exists())
        integration.restore(integration.load(), apply=False)
        integration.restore(integration.load(), apply=True)
        self.assert_previous()

    def test_idempotent_install_preserves_backups(self):
        integration.deploy()
        before = integration.JOURNAL.read_bytes()
        integration.deploy()
        self.assertEqual(integration.JOURNAL.read_bytes(), before)

    def test_unknown_standalone_blocks_before_any_write(self):
        self.test.write_bytes(b"external standalone edit")
        before = release.JOURNAL.read_bytes()
        with self.assertRaises(AssertionError):
            integration.deploy()
        self.assertEqual(release.JOURNAL.read_bytes(), before)
        self.assertEqual(self.target("vpk").read_bytes(), self.pair_before["vpk"])

    def test_second_copy_failure_restores_all(self):
        original = release.copy_verified
        failed = False
        def copy(source, target, digest):
            nonlocal failed
            if target == self.target("helper") and not failed:
                failed = True
                raise OSError("injected helper copy failure")
            original(source, target, digest)
        with patch.object(release, "copy_verified", side_effect=copy), self.assertRaises(OSError):
            integration.deploy()
        self.assert_previous()
        self.assertEqual(integration.load()["status"], "ROLLED_BACK")

    def test_failure_after_test_archival_restores_all(self):
        with patch.object(integration, "verify", side_effect=RuntimeError("injected final check")), self.assertRaises(RuntimeError):
            integration.deploy()
        self.assert_previous()

    def test_external_edit_blocks_rollback(self):
        integration.deploy()
        self.target("vpk").write_bytes(b"external edit")
        with self.assertRaises(AssertionError):
            integration.restore(integration.load(), apply=True)
        self.assertEqual(self.target("vpk").read_bytes(), b"external edit")

    def test_reinstall_after_rollback(self):
        integration.deploy()
        old_generation = integration.load()["generation"]
        integration.restore(integration.load(), apply=True)
        integration.deploy()
        self.assertNotEqual(integration.load()["generation"], old_generation)
        integration.verify()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report")
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IntegratedTests))
    if args.report:
        release.save(fixtures.Path(args.report), {"tests": result.testsRun, "failures": len(result.failures),
                                                 "errors": len(result.errors), "scope": "isolated fixtures only"})
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
