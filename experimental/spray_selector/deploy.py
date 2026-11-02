"""Hash-guarded CSP test deployment; index-only conflict scan, reversible files."""

import argparse
import csv
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from c_session_release import copy_verified, save, sha
from kv_audit import parse, tokenize
from vpk import read
from build_selector import VPK, DLL, ZIP, validate

GAME = Path(r'E:\SteamLibrary\steamapps\common\Left 4 Dead 2')
WORK = ROOT / 'reports/spray_selector/deploy'
JOURNAL = WORK / 'transaction.json'
NAME = VPK.name
RELATIVE = {'vpk': Path('left4dead2/addons') / NAME, 'dll': Path('bin/neko/plugins/CSPSelector.dll'),
            'addonlist': Path('left4dead2/addonlist.txt')}


def decode(raw):
    for encoding in ('utf-8-sig', 'gb18030') if raw.startswith(b'\xef\xbb\xbf') else ('utf-8', 'gb18030'):
        try:
            text = raw.decode(encoding)
            if text.encode(encoding) == raw:
                return text, encoding
        except UnicodeError:
            pass
    raise ValueError('Unreviewed addonlist encoding')


def addon_nodes(raw):
    text, encoding = decode(raw)
    tree = parse(text)
    assert len(tree) == 1 and tree[0].key.lower() == 'addonlist'
    nodes = tree[0].value
    assert all(isinstance(item.value, str) for item in nodes)
    names = [item.key.replace('\\', '/').casefold() for item in nodes]
    assert len(names) == len(set(names)), 'Duplicate addonlist entries'
    return text, encoding, nodes


def addon_state(raw):
    _, _, nodes = addon_nodes(raw)
    return next((item.value for item in nodes if item.key.replace('\\', '/').casefold() == NAME.casefold()), None)


def set_addon(raw, state):
    text, encoding, nodes = addon_nodes(raw)
    item = next((item for item in nodes if item.key.replace('\\', '/').casefold() == NAME.casefold()), None)
    if item and state is not None:
        value = tokenize(text[item.start:item.end])[1]
        begin, end = item.start + value.start, item.start + value.end
        text = text[:begin] + '"' + state + '"' + text[end:]
    elif item:
        text = text[:item.start] + text[item.end:]
    elif state is not None:
        newline = '\r\n' if '\r\n' in text else '\n'
        at = text.rfind('}')
        text = text[:at] + f'\t"{NAME}"\t\t"{state}"{newline}' + text[at:]
    result = text.encode(encoding)
    assert addon_state(result) == state
    return result


def inventory(path):
    """Read only the VPK directory tree. Never load any texture or image data."""
    with path.open('rb') as stream:
        signature, version, size = struct.unpack('<III', stream.read(12))
        assert signature == 0x55AA1234 and version in (1, 2) and size <= 64 * 1024 * 1024, f'Unreviewed VPK header: {path}'
        stream.seek(12 if version == 1 else 28)
        tree = stream.read(size)
    assert len(tree) == size
    at, names = 0, set()

    def string():
        nonlocal at
        end = tree.index(b'\0', at)
        value = tree[at:end].decode('utf-8')
        at = end + 1
        return value

    while extension := string():
        while folder := string():
            while name := string():
                _, preload, _, _, _, term = struct.unpack_from('<IHHIIH', tree, at)
                at += 18 + preload
                assert term == 0xffff and at <= len(tree)
                filename = name + ('.' + extension if extension != ' ' else '')
                key = (folder + '/' if folder != ' ' else '') + filename
                key = key.replace('\\', '/').casefold()
                assert key not in names, 'Case-folded resource collision'
                names.add(key)
    assert at == len(tree)
    return names


def target(game, key):
    path = game / RELATIVE[key]
    assert path.resolve().is_relative_to(game.resolve()) and not path.is_symlink()
    assert path.parent.is_dir()
    return path


def protected(game):
    paths = (game / 'left4dead2/addons/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk',
             game / 'bin/neko/plugins/CSessionDefaults.dll', game / 'bin/gameui.dll')
    return {str(path): sha(path) for path in paths if path.exists()}


