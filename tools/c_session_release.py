"""Package/deploy the C session pair with hash-guarded, reversible file writes."""

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid
import zipfile

from c_session_policy import BASE, BASE_HASH, CFG, MENU, validate
from release_paths import ROOT, OUTPUT, C_FILENAME
from vpk import read
from inspect_menu import blocks

GAME = Path(r'E:\SteamLibrary\steamapps\common\Left 4 Dead 2')
DLL = ROOT / 'dist/c_session_helper/CSessionDefaults.dll'
WORK = ROOT / 'reports/c_session_deploy'
JOURNAL = WORK / 'transaction.json'
BUNDLE = ROOT / 'dist/C_session_release.zip'
TARGETS = {'vpk': Path('left4dead2/addons') / C_FILENAME,
           'helper': Path('bin/neko/plugins/CSessionDefaults.dll')}
SOURCES = {'vpk': OUTPUT, 'helper': DLL}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.c-session.tmp', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            stream.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        assert json.loads(temporary.read_text(encoding='utf-8')) == data
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    assert json.loads(path.read_text(encoding='utf-8')) == data


def safe_target(key):
    target = GAME / TARGETS[key]
    assert target.resolve().is_relative_to(GAME.resolve()), 'Target escapes game directory'
    assert not target.is_symlink(), 'Linked target needs separate review'
    assert target.parent.is_dir(), 'Target directory is missing'
    return target


def snapshot(target):
    return sha(target) if target.exists() else None


def copy_verified(source, target, expected):
    # Same-directory staging makes replacement atomic on the destination volume.
    # Only our private temporary file is cleaned up; active files are never deleted.
    with tempfile.NamedTemporaryFile(dir=target.parent, suffix='.c-session.tmp', delete=False) as stream:
        temporary = Path(stream.name)
    try:
        shutil.copyfile(source, temporary)
        assert sha(temporary) == expected, 'Staged copy hash mismatch'
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    assert sha(target) == expected


def load_journal():
    journal = json.loads(JOURNAL.read_text(encoding='utf-8'))
    assert journal['game'] == str(GAME)
    assert set(journal['files']) == set(TARGETS)
    for key, entry in journal['files'].items():
        assert entry['relative'] == TARGETS[key].as_posix()
        backup = ROOT / entry['backup']
        assert backup.resolve().is_relative_to(WORK.resolve())
        safe_target(key)
    return journal


def stopped():
    command = ['tasklist', '/FI', 'IMAGENAME eq left4dead2.exe', '/FO', 'CSV', '/NH']
    result = subprocess.run(command, capture_output=True, text=True, errors='replace', check=True)
    rows = list(csv.reader(io.StringIO(result.stdout)))
    assert not any(row and row[0].lower() == 'left4dead2.exe' for row in rows), 'Exit L4D2 before file deployment'


