"""Record repeatable importer tests and a retained self-authored demonstration build."""

import json
from pathlib import Path
import subprocess
import sys
import uuid

from PIL import Image, ImageDraw
import spray_importer as tool
from c_session_release import save, sha
from vpk import read


def main():
    work = tool.ROOT / 'reports/spray_importer'
    work.mkdir(parents=True, exist_ok=True)
    guards = tool.protected(tool.GAME)
    guards[str(tool.BASE)] = sha(tool.BASE)
    commands = [[sys.executable, '-B', '-X', 'utf8', 'tools/test_spray_importer.py']] * 2
    commands.append([sys.executable, '-B', '-X', 'utf8', '-c',
                     "import sys;sys.path.insert(0,'tools');import spray_importer;spray_importer.gui(smoke=True)"])
    records = []
    for command in commands:
        result = subprocess.run(command, cwd=tool.ROOT, capture_output=True, text=True, encoding='utf-8')
        records.append(dict(command=command, input='none; synthetic fixture images',
                            stdout=result.stdout, stderr=result.stderr, exit_status=result.returncode))
        save(work / 'verification.json', dict(status='RUNNING', records=records))
        print('EXIT', result.returncode, ' '.join(command))
        assert result.returncode == 0, result.stderr
    home = work / 'demo' / uuid.uuid4().hex
    home.mkdir(parents=True)
    source = home / 'own_demo.png'
    image = Image.new('RGBA', (256, 256), (24, 110, 155, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((24, 24, 231, 231), outline='white', width=8)
    draw.text((75, 115), 'OWN DEMO 017', fill='white')
    image.save(source)
    tool.import_image(source, 17, home)
    folder = tool.build(home)
    before, after = read(tool.BASE), read(folder / tool.VPK_NAME)
    differences = [name for name in before if before[name] != after[name]]
    assert differences == [tool.PREFIX + 'test_017.vtf']
    patch = dict(baseline=sha(tool.BASE), modified=sha(folder / tool.VPK_NAME), changed= differences,
                 unchanged_members=len(before) - len(differences), manifest=str(folder / 'manifest.json'))
    save(home / 'patch.json', patch)
    assert all(sha(Path(path)) == digest for path, digest in guards.items())
    report = dict(status='TWO_TEST_ROUNDS_AND_GUI_SMOKE_PASS', records=records,
                  demo=str(folder), patch=str(home / 'patch.json'), protected=guards,
                  source_sha256={name: sha(tool.ROOT / name) for name in (
                      'tools/spray_importer.py', 'tools/test_spray_importer.py',
                      'tools/review_spray_importer.py', '启动喷漆导入工具.cmd')},
                  scope='15 tests twice; fixture deployment/rollback; Tk layout smoke; no real-game writes',
                  pending='User image visual/game test and manual GUI clicks; no new deployment')
    save(work / 'verification.json', report)
    assert json.loads((work / 'verification.json').read_text(encoding='utf-8')) == report
    print('PASS 15 tests twice + GUI smoke; demo VPK changes only slot 017; real game untouched')
    print(folder)


if __name__ == '__main__':
    main()
