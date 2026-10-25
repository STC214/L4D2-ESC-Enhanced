"""Record exact baseline/tests/deploy/verify commands for the selected game."""

import argparse
import datetime
import subprocess
import sys

from deploy_evolved_minimap import BUNDLE, JOURNAL, PLAN, PROFILE, ROOT, WORK, load, save, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--deploy', action='store_true')
    args = parser.parse_args()
    records = []
    commands = [
        ['tools/verify_evolved_minimap.py', '--baseline'],
        ['tools/verify_evolved_minimap.py', '--tests'],
    ]
    if args.deploy:
        commands.extend([
            ['tools/deploy_evolved_minimap.py', 'apply'],
            ['tools/verify_evolved_minimap.py'],
            ['tools/deploy_evolved_minimap.py', 'rollback-check'],
            ['tools/deploy_evolved_minimap.py', 'apply'],
        ])
    report = {'scope': 'static checks and actual file deployment only; game not launched',
              'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'inputs': {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in (PLAN, BUNDLE, PROFILE)},
              'records': records, 'runtime_status': 'NOT_TESTED', 'rollback_execution': 'preview_only'}
    record_path = WORK / ('verification.json' if args.deploy else 'preflight_verification.json')
    try:
        for arguments in commands:
            command = [sys.executable, '-X', 'utf8', *arguments]
            process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
            records.append({'cwd': str(ROOT), 'command': command, 'stdout': process.stdout,
                            'stderr': process.stderr, 'exit_status': process.returncode})
            print(subprocess.list2cmdline(command))
            print(process.stdout, end='')
            print(process.stderr, end='')
            assert process.returncode == 0, 'Command failed; review transaction and evidence'
        report['status'] = 'FILES_VERIFIED_RUNTIME_PENDING' if args.deploy else 'PREFLIGHT_PASSED'
        artifacts = [BUNDLE, PLAN, PROFILE, WORK / 'config.patch', ROOT / 'tools/deploy_evolved_minimap.py']
        if JOURNAL.exists():
            artifacts.append(JOURNAL)
        report['artifacts'] = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in artifacts}
    except Exception as exc:
        report['status'] = 'FAILED'
        report['failure'] = str(exc)
        raise
    finally:
        save(record_path, report)
    assert load(record_path) == report
    print('RECORD ' + str(record_path))


if __name__ == '__main__':
    main()
