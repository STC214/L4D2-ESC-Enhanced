"""Record literal prototype tests and prove existing C/game files stay intact."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'reports/spray_selector'
GAME = Path(r'E:\SteamLibrary\steamapps\common\Left 4 Dead 2')
NAME = '【00】C_ESC_LED_血条和速度_TUMTaRA.vpk'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot():
    paths = (ROOT / 'dist' / NAME, ROOT / 'dist/c_session_helper/CSessionDefaults.dll',
             GAME / 'left4dead2/addons' / NAME, GAME / 'bin/neko/plugins/CSessionDefaults.dll',
             GAME / 'bin/gameui.dll')
    return {str(path): sha(path) for path in paths}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).resolve().parent
    sources = {str(path.relative_to(ROOT)): sha(path) for path in sorted(source.rglob('*'))
               if path.is_file() and path.suffix in ('.py', '.cpp', '.h')}
    report = dict(scope='Phase 2 static UI/native fixtures; no UI/plugin deployment', before=snapshot(), records=[],
                  source_hashes=sources, rounds=[])
    try:
        for number in (1, 2):
            for name in ('test_catalog.py', 'prove_native_apply.py', 'prove_string_abi.py', 'prove_flyout_layout.py', 'build_fixture_pack.py',
                         'build_native.py', 'build_selector.py', 'test_selector.py', 'test_deploy.py'):
                command = [sys.executable, '-B', '-X', 'utf8', str(source / name)]
                result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
                record = dict(round=number, command=command, cwd=str(ROOT), stdout=result.stdout, stderr=result.stderr, exit_status=result.returncode)
                report['records'].append(record)
                assert result.returncode == 0, record
                print(f'PASS round={number} exit=0 {name}', flush=True)
            report['rounds'].append({str(path.relative_to(ROOT)): sha(path) for path in (
                ROOT / 'dist/spray_selector_prototype/CSP_Numbered_Selector_TEST.vpk',
                ROOT / 'dist/spray_selector_prototype/native/CSPSelector.dll',
                ROOT / 'dist/spray_selector_prototype/CSP_Numbered_Selector_TEST.zip')})
        assert report['rounds'][0] == report['rounds'][1], 'Native/UI package rebuild drift'
        assert sources == {str(path.relative_to(ROOT)): sha(path) for path in sorted(source.rglob('*'))
                           if path.is_file() and path.suffix in ('.py', '.cpp', '.h')}
        report['after'] = snapshot()
        assert report['after'] == report['before']
        paths = (OUT / 'native_apply.json', OUT / 'string_abi.json', OUT / 'flyout_layout.json', OUT / 'fixture_pack.json', OUT / 'native_build.json', OUT / 'selector_build.json',
                 ROOT / 'dist/spray_selector_prototype/CSP_Numbered_Test_Assets.vpk',
                 ROOT / 'dist/spray_selector_prototype/numbered_contact_sheet.png',
                 ROOT / 'dist/spray_selector_prototype/CSP_Numbered_Selector_TEST.zip')
        report['artifacts'] = {str(path.relative_to(ROOT)): sha(path) for path in paths}
        report['status'] = 'PHASE_2_TWO_STATIC_ROUNDS_PASS_RUNTIME_PENDING'
        report['remaining'] = ['Live window-thread bootstrap and Flyout routing',
                               'Real engine setter/readback and preview rendering', 'Persistence and per-map behavior',
                               'Install/conflict/rollback fixtures and opt-in deployment']
    except BaseException as error:
        report['status'] = 'FAILED'
        report['error'] = repr(error)
        raise
    finally:
        target = OUT / 'verification.json'
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        assert json.loads(target.read_text(encoding='utf-8')) == report
    print('PASS two deterministic rounds: 31 Python tests, native selection/layout replays, x86 hook/string/viewport/ABI fixtures and UI pair ZIP')
    print('Existing C/game hashes unchanged; real UI routing/rendering/persistence pending; nothing deployed')


if __name__ == '__main__':
    main()