def package():
    validate(read(OUTPUT))
    build = json.loads((ROOT / 'reports/c_session_plugin_build.json').read_text(encoding='utf-8'))
    assert sha(DLL) == build['dll_sha256']
    manifest = {'runtime_status': 'NOT_TESTED', 'requires': 'existing L4N plugin loader; x86 pinned engine profile',
                'engine_sha256': build['engine_profile_sha256'],
                'files': {TARGETS[k].as_posix(): sha(p) for k, p in SOURCES.items()}}
    with zipfile.ZipFile(BUNDLE, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        payload = {TARGETS[k].as_posix(): p.read_bytes() for k, p in SOURCES.items()}
        payload['manifest.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        for name, data in sorted(payload.items()):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data)
    with zipfile.ZipFile(BUNDLE) as archive:
        assert archive.testzip() is None
        assert json.loads(archive.read('manifest.json')) == manifest
        for key, path in SOURCES.items():
            assert archive.read(TARGETS[key].as_posix()) == path.read_bytes()
    print('PASS release pair reopened/CRC/hash checked: ' + str(BUNDLE))


def baseline():
    assert sha(BASE) == BASE_HASH
    files = read(BASE)
    assert sum(name.startswith('Init_') for name, _, _, _ in blocks(files[MENU].decode('utf-8-sig'))) == 12
    assert b'\nr_flashlightfov 200\n' in files[CFG]
    print('BASELINE: 12 ESC fixed-range default writers; shared flashlight default 200')
    print('BASE SHA256 ' + BASE_HASH)


def rollback_copy():
    baseline()
    target = ROOT / 'dist/rollback_before_session_defaults' / C_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        assert sha(target) == BASE_HASH
    shutil.copyfile(BASE, target)
    assert sha(target) == BASE_HASH and read(target) == read(BASE)
    print('PASS rollback copy restored/reopened: ' + str(target))
    print('Current C and game files were not touched')


def verify_installed():
    journal = load_journal()
    assert journal['status'] == 'FILES_VERIFIED_RUNTIME_PENDING'
    for key, relative in TARGETS.items():
        assert sha(GAME / relative) == journal['files'][key]['after_sha256'] == sha(SOURCES[key])
    assert sha(GAME / 'bin/engine.dll') == journal['engine_sha256']
    print('PASS installed C and helper byte-identical to release; runtime pending')


def deploy():
    stopped()
    package()
    engine_hash = json.loads((ROOT / 'reports/c_session_plugin_build.json').read_text(encoding='utf-8'))['engine_profile_sha256']
    assert sha(GAME / 'bin/engine.dll') == engine_hash
    assert (GAME / 'bin/left4neko.dll').is_file(), 'Existing L4N deployment required; Evolved is optional'
    source_hashes = {k: sha(p) for k, p in SOURCES.items()}
    previous = load_journal() if JOURNAL.exists() else None
    if previous:
        assert previous['status'] in ('FILES_VERIFIED_RUNTIME_PENDING', 'ROLLED_BACK'), 'Finish pending rollback before another deployment'
        state = 'after_sha256' if previous['status'] == 'FILES_VERIFIED_RUNTIME_PENDING' else 'before_sha256'
        for key, entry in previous['files'].items():
            assert snapshot(safe_target(key)) == entry[state], 'Installed file changed since transaction'
        if state == 'after_sha256' and all(previous['files'][k][state] == v for k, v in source_hashes.items()):
            verify_installed()
            return
    # Validate every destination before backups, journals or game writes.
    targets = {k: safe_target(k) for k in TARGETS}
    before_hashes = {k: snapshot(p) for k, p in targets.items()}
    if not previous:
        assert before_hashes['vpk'] == BASE_HASH, 'Installed C differs from confirmed task baseline'
        assert before_hashes['helper'] is None, 'Unknown existing helper needs review'
    generation = uuid.uuid4().hex
    directory = WORK / 'transactions' / generation
    journal = {'game': str(GAME), 'engine_sha256': engine_hash, 'status': 'PREPARED',
               'generation': generation, 'files': {}}
    if previous:
        save(directory / 'previous.json', previous)
        journal['previous_transaction'] = str((directory / 'previous.json').relative_to(ROOT))
    for key, relative in TARGETS.items():
        target = targets[key]
        exists = before_hashes[key] is not None
        backup = directory / ('before_' + key + target.suffix)
        assert not backup.exists(), 'Existing backup needs review'
        if exists:
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(target, backup)
            assert sha(target) == sha(backup) == before_hashes[key]
        journal['files'][key] = {'relative': relative.as_posix(), 'existed': exists,
                                  'before_sha256': before_hashes[key],
                                  'backup': str(backup.relative_to(ROOT)),
                                  'after_sha256': source_hashes[key],
                                  'disabled_relative': relative.as_posix() + '.' + generation + '.disabled'}
        print('TARGET ' + str(target.resolve()))
    save(JOURNAL, journal)
    for key, relative in TARGETS.items():
        target = safe_target(key)
        assert snapshot(target) == before_hashes[key], 'Destination changed during staging'
        copy_verified(SOURCES[key], target, source_hashes[key])
    journal['status'] = 'FILES_VERIFIED_RUNTIME_PENDING'
    save(JOURNAL, journal)
    verify_installed()


def rollback_game(apply=False):
    journal = load_journal()
    assert journal['status'] in ('PREPARED', 'FILES_VERIFIED_RUNTIME_PENDING', 'ROLLED_BACK')
    # Preflight every file before any change. New helper is disabled by rename,
    # never deleted. Original C is restored from the actual installed backup.
    actions = []
    for key, entry in journal['files'].items():
        target = safe_target(key)
        if entry['existed']:
            assert target.exists() and sha(target) in (entry['before_sha256'], entry['after_sha256'])
            backup = ROOT / entry['backup']
            assert backup.resolve().is_relative_to(WORK.resolve())
            assert sha(backup) == entry['before_sha256']
            actions.append((target, backup))
            print('RESTORE ' + str(target.resolve()) + ' FROM ' + str(backup.resolve()))
        else:
            disabled = GAME / entry.get('disabled_relative', entry['relative'] + '.disabled')
            assert disabled.parent == target.parent and disabled.name.startswith(target.name + '.')
            assert disabled.suffix == '.disabled' and not disabled.is_symlink()
            if not target.exists():
                if disabled.exists():
                    assert sha(disabled) == entry['after_sha256']
                print('NO CHANGE: helper not active at ' + str(target.resolve()))
                continue  # Also handles an interrupted deployment before copy.
            assert sha(target) == entry['after_sha256']
            assert not disabled.exists()
            actions.append((target, disabled))
            print('RENAME ' + str(target.resolve()) + ' TO ' + str(disabled.resolve()))
    if not apply:
        print('PASS rollback preview: backups/installed hashes valid; no game changes')
        return
    stopped()
    for target, backup in actions:
        if backup.suffix != '.disabled':
            copy_verified(backup, target, sha(backup))
        else:
            target.rename(backup)
            assert not target.exists()
    journal['status'] = 'ROLLED_BACK'
    save(JOURNAL, journal)
    print('PASS game rollback; no files deleted')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['baseline', 'package', 'rollback-copy', 'deploy', 'verify-installed', 'rollback-preview', 'rollback-game'])
    action = parser.parse_args().action
    functions = {'baseline': baseline, 'package': package, 'rollback-copy': rollback_copy,
                 'deploy': deploy, 'verify-installed': verify_installed,
                 'rollback-preview': rollback_game, 'rollback-game': lambda: rollback_game(True)}
    functions[action]()


if __name__ == '__main__':
    main()
