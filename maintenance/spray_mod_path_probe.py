"""Reversible MOD-path experiment using only CSP's self-authored numbered assets."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'experimental/spray_selector'))
from c_session_release import copy_verified, save, sha
from catalog import fixtures
from deploy import GAME, protected, stopped
from kv_audit import parse
from vpk import read

WORK = ROOT / 'reports/spray_selector/mod_path_probe'
JOURNAL = WORK / 'transaction.json'
PACK = ROOT / 'dist/spray_selector_prototype/CSP_Numbered_Selector_TEST.vpk'


def assets():
    report = json.loads((WORK.parent / 'verification.json').read_text(encoding='utf-8'))
    assert report['status'] == 'PHASE_2_TWO_STATIC_ROUNDS_PASS_RUNTIME_PENDING'
    assert sha(PACK) == report['rounds'][0][str(PACK.relative_to(ROOT))]
    content = read(PACK)
    result = {}
    for entry in fixtures().entries:
        for name in (entry.texture, entry.texture[:-4] + '.vmt'):
            result[name] = content[name]
    assert len(result) == 80
    return result


def mod_root(game):
    tree = parse((game / 'left4dead2/gameinfo.txt').read_text(encoding='utf-8'))
    node = tree[0]
    for key in ('FileSystem', 'SearchPaths'):
        node = next(item for item in node.value if item.key.casefold() == key.casefold())
    first = next(item.value for item in node.value if item.key.casefold() == 'game')
    # This experiment is pinned to the inspected local search-path order.
    assert first == 'update', 'Recheck MOD mapping after gameinfo changes'
    target = game / first
    assert target.is_dir() and target.resolve().is_relative_to(game.resolve())
    return target


def target(base, name):
    assert name in {entry.texture for entry in fixtures().entries} | {
        entry.texture[:-4] + '.vmt' for entry in fixtures().entries}
    path = base / name
    assert path.resolve().is_relative_to(base.resolve())
    for parent in (path, *path.parents):
        assert not parent.is_symlink(), 'Linked deployment path needs separate review'
        if parent == base:
            break
    return path


def plan(game, payload):
    base = mod_root(game)
    files = {}
    for name, data in payload.items():
        path = target(base, name)
        assert not path.exists(), f'Preserve existing file: {path}'
        files[name] = dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
    guards = protected(game)
    for relative in ('bin/engine.dll', 'bin/neko/plugins/CSPSelector.dll',
                     'left4dead2/addons/CSP_Numbered_Selector_TEST.vpk',
                     'left4dead2/cfg/config.cfg'):
        path = game / relative
        if path.exists():
            guards[str(path)] = sha(path)
    return dict(game=str(game.resolve()), mod_root=str(base.resolve()), files=files,
                guards=guards, gameinfo_sha256=sha(game / 'left4dead2/gameinfo.txt'))


def check_guards(journal):
    assert all(sha(Path(path)) == digest for path, digest in journal['guards'].items())


def deploy(game, payload, work):
    journal_path = work / 'transaction.json'
    assert not journal_path.exists(), 'Existing probe transaction: verify or rollback first'
    journal = plan(game, payload)
    journal.update(id=uuid.uuid4().hex, status='PREPARED')
    # Preserve the exact source bytes and manifest before any game-directory write.
    for name, data in payload.items():
        source = work / 'payload' / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(data)
        assert sha(source) == journal['files'][name]['sha256']
    save(journal_path, journal)
    base = Path(journal['mod_root'])
    for name, row in journal['files'].items():
        path = target(base, name)
        assert not path.exists(), 'Target appeared after preflight'
        path.parent.mkdir(parents=True, exist_ok=True)
        copy_verified(work / 'payload' / name, path, row['sha256'])
    check_guards(journal)
    journal['status'] = 'INSTALLED_RUNTIME_PENDING'
    save(journal_path, journal)
    verify(journal)
    return journal


def verify(journal):
    base = Path(journal['mod_root'])
    for name, row in journal['files'].items():
        assert sha(target(base, name)) == row['sha256']
    print(f"PASS {len(journal['files'])} numbered MOD-path files; hashes match")


def rollback(journal, work, preview=False):
    base = Path(journal['mod_root'])
    assert base == mod_root(Path(journal['game'])).resolve()
    actions = []
    for name, row in journal['files'].items():
        path = target(base, name)
        if not path.exists():  # Also permits recovery after a partial installation.
            continue
        assert sha(path) == row['sha256'], f'Externally changed file: {path}'
        disabled = path.with_name(path.name + '.' + journal['id'] + '.disabled')
        assert not disabled.exists()
        actions.append((path, disabled, row['sha256']))
    print('ROLLBACK ROOT', base)
    print('ROLLBACK ACTION', len(actions), 'owned files renamed to transaction-specific .disabled; no deletion')
    if preview:
        return
    for path, disabled, digest in actions:
        path.rename(disabled)
        assert not path.exists() and sha(disabled) == digest
    journal['status'] = 'ROLLED_BACK'
    save(work / 'transaction.json', journal)
    print('PASS probe rollback; native spray resources were never overwritten')


def self_test(payload):
    WORK.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='fixture_', dir=WORK) as folder:
        root = Path(folder)
        game, work = root / 'game', root / 'record'
        (game / 'update').mkdir(parents=True)
        (game / 'left4dead2').mkdir()
        (game / 'left4dead2/gameinfo.txt').write_text(
            '"GameInfo" { "FileSystem" { "SearchPaths" { "Game" "update" } } }', encoding='utf-8')
        journal = deploy(game, payload, work)
        rollback(journal, work, preview=True)
        path = target(game / 'update', next(iter(payload)))
        original = path.read_bytes()
        path.write_bytes(b'external edit')
        try:
            rollback(journal, work)
        except AssertionError:
            pass
        else:
            raise AssertionError('Rollback overwrote an external edit')
        path.write_bytes(original)
        rollback(journal, work)
        assert all(not target(game / 'update', name).exists() for name in payload)
        path.write_bytes(b'existing file')
        try:
            plan(game, payload)
        except AssertionError:
            pass
        else:
            raise AssertionError('Preflight accepted an existing target')
        try:
            target(game / 'update', '../escape.vtf')
        except AssertionError:
            pass
        else:
            raise AssertionError('Preflight accepted a foreign path')
    print('PASS controlled install/verify/rollback, collision, external-edit and traversal checks')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('self-test', 'preflight', 'deploy', 'verify', 'rollback-preview', 'rollback', 'review'))
    args = parser.parse_args()
    if args.action == 'review':
        records = []
        log = GAME / 'CSPSelector.log'
        if log.exists():
            WORK.mkdir(parents=True, exist_ok=True)
            (WORK / 'runtime_before.log').write_bytes(log.read_bytes())
        for action in ('self-test', 'preflight', 'deploy', 'verify', 'rollback-preview'):
            command = [sys.executable, '-B', '-X', 'utf8', str(Path(__file__).resolve()), action]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
            records.append(dict(command=command, input='none', stdout=result.stdout,
                                stderr=result.stderr, exit_status=result.returncode))
            save(WORK / 'verification.json', dict(
                status='FAILED' if result.returncode else 'IN_PROGRESS', records=records))
            print(action, result.returncode, result.stdout, result.stderr)
            if result.returncode:
                raise SystemExit(result.returncode)
        journal = json.loads(JOURNAL.read_text(encoding='utf-8'))
        check_guards(journal)
        save(WORK / 'verification.json', dict(status='INSTALLED_FILES_VERIFIED_RUNTIME_PENDING',
             records=records, baseline='80 target files absent; originals untouched',
             modified='80 owned numbered VTF/VMT files present with exact source hashes',
             journal=str(JOURNAL), source_sha256=sha(Path(__file__)), protected=journal['guards']))
        print('PASS recorded commands, literal outputs, exit statuses; real spray rendering pending')
        return
    if args.action in ('verify', 'rollback-preview', 'rollback'):
        journal = json.loads(JOURNAL.read_text(encoding='utf-8'))
        assert journal['game'] == str(GAME.resolve())
        if args.action == 'verify':
            verify(journal)
        else:
            if args.action == 'rollback':
                stopped()
            rollback(journal, WORK, preview=args.action == 'rollback-preview')
        return
    payload = assets()
    if args.action == 'self-test':
        self_test(payload)
    elif args.action == 'preflight':
        report = plan(GAME, payload)
        save(WORK / 'preflight.json', report)
        print('TARGET', report['mod_root'] + '/materials/vgui/logos/csp_test')
        print('PASS 80 new owned files; no existing file overwritten; C/plugin/config unchanged')
    else:
        stopped()
        deploy(GAME, payload, WORK)


if __name__ == '__main__':
    main()
