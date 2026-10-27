"""Publish verified C artifacts using the existing Git credential helper.

Credentials are held in memory and sent only to GitHub's API/upload hosts.
Never print or persist credential-helper output. Never replace existing assets.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from release_paths import ROOT, OUTPUT

REPO = "STC214/L4D2-ESC-Enhanced"
TAG = "v1.3.0"
API = "https://api.github.com/repos/" + REPO
NOTES = ROOT / "docs/releases/v1.3.0.md"
ZIP = ROOT / "dist/C_session_release.zip"
SUMS = ROOT / "dist/SHA256SUMS.txt"
REPORT = ROOT / "reports/release_v1.3.0"


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError("Git command failed: " + " ".join(args))
    return result.stdout.strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check():
    evidence = json.loads((ROOT / "reports/c_current_review/verification.json").read_text(encoding="utf-8"))
    assert evidence["status"] == "TWO_CLEAN_STATIC_REGRESSION_ROUNDS" and evidence["clean_rounds"] == 2
    for round_ in evidence["rounds"]:
        assert round_["vpk_sha256"] == sha(OUTPUT)
        assert round_["bundle_sha256"] == sha(ZIP)
        assert all(record["exit_status"] == 0 for record in round_["records"])
    with zipfile.ZipFile(ZIP) as archive:
        assert archive.testzip() is None
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["helper_version"] == "1.3.0"
        for name, digest in manifest["files"].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    assert NOTES.is_file()
    lines = "".join(f"{sha(p)}  {p.name}\n" for p in (ZIP, OUTPUT))
    SUMS.write_text(lines, encoding="utf-8", newline="\n")
    assert SUMS.read_text(encoding="utf-8") == lines
    return [ZIP, OUTPUT, SUMS]


class Github:
    def __init__(self):
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
        result = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                                cwd=ROOT, env=env, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError("GitHub credential helper did not return an existing credential")
        values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        self._token = values.get("password")
        if not self._token:
            raise RuntimeError("No existing GitHub API credential")

    def request(self, url, method="GET", data=None, binary=False, missing=False):
        parsed = urllib.parse.urlparse(url)
        assert parsed.scheme == "https" and parsed.hostname in ("api.github.com", "uploads.github.com")
        headers = {"Authorization": "Bearer " + self._token,
                   "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2026-03-10",
                   "User-Agent": "L4D2-ESC-Enhanced-release"}
        if data is not None:
            headers["Content-Type"] = "application/octet-stream" if binary else "application/json"
            if not binary:
                data = json.dumps(data, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=240) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and missing:
                return None
            # GitHub's message only, never request headers or credentials.
            try:
                message = json.loads(exc.read()).get("message", "API request failed")
            except (ValueError, AttributeError):
                message = "API request failed"
            raise RuntimeError(f"GitHub HTTP {exc.code}: {message}") from None


def release_for_tag(api):
    rows = api.request(API + "/releases?per_page=100")
    return next((r for r in rows if r["tag_name"] == TAG), None)


def asset_name(path):
    # GitHub strips Chinese/full-width characters from uploaded filenames.
    # The install ZIP keeps the original fixed VPK name inside the archive.
    return "C_ESC_LED_Health_Speed_TUMTaRA.vpk" if path == OUTPUT else path.name


def verify_assets(release, paths):
    by_name = {a["name"]: a for a in release["assets"]}
    assert set(by_name) == {asset_name(p) for p in paths}, "Unexpected/missing release assets"
    for path in paths:
        asset = by_name[asset_name(path)]
        assert asset["state"] == "uploaded" and asset["size"] == path.stat().st_size
        assert asset.get("digest") == "sha256:" + sha(path), "Remote asset SHA256 mismatch: " + path.name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "preflight", "publish", "verify"))
    action = parser.parse_args().action
    paths = check()
    if action == "check":
        print("PASS verified VPK/ZIP; SHA256SUMS generated")
        return
    api = Github()
    repo = api.request(API)
    assert repo["full_name"].lower() == REPO.lower() and repo.get("permissions", {}).get("push")
    release = release_for_tag(api)
    if action == "preflight":
        assert release is None, "Version already has a release; inspect before continuing"
        assert api.request(API + "/git/ref/tags/" + TAG, missing=True) is None, "Tag already exists"
        print("PASS GitHub authenticated push permission; release/tag available: " + TAG)
        return
    commit = git("rev-parse", TAG + "^{commit}")
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        assert git("hash-object", "--", relative) == git("rev-parse", TAG + ":" + relative), "Artifact differs from tagged release"
    ref = api.request(API + "/git/ref/tags/" + TAG)["object"]
    if ref["type"] == "tag":
        ref = api.request(API + "/git/tags/" + ref["sha"])["object"]
    assert ref["type"] == "commit" and ref["sha"] == commit, "Remote tag/source mismatch"
    if action == "publish":
        assert not git("status", "--porcelain"), "Commit release sources/artifacts first"
        if release is None:
            release = api.request(API + "/releases", "POST", {
                "tag_name": TAG, "target_commitish": commit,
                "name": "C v1.3.0 — 轮廓默认项、原生开关与手电着色器整合",
                "body": NOTES.read_text(encoding="utf-8"), "draft": True, "prerelease": True})
            print("DRAFT created", flush=True)
        upload = release["upload_url"].split("{", 1)[0]
        assets = {a["name"]: a for a in release["assets"]}
        for path in paths:
            name = asset_name(path)
            if name not in assets and release["draft"]:
                matches = [a for a in assets.values() if a.get("digest") == "sha256:" + sha(path)]
                if len(matches) == 1:
                    original = matches[0]
                    renamed = api.request(API + "/releases/assets/" + str(original["id"]), "PATCH",
                                          {"name": name, "label": path.name})
                    del assets[original["name"]]
                    assets[renamed["name"]] = renamed
                    print("RENAMED " + name, flush=True)
            if name in assets:
                assert assets[name].get("digest") == "sha256:" + sha(path), "Existing asset differs; no overwrite"
                continue
            assert release["draft"], "Do not append to an already published release"
            print("UPLOAD " + path.name, flush=True)
            asset = api.request(upload + "?" + urllib.parse.urlencode({"name": name, "label": path.name}),
                                "POST", path.read_bytes(), binary=True)
            assert asset["name"] == name and asset.get("digest") == "sha256:" + sha(path)
        release = api.request(API + "/releases/" + str(release["id"]))
        verify_assets(release, paths)
        if release["draft"]:
            api.request(API + "/releases/" + str(release["id"]), "PATCH",
                        {"draft": False, "prerelease": True, "body": NOTES.read_text(encoding="utf-8")})
    assert release is not None
    release = api.request(API + "/releases/" + str(release["id"]))
    assert not release["draft"]
    verify_assets(release, paths)
    report = {"tag": TAG, "commit": commit, "url": release["html_url"],
              "prerelease": release["prerelease"], "assets": [
                  {k: a[k] for k in ("name", "size", "digest", "browser_download_url")}
                  for a in release["assets"]]}
    REPORT.mkdir(parents=True, exist_ok=True)
    target = REPORT / "published.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert json.loads(target.read_text(encoding="utf-8")) == report
    print("PASS published release; all three remote asset SHA256/size checks passed")
    print(release["html_url"])


if __name__ == "__main__":
    main()