def conflicts(game):
    raw = target(game, 'addonlist').read_bytes()
    _, _, nodes = addon_nodes(raw)
    states = {item.key.replace('\\', '/').casefold(): item.value for item in nodes}
    wanted = inventory(VPK) - {'addoninfo.txt', 'addonimage.jpg'}
    addons = game / 'left4dead2/addons'
    records, collisions = [], []
    for path in sorted([*addons.glob('*.vpk'), *(addons / 'workshop').glob('*.vpk')]):
        if path.resolve() == target(game, 'vpk').resolve():
            continue
        relative = path.relative_to(addons).as_posix()
        enabled = states.get(relative.casefold(), '1') != '0'
        with path.open('rb') as stream:
            zip_header = stream.read(4) == b'PK\x03\x04'
        installer = zip_header and zipfile.is_zipfile(path)
        overlap = sorted(inventory(path) & wanted) if enabled and not installer else []
        records.append(dict(path=str(path), enabled=enabled, overlaps=overlap,
                            format='ZIP_INSTALLER_NOT_NATIVE_VPK' if installer else 'VPK'))
        if overlap:
            collisions.append(dict(path=str(path), overlaps=overlap))
    for layer in ('update', 'left4dead2_dlc3', 'left4dead2_dlc2', 'left4dead2_dlc1', 'left4dead2'):
        loose = game / layer / 'resource/ui/l4d360ui/multiplayer.res'
        if loose.exists():
            collisions.append(dict(path=str(loose), overlaps=['resource/ui/l4d360ui/multiplayer.res']))
    return dict(scope='Enabled root/workshop VPK directory entries only, plus native-layer loose multiplayer.res; no image payload read',
                addonlist_sha256=sha(target(game, 'addonlist')), inspected=records, collisions=collisions)


def stopped():
    command = ['tasklist', '/FI', 'IMAGENAME eq left4dead2.exe', '/FO', 'CSV', '/NH']
    result = subprocess.run(command, capture_output=True, text=True, errors='replace', check=True)
    assert not any(row and row[0].lower() == 'left4dead2.exe' for row in csv.reader(io.StringIO(result.stdout))), 'Exit L4D2 before deployment/rollback'


def check_sources():
    report = json.loads((WORK.parent / 'verification.json').read_text(encoding='utf-8'))
    assert report['status'] == 'PHASE_2_TWO_STATIC_ROUNDS_PASS_RUNTIME_PENDING'
    assert len(report['rounds']) == 2 and report['rounds'][0] == report['rounds'][1]
    assert all(row['exit_status'] == 0 for row in report['records'])
    source = Path(__file__).resolve().parent
    current = {str(path.relative_to(ROOT)): sha(path) for path in sorted(source.rglob('*'))
               if path.is_file() and path.suffix in ('.py', '.cpp', '.h')}
    assert current == report['source_hashes'], 'Prototype sources changed after review'
    for path in (VPK, DLL, ZIP):
        assert sha(path) == report['rounds'][0][str(path.relative_to(ROOT))]
    validate(read(VPK))


def preflight(game=GAME):
    check_sources()
    report = conflicts(game)
    report['targets'] = {key: str(target(game, key).resolve()) for key in RELATIVE}
    report['before_hashes'] = {key: sha(target(game, key)) if target(game, key).exists() else None for key in RELATIVE}
    report['protected'] = protected(game)
    save(WORK / 'preflight.json', report)
    for key, path in report['targets'].items():
        print('TARGET', key, path)
    print('VPKs checked:', len(report['inspected']), 'conflicts:', len(report['collisions']))
    assert not report['collisions'], report['collisions']
    assert addon_state(target(game, 'addonlist').read_bytes()) in (None, '0', '1')
    return report


