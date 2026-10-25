"""Create/replay a full-replacement helper patch and verify prior-DLL rollback."""

import difflib
import hashlib
import json
import shutil
import zipfile

from c_session_release import DLL, ROOT, save, sha


def main():
    work = ROOT / 'reports/c_session_audit'
    before = work / 'before_helper.dll'
    before_hash = 'c6be091992ef23cf9a6c4e1250cfebfb64532aa42356bb051d52d0e24f4a8785'
    assert sha(before) == before_hash
    header = ROOT / 'native/c_session_defaults/session_state.h'
    diff = ''.join(difflib.unified_diff(
        (work / 'before_session_state.h.txt').read_text(encoding='utf-8').splitlines(keepends=True),
        header.read_text(encoding='utf-8').splitlines(keepends=True),
        fromfile='before/native/c_session_defaults/session_state.h',
        tofile='after/native/c_session_defaults/session_state.h'))
    (work / 'fixes.patch').write_text(diff, encoding='utf-8', newline='\n')
    sources = [header, ROOT / 'native/c_session_defaults/plugin.cpp',
               ROOT / 'native/c_session_defaults/test_session_state.cpp',
               ROOT / 'tools/c_session_release.py', ROOT / 'tools/test_c_session_deploy.py',
               ROOT / 'tools/review_c_session_deployment.py']
    manifest = {'format': 'sha256-guarded full replacement; not a byte-offset patch',
                'target': 'bin/neko/plugins/CSessionDefaults.dll',
                'before_sha256': before_hash, 'after_sha256': sha(DLL),
                'sources': {str(p.relative_to(ROOT)): sha(p) for p in sources},
                'runtime_status': 'NOT_TESTED'}
    payload = {'manifest.json': (json.dumps(manifest, indent=2) + '\n').encode(),
               'payload/CSessionDefaults.dll': DLL.read_bytes(), 'fixes.patch': diff.encode()}
    payload.update({'sources/' + p.relative_to(ROOT).as_posix(): p.read_bytes() for p in sources})
    bundle = work / 'fix_bundle.zip'
    with zipfile.ZipFile(bundle, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(payload.items()):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, content)
    with zipfile.ZipFile(bundle) as archive:
        assert archive.testzip() is None
        assert json.loads(archive.read('manifest.json')) == manifest
        assert {n: archive.read(n) for n in archive.namelist()} == payload
        old = before.read_bytes()
        assert hashlib.sha256(old).hexdigest() == manifest['before_sha256']
        replacement = archive.read('payload/CSessionDefaults.dll')
        assert hashlib.sha256(replacement).hexdigest() == manifest['after_sha256']
        replayed = ROOT / 'dist/C_session_helper_replayed.dll'
        replayed.write_bytes(replacement)
        assert replayed.read_bytes() == DLL.read_bytes()
    restored = ROOT / 'dist/C_session_helper_before_audit.dll'
    shutil.copyfile(before, restored)
    assert sha(restored) == before_hash
    save(work / 'patch_verification.json', {'before_sha256': before_hash, 'after_sha256': sha(DLL),
         'bundle_sha256': sha(bundle), 'replay_sha256': sha(replayed), 'rollback_sha256': sha(restored),
         'scope': 'actual patch replay and rollback copies; installed game untouched'})
    print('PASS full-replacement patch ZIP reopened, CRC and payload hashes verified')
    print('PASS helper patch replay = current DLL; rollback copy = previous DLL')
    print('PATCH ' + str(bundle))


if __name__ == '__main__':
    main()
