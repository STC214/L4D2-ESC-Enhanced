"""Plan or archive only identified Evolved files; preserve L4N/C and user data.

Archive requires an explicitly confirmed plan hash. No upstream script is run.
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

from c_session_release import stopped
from release_paths import ROOT, C_FILENAME

GAME = Path(r'E:\SteamLibrary\steamapps\common\Left 4 Dead 2')
WORK = ROOT / 'reports/evolved_cleanup'
PLAN = WORK / 'plan.json'
JOURNAL = WORK / 'transaction.json'
SOURCE = ROOT / 'research/workshop_3785109042/unpacked'
TREES = ('Evolved', 'L4d2evomodel', 'evo_professor_physics', 'bin/neko/plugins/evo_professor_physics')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)
    assert json.loads(path.read_text(encoding='utf-8')) == obj


def safe(root, relative):
    assert not Path(relative).is_absolute() and ':' not in relative and '..' not in Path(relative).parts
    target = root / relative
    assert target.resolve().is_relative_to(root.resolve())
    current = target
    while current != root:
        assert not (getattr(current.lstat(), 'st_file_attributes', 0) & 0x400) if current.exists() else not current.is_symlink()
        current = current.parent
    return target


def protected():
    names = ('left4dead2.exe', 'bin/left4neko.dll', 'dxgi.dll', 'd3d9.dll', 'dxvk_d3d9.dll',
             'bin/dxvk_d3d9.dll', 'bin/neko/plugins/CSessionDefaults.dll',
             'left4dead2/neko/config.vdf', 'left4dead2/neko/user_config.vdf',
             'left4dead2/cfg/config.cfg', 'left4dead2/cfg/autoexec.cfg', 'left4dead2/cfg/video.txt',
             'left4dead2/addonlist.txt', 'left4dead2/addons/' + C_FILENAME)
    return {name: sha(safe(GAME, name)) if safe(GAME, name).is_file() else None for name in names}


def plan():
    assert not JOURNAL.exists(), 'Existing cleanup transaction must be reviewed first'
    assert (GAME / 'left4dead2.exe').is_file()
    assert b'L4D2Evolved.EntryPatch.v' not in (GAME / 'left4dead2.exe').read_bytes(), 'EXE entry patch requires its own reviewed restoration'
    selected, directories, skipped = {}, set(), []
    for name in TREES:
        tree = safe(GAME, name)
        if not tree.exists():
            continue
        assert tree.is_dir()
        directories.add(name)
        for directory, dirs, files in os.walk(tree, followlinks=False):
            for leaf in dirs + files:
                path = Path(directory) / leaf
                relative = path.relative_to(GAME).as_posix()
                safe(GAME, relative)
                if path.is_dir():
                    directories.add(relative)
                else:
                    selected[relative] = 'dedicated Evolved data directory; archive including user settings/mods'
    expected = {p.relative_to(SOURCE).as_posix(): sha(p) for p in SOURCE.rglob('*') if p.is_file()}
    core = ('L4D2Evolved.dll', 'L4d2evomodel.dll')
    for prefix in ('', 'bin/', 'bin/neko/plugins/'):
        for module in core:
            expected[prefix + module] = sha(SOURCE / 'bin/neko/plugins' / module)
    package = ROOT / 'research/workshop_3785109042/3785109042.vpk'
    expected['left4dead2/addons/workshop/3785109042.vpk'] = sha(package)
    for name, known in expected.items():
        if any(name == tree or name.startswith(tree + '/') for tree in TREES):
            continue
        path = safe(GAME, name)
        if not path.is_file():
            continue
        if sha(path) != known:
            skipped.append({'path': name, 'reason': 'different bytes; ownership/version needs review'})
            continue
        selected[name] = 'hash matches original Evolved package'
    records = [{'path': name, 'absolute': str(safe(GAME, name)), 'sha256': sha(safe(GAME, name)),
                'bytes': safe(GAME, name).stat().st_size, 'reason': why} for name, why in sorted(selected.items())]
    assert not set(selected) & set(protected())
    total = sum(row['bytes'] for row in records)
    assert shutil.disk_usage(ROOT).free > total + 64 * 1024 * 1024, 'Insufficient archive space'
    data = {'game': str(GAME), 'operation': 'copy to project archive, verify, remove exact game files; remove empty Evolved directories only',
            'records': records, 'directories': sorted(directories, key=lambda s: (-len(Path(s).parts), s)),
            'protected': protected(), 'skipped': skipped, 'bytes': total,
            'archive': str(WORK / 'backup')}
    save(PLAN, data)
    for row in records:
        print('ARCHIVE_FILE ' + row['absolute'])
    for name in TREES:
        if name in directories:
            print('REMOVE_IF_EMPTY ' + str(GAME / name))
    print('FILES', len(records), 'BYTES', total)
    print('BACKUP ' + str(WORK / 'backup'))
    print('SKIPPED ' + json.dumps(skipped, ensure_ascii=False))
    print('PLAN_SHA256 ' + sha(PLAN))


def execute(confirmation):
    assert sha(PLAN) == confirmation, 'Confirmation must identify the printed plan'
    stopped()
    data = json.loads(PLAN.read_text(encoding='utf-8'))
    assert data['game'] == str(GAME) and protected() == data['protected']
    archive = WORK / 'backup'
    for row in data['records']:
        assert sha(safe(GAME, row['path'])) == row['sha256'], 'Changed since plan; regenerate and confirm'
        assert not safe(archive, row['path']).exists(), 'Archive already exists; inspect transaction'
    assert not JOURNAL.exists()
    # Preserve all bytes before removing even one source file.
    for row in data['records']:
        target = safe(archive, row['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(safe(GAME, row['path']), target)
        assert sha(target) == row['sha256']
    journal = {'game': str(GAME), 'state': 'BACKED_UP', 'plan_sha256': confirmation,
               'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'removed': []}
    save(JOURNAL, journal)
    for row in data['records']:
        path = safe(GAME, row['path'])
        assert sha(path) == row['sha256'] and sha(safe(archive, row['path'])) == row['sha256']
        path.unlink()
        assert not path.exists()
        journal['removed'].append(row['path'])
        save(JOURNAL, journal)
    for name in data['directories']:
        path = safe(GAME, name)
        if path.exists():
            path.rmdir()  # Empty only; new/unplanned files stop removal rather than recursive deletion.
    journal['state'] = 'ARCHIVED'
    save(JOURNAL, journal)
    verify()


def verify():
    data = json.loads(PLAN.read_text(encoding='utf-8'))
    assert data['game'] == str(GAME)
    journal = json.loads(JOURNAL.read_text(encoding='utf-8'))
    assert journal['plan_sha256'] == sha(PLAN) and journal['state'] == 'ARCHIVED'
    for row in data['records']:
        assert not safe(GAME, row['path']).exists()
        assert sha(safe(WORK / 'backup', row['path'])) == row['sha256']
    assert protected() == data['protected'], 'Protected files changed'
    messages = ['PASS archived ' + str(len(data['records'])) + ' files; all backup hashes verified',
                'PASS L4N, C, CSessionDefaults, renderers and player configuration unchanged',
                'BACKUP ' + str(WORK / 'backup')]
    for message in messages:
        print(message)
    save(WORK / 'verification.json', {'command': [sys.executable, *sys.argv], 'exit_status': 0,
         'stdout': '\n'.join(messages) + '\n', 'plan_sha256': sha(PLAN), 'transaction_sha256': sha(JOURNAL),
         'files': len(data['records']), 'protected_unchanged': True, 'runtime_status': 'NOT_TESTED'})


def restore(confirmed=False):
    data = json.loads(PLAN.read_text(encoding='utf-8'))
    assert data['game'] == str(GAME) and protected() == data['protected']
    for row in data['records']:
        target = safe(GAME, row['path'])
        assert sha(safe(WORK / 'backup', row['path'])) == row['sha256']
        assert not target.exists() or (target.is_file() and sha(target) == row['sha256']), 'New game file preserved; restoration conflict'
    if not confirmed:
        print('PASS restore preview: backup hashes and destinations verified; no game changes')
        return
    stopped()
    for name in reversed(data['directories']):
        safe(GAME, name).mkdir(parents=True, exist_ok=True)
    for row in data['records']:
        target = safe(GAME, row['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(safe(WORK / 'backup', row['path']), target)
        assert sha(target) == row['sha256']
    journal = json.loads(JOURNAL.read_text(encoding='utf-8'))
    journal['state'] = 'RESTORED'
    save(JOURNAL, journal)
    print('PASS restored Evolved from verified archive')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('plan', 'archive', 'verify', 'restore-preview', 'restore'))
    parser.add_argument('--confirmed-plan-sha256')
    args = parser.parse_args()
    if args.mode == 'plan':
        plan()
    elif args.mode == 'archive':
        execute(args.confirmed_plan_sha256)
    elif args.mode == 'verify':
        verify()
    else:
        restore(args.mode == 'restore')


if __name__ == '__main__':
    main()
