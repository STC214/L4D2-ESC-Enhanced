"""Record baseline, current pair, actual deployment and rollback preview."""

import argparse
import shutil
import subprocess
import sys
import uuid

from c_session_release import BUNDLE, DLL, JOURNAL, OUTPUT, ROOT, WORK, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deploy', action='store_true')
    args = parser.parse_args()
    commands = [['tools/c_session_release.py', 'baseline'],
                ['tools/c_session_release.py', 'package'],
                ['tools/c_session_release.py', 'rollback-copy']]
    if args.deploy:
        commands += [['tools/c_session_release.py', 'deploy'],
                     ['tools/c_session_release.py', 'verify-installed'],
                     ['tools/c_session_release.py', 'rollback-preview']]
    report = {'scope': 'file installation and static checks; game not launched',
              'inputs': {str(p.relative_to(ROOT)): sha(p) for p in (OUTPUT, DLL, BUNDLE)},
              'records': [], 'runtime_status': 'NOT_TESTED', 'game_rollback': 'PREVIEW_ONLY'}
    record = WORK / ('verification.json' if args.deploy else 'preflight_verification.json')
    if args.deploy and record.exists():
        archived = WORK / 'reviews' / (uuid.uuid4().hex + '.json')
        archived.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(record, archived)
        assert sha(archived) == sha(record)
    try:
        for args_ in commands:
            command = [sys.executable, '-X', 'utf8', *args_]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
            report['records'].append({'cwd': str(ROOT), 'command': command, 'stdout': result.stdout,
                                      'stderr': result.stderr, 'exit_status': result.returncode})
            print(subprocess.list2cmdline(command))
            print(result.stdout, end='')
            print(result.stderr, end='')
            assert result.returncode == 0, 'Command failed; inspect recorded output before continuing'
        report['status'] = 'FILES_VERIFIED_RUNTIME_PENDING' if args.deploy else 'PREFLIGHT_PASSED'
        report['artifacts'] = {str(p.relative_to(ROOT)): sha(p) for p in (OUTPUT, DLL, BUNDLE)}
        if JOURNAL.exists():
            report['transaction_sha256'] = sha(JOURNAL)
    except Exception as exc:
        report['status'] = 'FAILED'
        report['failure'] = str(exc)
        raise
    finally:
        save(record, report)
    print('RECORD ' + str(record))


if __name__ == '__main__':
    main()
