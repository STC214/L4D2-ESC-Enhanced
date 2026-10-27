"""Deploy integrated C pair and retire the exact recorded standalone shader test.

Back up all three artifacts before writes. On failure restore the complete
previous state. The ordinary pair journal remains usable by existing tooling;
use this wrapper's rollback to restore the standalone test as well.
"""

import argparse
import json
import shutil
import uuid

import c_session_release as r

WORK = r.WORK / "integrated"
JOURNAL = WORK / "current.json"
TEST_REL = "left4dead2/addons/C_flashlight_nofade_TEST.vpk"


def targets():
    result = {key: r.safe_target(key) for key in r.TARGETS}
    result["test"] = r.GAME / TEST_REL
    assert result["test"].resolve().is_relative_to(r.GAME.resolve())
    assert not result["test"].is_symlink()
    return result


def load():
    data = json.loads(JOURNAL.read_text(encoding="utf-8"))
    assert data["game"] == str(r.GAME)
    for key, target in targets().items():
        assert data["files"][key]["target"] == str(target)
        backup = r.ROOT / data["files"][key]["backup"]
        assert backup.resolve().is_relative_to(WORK.resolve()) and not backup.is_symlink()
        if data["files"][key]["before"] is not None:
            assert r.sha(backup) == data["files"][key]["before"]
    return data


def verify():
    data = load()
    assert data["status"] == "DEPLOYED_RUNTIME_PENDING"
    r.verify_installed()
    assert not targets()["test"].exists()
    disabled = r.GAME / data["disabled_test_relative"]
    if data["files"]["test"]["before"] is not None:
        assert r.sha(disabled) == data["files"]["test"]["before"]
    print("PASS integrated C pair installed; standalone shader test archived, no duplicate override")


def restore(data, apply=False):
    paths = targets()
    disabled = r.GAME / data["disabled_test_relative"]
    assert disabled.parent == paths["test"].parent and disabled.name.startswith(paths["test"].name + ".")
    assert disabled.suffix == ".disabled" and not disabled.is_symlink()
    for key, target in paths.items():
        entry = data["files"][key]
        allowed = (entry["before"], entry["after"])
        assert r.snapshot(target) in allowed
        if key == "test" and disabled.exists():
            assert r.sha(disabled) == entry["before"] and not target.exists()
        print("RESTORE", target.resolve(), "FROM", r.ROOT / entry["backup"])
    if not apply:
        print("PASS all three rollback roles preflighted; no game changes")
        return
    r.stopped()
    for key, target in paths.items():
        entry = data["files"][key]
        if key == "test" and disabled.exists():
            disabled.rename(target)
        elif entry["before"] is not None:
            r.copy_verified(r.ROOT / entry["backup"], target, entry["before"])
        assert r.snapshot(target) == entry["before"]
    pair = r.load_journal()
    assert pair["generation"] == data["generation"]
    pair["status"] = "ROLLED_BACK"
    r.save(r.JOURNAL, pair)
    data["status"] = "ROLLED_BACK"
    r.save(JOURNAL, data)
    print("PASS integrated rollback restored prior C, helper and standalone-test state")


def deploy():
    r.stopped()
    r.package()
    if JOURNAL.exists():
        old = load()
        if old["status"] == "DEPLOYED_RUNTIME_PENDING":
            verify()
            return
        assert old["status"] == "ROLLED_BACK", "Complete pending rollback first"
    paths = targets()
    previous = r.load_journal()
    assert previous["status"] in ("FILES_VERIFIED_RUNTIME_PENDING", "ROLLED_BACK")
    state = "after_sha256" if previous["status"] == "FILES_VERIFIED_RUNTIME_PENDING" else "before_sha256"
    observed = {k: r.snapshot(p) for k, p in paths.items()}
    if not all(observed[k] == previous["files"][k][state] for k in r.TARGETS):
        trial = json.loads((r.ROOT / "reports/led_mean190_test/deployment.json").read_text(encoding="utf-8"))
        assert trial["status"] == "DEPLOYED_RUNTIME_PENDING" and trial["target"] == str(paths["vpk"])
        assert observed["vpk"] == trial["after_sha256"]
        assert observed["helper"] == trial["helper_sha256"] == previous["files"]["helper"][state]
    if observed["test"] is not None:
        test = json.loads((r.ROOT / "reports/flashlight_gain2x_test/deployment.json").read_text(encoding="utf-8"))
        assert test["status"] == "DEPLOYED_RUNTIME_PENDING" and test["target"] == str(paths["test"])
        assert observed["test"] == test["after_sha256"]
    build = json.loads((r.ROOT / "reports/c_session_plugin_build.json").read_text(encoding="utf-8"))
    assert r.sha(r.GAME / "bin/engine.dll") == build["engine_profile_sha256"]
    assert (r.GAME / "bin/left4neko.dll").is_file()
    generation = uuid.uuid4().hex
    directory = WORK / generation
    disabled_rel = TEST_REL + "." + generation + ".disabled"
    assert not (r.GAME / disabled_rel).exists()
    data = {"game": str(r.GAME), "generation": generation, "status": "PREPARED",
            "disabled_test_relative": disabled_rel, "files": {}}
    pair = {"game": str(r.GAME), "generation": generation, "status": "PREPARED",
            "engine_sha256": build["engine_profile_sha256"], "files": {},
            "previous_transaction": str((directory / "previous_pair.json").relative_to(r.ROOT))}
    r.save(directory / "previous_pair.json", previous)
    for key, target in paths.items():
        backup = directory / ("before_" + key + ".bak")
        if observed[key] is not None:
            shutil.copyfile(target, backup)
            assert r.sha(backup) == observed[key]
        after = r.sha(r.SOURCES[key]) if key in r.SOURCES else None
        data["files"][key] = {"target": str(target), "backup": str(backup.relative_to(r.ROOT)),
                               "before": observed[key], "after": after}
        if key in r.TARGETS:
            pair["files"][key] = {"relative": r.TARGETS[key].as_posix(), "existed": observed[key] is not None,
                                  "before_sha256": observed[key], "after_sha256": after,
                                  "backup": str(backup.relative_to(r.ROOT)),
                                  "disabled_relative": r.TARGETS[key].as_posix() + "." + generation + ".disabled"}
    r.save(JOURNAL, data)
    r.save(r.JOURNAL, pair)
    try:
        for key in r.TARGETS:
            assert r.snapshot(paths[key]) == observed[key]
            print("TARGET", paths[key].resolve())
            r.copy_verified(r.SOURCES[key], paths[key], data["files"][key]["after"])
        if observed["test"] is not None:
            assert r.sha(paths["test"]) == observed["test"]
            print("ARCHIVE", paths["test"].resolve(), "TO", (r.GAME / disabled_rel).resolve())
            paths["test"].rename(r.GAME / disabled_rel)
        pair["status"] = "FILES_VERIFIED_RUNTIME_PENDING"
        r.save(r.JOURNAL, pair)
        data["status"] = "DEPLOYED_RUNTIME_PENDING"
        r.save(JOURNAL, data)
        verify()
    except BaseException:
        restore(data, apply=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("deploy", "verify", "rollback-preview", "rollback"))
    action = parser.parse_args().action
    if action == "deploy":
        deploy()
    elif action == "verify":
        verify()
    else:
        restore(load(), apply=action == "rollback")


if __name__ == "__main__":
    main()
