"""Offline release guards: stale sources, wrong helper, and artifact drift."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import publish_github_release as publish


class ReleaseGuards(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="c-release-guard-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.paths = {"ROOT": root, "OUTPUT": root / "C.vpk", "ZIP": root / "release.zip",
                      "SUMS": root / "SHA256SUMS.txt", "NOTES": root / "notes.md"}
        for name, value in self.paths.items():
            item = patch.object(publish, name, value)
            item.start()
            self.addCleanup(item.stop)
        publish.OUTPUT.write_bytes(b"fixture VPK")
        publish.NOTES.write_text("fixture notes", encoding="utf-8")
        self.helper = b"fixture helper"
        self.archive()
        self.evidence = {"status": "TWO_CLEAN_STATIC_REGRESSION_ROUNDS", "clean_rounds": 2,
                         "source_hashes": {"fixture.py": "reviewed"}, "rounds": [
             {"vpk_sha256": publish.sha(publish.OUTPUT), "bundle_sha256": publish.sha(publish.ZIP),
              "helper_sha256": hashlib.sha256(self.helper).hexdigest(), "records": [{"exit_status": 0}]}
             for _ in range(2)]}
        self.record = root / "reports/c_current_review/verification.json"
        self.record.parent.mkdir(parents=True)
        self.save()
        item = patch("review_c_menu_consolidation.sources", return_value={"fixture.py": "reviewed"})
        item.start()
        self.addCleanup(item.stop)

    def archive(self, version="1.3.1"):
        name = "bin/neko/plugins/CSessionDefaults.dll"
        with zipfile.ZipFile(publish.ZIP, "w") as archive:
            archive.writestr(name, self.helper)
            archive.writestr("manifest.json", json.dumps({"helper_version": version,
                "files": {name: hashlib.sha256(self.helper).hexdigest()}}))

    def save(self):
        self.record.write_text(json.dumps(self.evidence), encoding="utf-8")

    def test_reviewed_artifacts_generate_exact_sums(self):
        self.assertEqual(publish.check(), [publish.ZIP, publish.OUTPUT, publish.SUMS])
        self.assertIn(publish.sha(publish.ZIP), publish.SUMS.read_text(encoding="utf-8"))

    def test_source_edit_after_review_rejected(self):
        self.evidence["source_hashes"]["fixture.py"] = "old version"
        self.save()
        with self.assertRaisesRegex(AssertionError, "Sources changed"):
            publish.check()

    def test_wrong_helper_digest_rejected(self):
        self.evidence["rounds"][0]["helper_sha256"] = "wrong"
        self.save()
        with self.assertRaises(AssertionError):
            publish.check()

    def test_old_helper_version_rejected(self):
        self.archive("1.3.0")
        for round_ in self.evidence["rounds"]:
            round_["bundle_sha256"] = publish.sha(publish.ZIP)
        self.save()
        with self.assertRaises(AssertionError):
            publish.check()

    def test_vpk_changed_after_review_rejected(self):
        publish.OUTPUT.write_bytes(b"external edit")
        with self.assertRaises(AssertionError):
            publish.check()


if __name__ == "__main__":
    unittest.main(verbosity=2)
