"""Compare selected package paths and preserve bounded configuration evidence.

This does not extract executable files, run scripts, or alter an installation.
"""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

from release_paths import ROOT
from vpk import read as read_vpk

IDS = ('3787239937', '3558049615', '3785109042')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    for codec in ('utf-8-sig', 'utf-16', 'gb18030'):
        try:
            return raw.decode(codec)
        except UnicodeError:
            pass
    return raw.decode('utf-8', errors='replace')


def inspect(folder, selected):
    output = folder / 'inspection'
    output.mkdir(exist_ok=True)
    records, paths, nested = {}, {}, {}
    metadata = {str(d['publishedfileid']): d for d in json.loads(
        (folder / 'api_response.json').read_text(encoding='utf-8'))['response']['publishedfiledetails']}
    for item in selected:
        path = folder / (item + '.vpk')
        files = {}
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                name = entry.filename.replace('\\', '/')
                parts = PurePosixPath(name).parts
                assert not name.startswith('/') and '..' not in parts and ':' not in name
                assert name.casefold() not in files
                files[name.casefold()] = (name, archive.read(entry))
        paths[item] = files
        rows = []
        text_rows = []
        native_strings = {}
        nested[item] = {}
        for key, (name, raw) in files.items():
            rows.append({'path': name, 'bytes': len(raw), 'sha256': sha(raw)})
            if key.endswith(('.txt', '.sample', '.json', '.vdf', '.cfg', '.bat', '.ps1')) and len(raw) < 1024 * 1024:
                text = decode(raw)
                target = output / item / (name + '.txt')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding='utf-8', newline='\n')
                text_rows.append({'source': name, 'saved_as': str(target.relative_to(ROOT))})
            if raw[:2] == b'MZ':
                strings = [s.decode('ascii') for s in re.findall(rb'[\x20-\x7e]{5,}', raw)]
                # Strings are indicators only, not proof a feature executes.
                selected_strings = sorted({s for s in strings if len(s) < 240 and re.search(
                    r'skeeto|evolved|l4n|wininet\.dll|winmm\.dll|d3d9\.dll|GetL4NPlugin|NoHmd|Crosshair|Minimap|HitSound|HitMarker', s, re.I)})
                target = output / item / (name.replace('/', '_') + '_strings.txt')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('\n'.join(selected_strings), encoding='utf-8')
                native_strings[name] = {'sha256': sha(raw), 'saved_as': str(target.relative_to(ROOT)), 'selected_strings': len(selected_strings)}
            if key.endswith('.vpk') and raw[:4] == b'\x34\x12\xaa\x55':
                # Existing VPK parser takes a path; store only archive bytes as evidence.
                target = output / item / 'nested' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                members = read_vpk(target)
                for member, content in members.items():
                    nested[item].setdefault(member.casefold(), []).append({'container': name, 'path': member, 'sha256': sha(content)})
        description = output / item / 'workshop_description_from_api.txt'
        description.parent.mkdir(parents=True, exist_ok=True)
        description.write_text(metadata[item].get('description', ''), encoding='utf-8', newline='\n')
        records[item] = {'package_sha256': sha(path.read_bytes()), 'files': rows, 'text_evidence': text_rows, 'native_string_evidence': native_strings,
                         'description_evidence': {'source': 'official Workshop API description, not HTML snapshot', 'saved_as': str(description.relative_to(ROOT))}}
        print(item + ': ' + str(len(files)) + ' files, ' + str(len(nested[item])) + ' bundled VPK resource paths')
    collisions = []
    resource_collisions = []
    for i, left in enumerate(selected):
        for right in selected[i + 1:]:
            for name in sorted(set(paths[left]) & set(paths[right])):
                a, b = paths[left][name], paths[right][name]
                collisions.append({'left': left, 'right': right, 'path': a[0], 'same_bytes': a[1] == b[1], 'left_sha256': sha(a[1]), 'right_sha256': sha(b[1])})
            for name in sorted(set(nested[left]) & set(nested[right])):
                resource_collisions.append({'left': left, 'right': right, 'path': name, 'left_members': nested[left][name], 'right_members': nested[right][name]})
    report = {'scope': 'static package comparison, no runtime compatibility proof', 'packages': records,
              'same_install_path': collisions, 'bundled_resource_overlap': resource_collisions}
    target = output / ('comparison.json' if len(selected) == 3 else 'partial_comparison.json')
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert json.loads(target.read_text(encoding='utf-8')) == report
    print('COLLISIONS ' + json.dumps(collisions, ensure_ascii=False))
    print('REPORT ' + str(target))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--item', choices=IDS)
    args = parser.parse_args()
    inspect(args.folder.resolve(), (args.item,) if args.item else IDS)


if __name__ == '__main__':
    main()