def rollback(journal, preview=False):
    game = Path(journal['game'])
    actions = []
    for key in ('vpk', 'dll'):
        row = journal['files'][key]
        path = target(game, key)
        present = sha(path) if path.exists() else None
        assert present in (row['before'], row['after']), 'File changed since deployment'
        if row['before']:
            backup = ROOT / row['backup']
            assert backup.resolve().is_relative_to(WORK.resolve()) and sha(backup) == row['before']
            actions.append((key, path, backup))
            print('RESTORE', path, 'FROM', backup)
        elif path.exists():
            disabled = path.with_name(path.name + '.' + journal['id'] + '.disabled')
            assert not disabled.exists()
            actions.append((key, path, disabled))
            print('DISABLE', path, 'TO', disabled)
    addonlist = target(game, 'addonlist')
    raw = addonlist.read_bytes()
    current = addon_state(raw)
    before = journal['addon_before_state']
    assert current in (before, '1'), 'CSP addon entry changed since deployment'
    if sha(addonlist) == journal['files']['addonlist']['after']:
        backup = ROOT / journal['files']['addonlist']['backup']
        assert backup.resolve().is_relative_to(WORK.resolve()) and sha(backup) == journal['files']['addonlist']['before']
        restored_list = backup.read_bytes()
    else:
        restored_list = set_addon(raw, before)
    if preview:
        print('PASS rollback preview; restore only CSP addon entry, preserve unrelated addonlist edits')
        return
    for key, path, backup in actions:
        if journal['files'][key]['before']:
            copy_verified(backup, path, sha(backup))
        else:
            path.rename(backup)
            assert not path.exists() and sha(backup) == journal['files'][key]['after']
    stage = WORK / ('addonlist_restore_' + journal['id'] + '.txt')
    stage.write_bytes(restored_list)
    copy_verified(stage, addonlist, sha(stage))
    assert addon_state(addonlist.read_bytes()) == before
    assert protected(game) == journal['protected']
    journal['status'] = 'ROLLED_BACK'
    save(JOURNAL, journal)
    print('PASS rollback; CSP components restored/disabled; C unchanged')


def deploy(game=GAME, fixture=False):
    if not fixture:
        stopped()
        plan = preflight(game)
    else:
        plan = dict(protected=protected(game))
    generation = uuid.uuid4().hex
    folder = WORK / 'transactions' / generation
    folder.mkdir(parents=True)
    addonlist = target(game, 'addonlist')
    raw = addonlist.read_bytes()
    stage = folder / 'addonlist.after.txt'
    stage.write_bytes(set_addon(raw, '1'))
    sources = dict(vpk=VPK, dll=DLL, addonlist=stage)
    journal = dict(id=generation, game=str(game), protected=plan['protected'], status='PREPARED',
                   addon_before_state=addon_state(raw), files={})
    for key, source in sources.items():
        path = target(game, key)
        before = sha(path) if path.exists() else None
        backup = folder / (key + '.before')
        if before:
            shutil.copyfile(path, backup)
            assert sha(backup) == before
        journal['files'][key] = dict(before=before, after=sha(source), backup=str(backup.relative_to(ROOT)))
    save(JOURNAL, journal)
    for key, source in sources.items():
        path = target(game, key)
        assert (sha(path) if path.exists() else None) == journal['files'][key]['before'], 'Destination changed during staging'
        copy_verified(source, path, journal['files'][key]['after'])
    assert protected(game) == journal['protected']
    assert addon_state(addonlist.read_bytes()) == '1'
    journal['status'] = 'INSTALLED_RUNTIME_PENDING'
    save(JOURNAL, journal)
    rollback(journal, preview=True)
    print('PASS VPK/DLL installed and hash-verified; CSP addon enabled; C unchanged; runtime pending')
    return journal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'deploy', 'verify', 'rollback-preview', 'rollback'))
    args = parser.parse_args()
    if args.action == 'preflight':
        preflight()
    elif args.action == 'deploy':
        deploy()
    else:
        journal = json.loads(JOURNAL.read_text(encoding='utf-8'))
        assert journal['game'] == str(GAME)
        if args.action == 'verify':
            for key in ('vpk', 'dll'):
                assert sha(target(GAME, key)) == journal['files'][key]['after']
            assert addon_state(target(GAME, 'addonlist').read_bytes()) == '1'
            assert protected(GAME) == journal['protected']
            print('PASS installed CSP VPK/DLL and addon state; C unchanged; runtime pending')
        else:
            if args.action == 'rollback':
                stopped()
            rollback(journal, preview=args.action == 'rollback-preview')


if __name__ == '__main__':
    main()
