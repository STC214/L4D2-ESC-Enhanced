"""Build isolated x86 CSP fixtures/plugin; does not touch C's native outputs."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).resolve().parent / 'native'
OUT = ROOT / 'dist/spray_selector_prototype/native'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tests-only', action='store_true')
    args = parser.parse_args()
    vc = Path(r'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.44.35207')
    sdk = Path(r'C:\Program Files (x86)\Windows Kits\10')
    version = '10.0.26100.0'
    env = dict(os.environ)
    env['PATH'] = str(vc / 'bin/Hostx64/x86') + os.pathsep + env.get('PATH', '')
    env['INCLUDE'] = ';'.join(map(str, (vc / 'include', sdk / 'Include' / version / 'ucrt', sdk / 'Include' / version / 'shared', sdk / 'Include' / version / 'um')))
    env['LIB'] = ';'.join(map(str, (vc / 'lib/x86', sdk / 'Lib' / version / 'ucrt/x86', sdk / 'Lib' / version / 'um/x86')))
    OUT.mkdir(parents=True, exist_ok=True)
    common = [str(vc / 'bin/Hostx64/x86/cl.exe'), '/nologo', '/std:c++17', '/W4', '/WX', '/EHsc', '/MT', '/Brepro']
    commands = [common + [str(SOURCE / 'test_bridge.cpp'), '/Fo' + str(OUT / 'test_bridge.obj'), '/Fe' + str(OUT / 'test_bridge.exe'), '/link', '/Brepro', '/MACHINE:X86'],
                [str(OUT / 'test_bridge.exe')],
                common + [str(SOURCE / 'test_apply.cpp'), '/Fo' + str(OUT / 'test_apply.obj'), '/Fe' + str(OUT / 'test_apply.exe'), '/link', '/Brepro', '/MACHINE:X86'],
                [str(OUT / 'test_apply.exe')],
                common + [str(SOURCE / 'test_viewport.cpp'), '/Fo' + str(OUT / 'test_viewport.obj'), '/Fe' + str(OUT / 'test_viewport.exe'), '/link', '/Brepro', '/MACHINE:X86', 'user32.lib'],
                [str(OUT / 'test_viewport.exe')]]
    if not args.tests_only:
        commands.append(common + ['/LD', str(SOURCE / 'plugin.cpp'), '/Fo' + str(OUT / 'plugin.obj'), '/Fe' + str(OUT / 'CSPSelector.dll'), '/link', '/Brepro', '/MACHINE:X86', 'user32.lib', 'bcrypt.lib'])
        commands.extend([
            common + [str(SOURCE / 'test_contract.cpp'), '/Fo' + str(OUT / 'test_contract.obj'), '/Fe' + str(OUT / 'test_contract.exe'), '/link', '/Brepro', '/MACHINE:X86'],
            [str(OUT / 'test_contract.exe'), str(OUT / 'CSPSelector.dll')],
        ])
    records = []
    try:
        for command in commands:
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, errors='replace')
            records.append(dict(command=command, stdout=result.stdout, stderr=result.stderr, exit_status=result.returncode))
            print(result.stdout + result.stderr, end='', flush=True)
            assert result.returncode == 0, 'Native build/test failed'
    finally:
        report = dict(records=records, tests_only=args.tests_only, runtime='NOT_TESTED',
                      files={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('*') if p.suffix in ('.exe', '.dll')})
        target = ROOT / 'reports/spray_selector/native_build.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        assert json.loads(target.read_text(encoding='utf-8')) == report


if __name__ == '__main__':
    main()
