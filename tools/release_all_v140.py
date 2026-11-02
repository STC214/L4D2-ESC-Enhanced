"""Package/publish current deliverables only; never read user image directories."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import urllib.parse
import zipfile

import publish_github_release as previous
from c_session_release import save

ROOT = Path(__file__).resolve().parents[1]
TAG = 'v1.4.0'
OUT = ROOT / 'dist/release_v1.4.0'
REPORT = ROOT / 'reports/release_v1.4.0'
NOTES = ROOT / 'docs/releases/v1.4.0.md'
NAME = '【00】C_ESC_LED_血条和速度_TUMTaRA.vpk'
EXE = ROOT / 'dist/spray_importer_go/CSP_Spray_Manager.exe'
SELECTOR = ROOT / 'dist/spray_selector_prototype'
MANAGER_ZIP = 'CSP_Spray_Manager_v1.1.1.zip'
SELECTOR_ZIP = 'CSP_Selector_Complete_v1.4.0.zip'
ALL_ZIP = 'L4D2_ESC_All_Products_v1.4.0.zip'
MANAGER_VERSION = '1.1.1'
GO_TEST_COUNT = 29
REQUIRE_STUDIO = False


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources():
    files = [ROOT / 'README.md', ROOT / '启动喷漆导入工具.cmd']
    files += [path for path in (ROOT / 'docs').rglob('*') if path.is_file() and path.suffix in ('.md', '.json', '.png')]
    files += list((ROOT / 'tools').glob('*.py'))
    files += [ROOT / 'maintenance/inspect_spray_menu.py', ROOT / 'maintenance/spray_mod_path_probe.py']
    for folder in ('native/spray_importer', 'experimental/spray_selector'):
        files += [path for path in (ROOT / folder).rglob('*') if path.is_file()
                  and path.suffix in ('.go', '.mod', '.ps1', '.vpk', '.py', '.h', '.cpp', '.rc', '.ico', '.syso')]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(set(files))}


def verify_components():
    previous.check()
    c = json.loads((ROOT / 'reports/c_current_review/verification.json').read_text(encoding='utf-8'))
    assert sha(ROOT / 'dist/c_session_helper/CSessionDefaults.dll') == c['rounds'][0]['helper_sha256']
    go = json.loads((ROOT / 'reports/spray_importer_go/verification.json').read_text(encoding='utf-8-sig'))
    assert go['version'] == MANAGER_VERSION and sha(EXE).upper() == go['exe_sha256']
    assert all(row['exit_status'] == 0 for row in go['records'])
    output = next(row['output'] for row in go['records'] if 'test' in row['command'])
    assert output.count('--- PASS:') == GO_TEST_COUNT * 2 and '--- SKIP:' not in output
    if REQUIRE_STUDIO:
        from verify_exe_icon import verify
        verify(EXE, ROOT / 'native/spray_importer/assets/app.ico')
        smoke = json.loads((ROOT / 'reports/spray_importer_go/win32-smoke.json').read_text(encoding='utf-8'))
        assert smoke['embedded_icons_loaded'] and smoke['studio_theme_painted']
    for name, digest in go['source_sha256'].items():
        assert sha(ROOT / 'native/spray_importer' / name).upper() == digest
    native = json.loads((ROOT / 'reports/spray_selector/verification.json').read_text(encoding='utf-8'))
    assert native['status'] == 'PHASE_2_TWO_STATIC_ROUNDS_PASS_RUNTIME_PENDING'
    assert native['rounds'][0] == native['rounds'][1]
    assert all(row['exit_status'] == 0 for row in native['records'])
    for name, digest in native['source_hashes'].items():
        assert sha(ROOT / name) == digest
    for name, digest in native['rounds'][0].items():
        assert sha(ROOT / name) == digest
    assert sha(ROOT / 'native/spray_importer/assets/selector.vpk') == sha(SELECTOR / 'CSP_Numbered_Selector_TEST.vpk')


def archive(path, files):
    files = dict(files)
    assert all(not Path(name).is_absolute() and '..' not in Path(name).parts for name in files)
    files['manifest.json'] = (json.dumps({'files': {name: hashlib.sha256(data).hexdigest()
                              for name, data in sorted(files.items())}}, indent=2) + '\n').encode()
    with zipfile.ZipFile(path, 'w') as stream:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            stream.writestr(info, data)
    with zipfile.ZipFile(path) as stream:
        assert stream.testzip() is None
        assert {name: stream.read(name) for name in stream.namelist()} == files


def package():
    verify_components()
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    from vpk import read
    vpk = SELECTOR / 'CSP_Numbered_Selector_TEST.vpk'
    content = read(vpk)
    selector_files = {'left4dead2/addons/' + vpk.name: vpk.read_bytes(),
                      'bin/neko/plugins/CSPSelector.dll': (SELECTOR / 'native/CSPSelector.dll').read_bytes()}
    textures = {name: data for name, data in content.items() if name.startswith('materials/vgui/logos/csp_test/')}
    assert len(textures) == 80 and all(Path(name).suffix in ('.vtf', '.vmt') for name in textures)
    selector_files.update({'update/' + name: data for name, data in textures.items()})
    selector_files['INSTALL.md'] = (
        '# CSP independent selector\n\nExisting x86 L4N is required and is not bundled. Exit the game. Back up existing matching files. '
        'Copy bin, left4dead2 and update into the directory containing left4dead2.exe. '
        'Ensure CSP_Numbered_Selector_TEST.vpk is enabled in addonlist.txt. Do not install the diagnostic asset-only VPK alongside it.\n\n'
        'Select Options > Multiplayer > CSP TEST before opening a campaign. Changing in-session does not refresh immediately. '
        'The 80 loose files under update are REQUIRED, not just the VPK/DLL. Restore your backup to uninstall/update backwards. '
        'No native engine DLL on disk is replaced. Current bridge is pinned to inspected game binaries.\n').encode()
    archive(OUT / SELECTOR_ZIP, selector_files)
    manager_files = {'CSP_Spray_Manager.exe': EXE.read_bytes(),
                     '使用说明.md': (ROOT / 'docs/喷漆导入工具.md').read_bytes()}
    if REQUIRE_STUDIO:
        manager_files['images/spray-studio-preview.png'] = (ROOT / 'docs/images/spray-studio-preview.png').read_bytes()
    archive(OUT / MANAGER_ZIP, manager_files)
    for source, name in ((ROOT / 'dist/C_session_release.zip', 'C_session_release.zip'),
                         (ROOT / 'dist' / NAME, 'C_ESC_LED_Health_Speed_TUMTaRA.vpk'),
                         (EXE, EXE.name), (SELECTOR / 'CSP_Numbered_Test_Assets.vpk', 'CSP_Numbered_Test_Assets.vpk'),
                         (SELECTOR / 'numbered_contact_sheet.png', 'numbered_contact_sheet.png')):
        shutil.copyfile(source, OUT / name)
        assert sha(source) == sha(OUT / name)
    all_files = {'game/' + name: data for name, data in selector_files.items() if name != 'INSTALL.md'}
    all_files['game/left4dead2/addons/' + NAME] = (ROOT / 'dist' / NAME).read_bytes()
    all_files['game/bin/neko/plugins/CSessionDefaults.dll'] = (ROOT / 'dist/c_session_helper/CSessionDefaults.dll').read_bytes()
    all_files.update({'manager/' + name: data for name, data in manager_files.items()})
    all_files['INSTALL.md'] = NOTES.read_bytes()
    all_files['diagnostics/CSP_Numbered_Test_Assets.vpk'] = (OUT / 'CSP_Numbered_Test_Assets.vpk').read_bytes()
    all_files['diagnostics/numbered_contact_sheet.png'] = (OUT / 'numbered_contact_sheet.png').read_bytes()
    all_files['README.md'] = (ROOT / 'README.md').read_bytes()
    for path in (ROOT / 'docs').rglob('*'):
        if path.is_file() and path.suffix in ('.md', '.json', '.png'):
            all_files['docs/' + path.relative_to(ROOT / 'docs').as_posix()] = path.read_bytes()
    for name in ('spray_importer_go/verification.json', 'spray_importer_go/win32-smoke.json',
                 'spray_selector/verification.json', 'c_current_review/verification.json'):
        all_files['evidence/' + name] = (ROOT / 'reports' / name).read_bytes()
    archive(OUT / ALL_ZIP, all_files)
    names = [ALL_ZIP, SELECTOR_ZIP, MANAGER_ZIP, 'C_session_release.zip', 'C_ESC_LED_Health_Speed_TUMTaRA.vpk',
             EXE.name, 'CSP_Numbered_Test_Assets.vpk', 'numbered_contact_sheet.png']
    sums = ''.join(f'{sha(OUT / name)}  {name}\n' for name in sorted(names))
    (OUT / 'SHA256SUMS.txt').write_text(sums, encoding='utf-8', newline='\n')
    names.append('SHA256SUMS.txt')
    save(REPORT / 'package.json', dict(tag=TAG, files={name: sha(OUT / name) for name in names},
         sources=sources(), scope='Current deliverables, numbered self-authored fixtures only; no user data, upstream downloads or historical builds'))
    print('PASS 9 release assets; ZIP CRC/member hashes and component reviews verified')


def check():
    manifest = json.loads((REPORT / 'package.json').read_text(encoding='utf-8'))
    assert manifest['sources'] == sources(), 'Sources/docs changed after packaging'
    for name, digest in manifest['files'].items():
        assert sha(OUT / name) == digest
        if name.endswith('.zip'):
            with zipfile.ZipFile(OUT / name) as stream:
                assert stream.testzip() is None
    return manifest


def verify_remote(release, manifest):
    remote = {row['name']: row for row in release['assets']}
    assert set(remote) == set(manifest['files']), 'Missing/unexpected remote release assets'
    for name, digest in manifest['files'].items():
        row = remote[name]
        assert row['state'] == 'uploaded' and row['size'] == (OUT / name).stat().st_size
        assert row.get('digest') == 'sha256:' + digest, name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('package', 'check', 'preflight', 'publish', 'verify'))
    action = parser.parse_args().action
    if action == 'package':
        package()
        return
    if action == 'check':
        print('PASS', len(check()['files']), 'local release assets')
        return
    api = previous.Github()
    repository = api.request(previous.API)
    assert repository['full_name'].lower() == previous.REPO.lower() and repository.get('permissions', {}).get('push')
    endpoint = previous.API + '/releases/tags/' + TAG
    release = api.request(endpoint, missing=True)
    if action == 'preflight':
        assert release is None or release['draft'], 'Release already published; use verify'
        print('PASS authenticated repository; target', TAG, 'available/draft')
        return
    manifest = check()
    assert not previous.git('status', '--porcelain', '--untracked-files=no'), 'Commit tracked release changes first'
    commit = previous.git('rev-parse', TAG + '^{commit}')
    assert commit == previous.git('rev-parse', 'HEAD')
    for path in manifest['sources']:
        assert previous.git('hash-object', '--', path) == previous.git('rev-parse', TAG + ':' + path), 'Untagged source: ' + path
    ref = api.request(previous.API + '/git/ref/tags/' + TAG)['object']
    if ref['type'] == 'tag':
        ref = api.request(previous.API + '/git/tags/' + ref['sha'])['object']
    assert ref['type'] == 'commit' and ref['sha'] == commit
    if action == 'publish':
        if release is None:
            release = api.request(previous.API + '/releases', 'POST', dict(tag_name=TAG, target_commitish=commit,
                name=TAG + ' — C + Spray Studio ' + MANAGER_VERSION, body=NOTES.read_text(encoding='utf-8'),
                draft=True, prerelease=True))
        existing = {row['name']: row for row in release['assets']}
        for name, digest in manifest['files'].items():
            if name in existing:
                assert existing[name].get('digest') == 'sha256:' + digest, 'Existing asset differs; never overwrite'
                continue
            assert release['draft'], 'Only append assets while draft'
            print('UPLOAD', name, flush=True)
            url = release['upload_url'].split('{', 1)[0] + '?' + urllib.parse.urlencode({'name': name})
            row = api.request(url, 'POST', (OUT / name).read_bytes(), binary=True)
            assert row['name'] == name and row.get('digest') == 'sha256:' + digest
        release = api.request(previous.API + '/releases/' + str(release['id']))
        verify_remote(release, manifest)
        if release['draft']:
            release = api.request(previous.API + '/releases/' + str(release['id']), 'PATCH', {'draft': False, 'prerelease': True})
    assert release and not release['draft']
    release = api.request(previous.API + '/releases/' + str(release['id']))
    verify_remote(release, manifest)
    save(REPORT / 'published.json', dict(tag=TAG, commit=commit, url=release['html_url'], prerelease=release['prerelease'],
        assets=[{key: row[key] for key in ('name', 'size', 'digest', 'browser_download_url')} for row in release['assets']]))
    print('PASS remote tag/commit and all 9 SHA256/size checks')
    print(release['html_url'])


if __name__ == '__main__':
    main()
