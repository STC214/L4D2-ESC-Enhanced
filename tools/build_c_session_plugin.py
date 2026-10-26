"""Build the pinned-ABI x86 L4N helper and execute its standalone state tests."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

from release_paths import ROOT


def main():
    vc = Path(r'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.44.35207')
    sdk = Path(r'C:\Program Files (x86)\Windows Kits\10')
    version = '10.0.26100.0'
    env = os.environ.copy()
    env['PATH'] = str(vc / 'bin/Hostx64/x86') + os.pathsep + env.get('PATH', '')
    env['INCLUDE'] = ';'.join(map(str, (vc / 'include', sdk / 'Include' / version / 'ucrt', sdk / 'Include' / version / 'shared', sdk / 'Include' / version / 'um')))
    env['LIB'] = ';'.join(map(str, (vc / 'lib/x86', sdk / 'Lib' / version / 'ucrt/x86', sdk / 'Lib' / version / 'um/x86')))
    source = ROOT / 'native/c_session_defaults'
    out = ROOT / 'dist/c_session_helper'
    out.mkdir(parents=True, exist_ok=True)
    compiler = str(vc / 'bin/Hostx64/x86/cl.exe')
    common = [compiler, '/nologo', '/std:c++17', '/W4', '/WX', '/EHsc', '/MT', '/Brepro']
    commands = [
        common + [str(source / 'test_session_state.cpp'), '/Fo' + str(out / 'test.obj'), '/Fe' + str(out / 'session_state_test.exe'), '/link', '/Brepro', '/MACHINE:X86'],
        [str(out / 'session_state_test.exe')],
        common + ['/LD', str(source / 'plugin.cpp'), '/Fo' + str(out / 'plugin.obj'), '/Fe' + str(out / 'CSessionDefaults.dll'), '/link', '/Brepro', '/MACHINE:X86', 'user32.lib', 'bcrypt.lib'],
        common + [str(source / 'test_plugin_contract.cpp'), '/Fo' + str(out / 'contract.obj'), '/Fe' + str(out / 'plugin_contract_test.exe'), '/link', '/Brepro', '/MACHINE:X86'],
        [str(out / 'plugin_contract_test.exe'), str(out / 'CSessionDefaults.dll')],
    ]
    records = []
    for command in commands:
        process = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, errors='replace')
        print(process.stdout, end='')
        print(process.stderr, end='')
        records.append({'command': command, 'stdout': process.stdout, 'stderr': process.stderr, 'exit_status': process.returncode})
        if process.returncode:
            raise RuntimeError('Native build/test failed')
    dll = out / 'CSessionDefaults.dll'
    raw = dll.read_bytes()
    import struct
    pe = struct.unpack_from('<I', raw, 0x3c)[0]
    assert struct.unpack_from('<H', raw, pe + 4)[0] == 0x14c
    assert b'GetL4NPluginInstance\0' in raw
    report = {'scope': 'x86 build + standalone state model, not live game validation',
              'records': records, 'dll_sha256': hashlib.sha256(raw).hexdigest(),
              'runtime_status': 'NOT_TESTED', 'engine_profile_sha256': '8a6d468059394bf4cfce32f11dcba12ef45de88da1373084d5a2916d0bf7ba86'}
    target = ROOT / 'reports/c_session_plugin_build.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert json.loads(target.read_text(encoding='utf-8')) == report
    print('PASS x86 helper built: ' + str(dll))
    print('DLL SHA256 ' + report['dll_sha256'])


if __name__ == '__main__':
    main()
