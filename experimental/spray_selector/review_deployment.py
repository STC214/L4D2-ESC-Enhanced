"""Record the real CSP test deployment and a read-only rollback preview."""

import json
from pathlib import Path
import subprocess
import sys

from deploy import ROOT, WORK, JOURNAL, VPK, DLL, sha, save


def main():
    commands = ('preflight', 'deploy', 'verify', 'rollback-preview')
    report = dict(scope='CSP file deployment only; real game clicks/rendering pending', records=[], runtime='NOT_TESTED')
    output = WORK / 'verification.json'
    try:
        for action in commands:
            command = [sys.executable, '-B', '-X', 'utf8', str(Path(__file__).with_name('deploy.py')), action]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
            report['records'].append(dict(command=command, cwd=str(ROOT), stdout=result.stdout,
                                          stderr=result.stderr, exit_status=result.returncode))
            print(result.stdout + result.stderr, end='', flush=True)
            assert result.returncode == 0, 'Deployment step failed; inspect report and transaction journal'
        report['status'] = 'INSTALLED_FILES_VERIFIED_RUNTIME_PENDING'
        report['transaction'] = json.loads(JOURNAL.read_text(encoding='utf-8'))
        report['artifacts'] = {str(path.relative_to(ROOT)): sha(path) for path in (VPK, DLL, JOURNAL)}
        report['rollback_command'] = 'python -B -X utf8 experimental/spray_selector/deploy.py rollback'
    except BaseException as error:
        report['status'] = 'FAILED'
        report['error'] = repr(error)
        raise
    finally:
        save(output, report)
    print('RECORD', output)


if __name__ == '__main__':
    main()
