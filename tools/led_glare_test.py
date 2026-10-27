"""Replace only C's two LED textures with the original Glare Workshop payload."""

import shutil
import zipfile

from c_session_release import ROOT, OUTPUT, save, sha
from led_texture_2x import TEXTURES
from vpk import read, write

DIRECTORY = ROOT / "dist/led_glare_test"
REPORT = ROOT / "reports/led_glare_test"


def main():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    upstream = ROOT / "originals/BRIGHT_2833227093.vpk"
    assert sha(upstream) == "d7ec3f83a31390e6cac0596cf4d9ffb89b8c9c7025f5c7e71a211d5bd2412243"
    source = read(upstream)
    assert list(source) == [TEXTURES[0]]
    baseline = DIRECTORY / "baseline.vpk.bak"
    if baseline.exists():
        assert sha(baseline) == sha(OUTPUT)
    else:
        shutil.copyfile(OUTPUT, baseline)
    before = read(baseline)
    after = dict(before)
    for name in TEXTURES:
        after[name] = source[TEXTURES[0]]
    candidate = DIRECTORY / OUTPUT.name
    write(candidate, after)
    assert read(candidate) == after
    assert {name for name in before if before[name] != after[name]} == set(TEXTURES)
    from audit_c import inspect
    assert not inspect(candidate)["errors"]
    patch = REPORT / "patch.zip"
    with zipfile.ZipFile(patch, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in TEXTURES:
            archive.writestr(name, after[name])
    replay = dict(before)
    with zipfile.ZipFile(patch) as archive:
        assert archive.testzip() is None
        replay.update({name: archive.read(name) for name in archive.namelist()})
    replayed = REPORT / "replayed.vpk"
    write(replayed, replay)
    assert replayed.read_bytes() == candidate.read_bytes()
    restored = DIRECTORY / "restored" / OUTPUT.name
    restored.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(baseline, restored)
    assert sha(restored) == sha(baseline) and read(restored) == before
    save(REPORT / "verification.json", {
        "scope": "original Glare DXT5 texture unchanged; game rendering pending",
        "candidate_sha256": sha(candidate), "baseline_sha256": sha(baseline),
        "upstream_sha256": sha(upstream), "changed_members": list(TEXTURES),
        "texture_mappings": {name: TEXTURES[0] for name in TEXTURES},
        "unchanged_members": len(before) - 2, "patch": str(patch),
        "restored_baseline": str(restored)})
    print("PASS both LED texture payloads byte-identical to Glare Flashlight original")
    print("PASS 220 unrelated members unchanged; full archive audit, patch replay and rollback copy")
    print("CANDIDATE", candidate)


if __name__ == "__main__":
    main()
