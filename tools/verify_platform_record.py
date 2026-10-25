"""Verify the selected Workshop catalogue against preserved API/package evidence."""

import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

from record_platform_sources import API, Description, ITEMS
from release_paths import ROOT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    catalog_path = ROOT / 'docs/workshop-platforms.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    folder = ROOT / catalog['evidence_directory']
    sources = json.loads((folder / 'sources.json').read_text(encoding='utf-8'))
    api = {str(d['publishedfileid']): d for d in json.loads((folder / 'api_response.json').read_text(encoding='utf-8'))['response']['publishedfiledetails']}
    inspection = json.loads((folder / 'inspection/comparison.json').read_text(encoding='utf-8'))
    assert {p['id'] for p in catalog['platforms']} == set(ITEMS) == set(api)
    assert catalog['metadata_api']['url'] == API
    paths = {}
    for platform in catalog['platforms']:
        item = platform['id']
        data = api[item]
        assert data['result'] == 1 and data['consumer_app_id'] == catalog['consumer_app_id'] == 550
        for key in ('hcontent_file', 'time_updated', 'file_size'):
            assert str(platform[key]) == str(data[key]), (item, key)
        assert platform['snapshot_file_url'] == data['file_url']
        assert platform['page'] == f'https://steamcommunity.com/sharedfiles/filedetails/?id={item}'
        path = folder / (item + '.vpk')
        assert sha(path) == platform['sha256'] == inspection['packages'][item]['package_sha256']
        assert path.stat().st_size == platform['file_size']
        assert platform['actual_format'] == 'ZIP'
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            members = {e.filename.replace('\\', '/').casefold(): e for e in archive.infolist() if not e.is_dir()}
            assert len(members) == platform['regular_files'] == len(inspection['packages'][item]['files'])
            assert all(name.casefold() in members for name in platform['main_files'])
            paths[item] = set(members)
            if item == '3787239937':
                text = archive.read('VERSION.txt').decode('utf-8-sig')
                assert re.search(r'(?m)^semver=' + re.escape(platform['version']) + r'\s*$', text)
            elif item == '3785109042':
                assert archive.read('Evolved/version.txt').decode('utf-8-sig').strip() == platform['version']
            else:
                text = archive.read('readme_l4n.txt').decode('utf-8-sig')
                assert re.search(r'\[(\d+\.\d+\.\d+)\]', text).group(1) == platform['version']
        description = folder / 'inspection' / item / 'workshop_description_from_api.txt'
        assert description.read_text(encoding='utf-8') == data['description'].replace('\r\n', '\n')
    for i, left in enumerate(ITEMS):
        for right in ITEMS[i + 1:]:
            assert not paths[left] & paths[right], (left, right)
    assert inspection['same_install_path'] == [] and inspection['bundled_resource_overlap'] == []
    doc = ROOT / catalog['comparison']['matrix_document']
    text = doc.read_text(encoding='utf-8')
    assert all(f'F{i:02}' in text for i in range(1, 14))
    assert all(f'P{i:02}' in text for i in range(1, 6))
    assert all(p['page'] in text for p in catalog['platforms'])
    assert 'HTTP 429' in text and '待实测' in text
    # Minimal parser regression: nested nodes/void elements must not eat following content.
    parser = Description()
    parser.feed('<div class="workshopItemDescription" id="highlightContent">a<br><b>b</b><a href="https://example.test/">c</a></div><div>outside</div>')
    assert ''.join(parser.text).strip() == 'a\nbc'
    assert parser.links == ['https://example.test/']
    game = Path(r'E:\SteamLibrary\steamapps\common\Left 4 Dead 2')
    install = {}
    for name in ('bin/left4neko.dll', 'skeeto.dll', 'bin/wininet.dll', 'winmm.dll', 'bin/winmm.dll',
                 'bin/neko/plugins/L4D2Evolved.dll', 'bin/neko/plugins/L4d2evomodel.dll'):
        path = game / name
        install[name] = {'exists': path.is_file(), 'sha256': sha(path) if path.is_file() else None}
    print('PASS 3 IDs, fresh API identities, versions, lengths, SHA256 and ZIP CRCs')
    print('PASS 27/76/15 package files; all three pairs have zero same-file paths')
    print('PASS API description provenance, 13 functional rows, 5 install rows and parser regression')
    print('NOTE runtime coexistence remains NOT_TESTED; no installation writes')
    report = {'command': [sys.executable, *sys.argv], 'exit_status': 0,
              'scope': 'static catalogue/package verification; no game execution or writes',
              'artifacts': {str(p.relative_to(ROOT)): sha(p) for p in (catalog_path, doc, folder / 'sources.json', folder / 'inspection/comparison.json')},
              'read_only_installed_module_snapshot': install, 'runtime_status': 'NOT_TESTED'}
    target = folder / 'verification.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert json.loads(target.read_text(encoding='utf-8')) == report
    print('RECORD ' + str(target))


if __name__ == '__main__':
    main()
