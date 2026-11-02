"""Build a separate 40-item, four-page Source UI prototype plus L4N helper."""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from catalog import fixtures

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from inspect_menu import blocks, fields
from prepare_menu_patch import set_fields
from kv_audit import parse, scalars
from vpk import read, write

OUT = ROOT / 'dist/spray_selector_prototype'
REPORT = ROOT / 'reports/spray_selector'
MULTIPLAYER = 'resource/ui/l4d360ui/multiplayer.res'
SEED = ROOT / 'reports/spray_menu_native/update' / MULTIPLAYER
VPK = OUT / 'CSP_Numbered_Selector_TEST.vpk'
DLL = OUT / 'native/CSPSelector.dll'
ZIP = OUT / 'CSP_Numbered_Selector_TEST.zip'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def node(name, **props):
    assert '"' not in name
    lines = [f'"{name}"', '{']
    for key, value in props.items():
        assert '"' not in str(value) and '\n' not in str(value)
        lines.append(f'    "{key}" "{value}"')
    return '\n'.join(lines + ['}'])


def button(name, label, command, x, y, width=100, navup=None, navdown=None):
    props = dict(controlname='L4D360HybridButton', fieldname=name, xpos=x, ypos=y, wide=width, tall=20,
                 visible=1, enabled=1, labeltext=label, style='SmallButton', command=command,
                 activationtype=0, onlyactiveuser=1)
    if navup:
        props['navup'] = navup
    if navdown:
        props['navdown'] = navdown
    return node(name, **props)


def frame(name, title, content, height=330):
    bg = node('CSPBackground', controlname='Panel', fieldname='CSPBackground', xpos=0, ypos=0,
              wide=450, tall=height, visible=1, enabled=1, paintbackground=1, paintbackgroundtype=0,
              bgcolor_override='0 0 0 245', zpos=-1)
    heading = node('CSPHeading', controlname='Label', fieldname='CSPHeading', xpos=12, ypos=5,
                   wide=426, tall=20, visible=1, labeltext=title)
    return ('"' + name + '"\n{\n' + '\n'.join([bg, heading, *content]) + '\n}\n').encode()


def build_files():
    catalog = fixtures()
    files = read(OUT / 'CSP_Numbered_Test_Assets.vpk')
    seed = SEED.read_bytes()
    inspection = json.loads((ROOT / 'reports/spray_menu_native/inspection.json').read_text(encoding='utf-8'))
    expected = next(item['sha256'] for item in inspection['resources'] if item['member'] == MULTIPLAYER and '\\update\\' in item['pak'])
    assert sha(seed) == expected, 'Seed must match inspected native multiplayer menu'
    text = seed.decode('utf-8-sig')
    for name, start, end, block in reversed(blocks(text)):
        changes = {'navdown': 'DrpCSPSelector'} if name == 'BtnBrowseSpraypaint' else {'navup': 'DrpCSPSelector'} if name == 'DrpColorBlind' else {}
        if changes:
            text = text[:start] + set_fields(block, changes) + text[end:]
    additions = []
    dropdown = node('DrpCSPSelector', controlname='DropDownMenu', fieldname='DrpCSPSelector', xpos='c-100',
                    ypos=226, wide=280, tall=20, zpos=3, visible=1, enabled=1, navup='BtnBrowseSpraypaint',
                    navdown='DrpColorBlind')
    opening = button('BtnDropButton', 'CSP TEST: select numbered spray', 'FlmCSPPage1', 0, 0, 280)
    additions.append(dropdown[:-1] + opening + '\n}')
    for page in range(catalog.pages):
        entries = catalog.page(page)
        widgets = []
        for index, entry in enumerate(entries):
            number = page * 12 + index + 1
            column, row = index % 4, index // 4
            x, y = 12 + column * 108, 32 + row * 83
            widgets.append(node(f'CSPPreview{number:03}', controlname='ImagePanel', fieldname=f'CSPPreview{number:03}',
                                xpos=x + 10, ypos=y, wide=80, tall=58, visible=1, scaleimage=1,
                                image='logos/ui/' + entry.native_name))
            previous = entries[(index - 1) % len(entries)].identifier.removeprefix('test_')
            following = entries[(index + 1) % len(entries)].identifier.removeprefix('test_')
            widgets.append(button(f'CSPPick{number:03}', entry.title, f'FlmCSPConfirm{number:03}', x, y + 58,
                                  navup='CSPClose' if index == 0 else 'CSPPick' + previous,
                                  navdown='CSPPrevPage' if index == len(entries) - 1 else 'CSPPick' + following))
            confirm = [node('CSPConfirmPreview', controlname='ImagePanel', fieldname='CSPConfirmPreview',
                            xpos=145, ypos=35, wide=160, tall=160, visible=1, scaleimage=1,
                            image='logos/ui/' + entry.native_name),
                       button(f'CSPApply{number:03}', 'Apply and return', f'CSP_TEST_APPLY_{number:03}', 40, 210, 170,
                              navup='CSPCancel', navdown='CSPCancel'),
                       button('CSPCancel', 'Cancel / page', f'FlmCSPPage{page + 1}', 240, 210, 170,
                              navup=f'CSPApply{number:03}', navdown=f'CSPApply{number:03}')]
            confirm_path = f'resource/ui/csp_test/confirm_{number:03}.res'
            files[confirm_path] = frame(f'CSPConfirm{number:03}', 'Confirm ' + entry.title + ' (numbered fixture)', confirm, height=245)
            additions.append(node(f'FlmCSPConfirm{number:03}', controlname='FlyoutMenu', fieldname=f'FlmCSPConfirm{number:03}',
                                  visible=0, wide=450, tall=245, zpos=5, initialfocus=f'CSPApply{number:03}', resourcefile=confirm_path,
                                  onlyactiveuser=1))
        prev = max(0, page - 1) + 1
        nxt = min(catalog.pages - 1, page + 1) + 1
        widgets.extend([button('CSPPrevPage', 'Previous', f'FlmCSPPage{prev}', 12, 300, navup=f'CSPPick{page * 12 + 1:03}', navdown='CSPNextPage'),
                        button('CSPNextPage', 'Next', f'FlmCSPPage{nxt}', 174, 300, navup='CSPPrevPage', navdown='CSPClose'),
                        button('CSPClose', 'Return', 'Back', 336, 300, navup='CSPNextPage', navdown=f'CSPPick{page * 12 + 1:03}')])
        page_path = f'resource/ui/csp_test/page_{page + 1}.res'
        files[page_path] = frame(f'CSPPage{page + 1}', f'Numbered sprays - page {page + 1}/{catalog.pages} (choose then confirm)', widgets)
        additions.append(node(f'FlmCSPPage{page + 1}', controlname='FlyoutMenu', fieldname=f'FlmCSPPage{page + 1}',
                              visible=0, wide=450, tall=330, zpos=4, initialfocus=f'CSPPick{page * 12 + 1:03}', resourcefile=page_path,
                              onlyactiveuser=1))
    last = text.rfind('}')
    files[MULTIPLAYER] = (text[:last] + '\n' + '\n'.join(additions) + '\n' + text[last:]).encode()
    files['addoninfo.txt'] = b'"AddonInfo" { "addonSteamAppID" "550" "addontitle" "CSP numbered selector TEST 0.2.3" "addonversion" "0.2.3" "addonContent_Spray" "1" "addonDescription" "Prototype: verified native IConVar string slot 3. Requires CSPSelector.dll 0.2.3 and existing L4N. Live spray validation pending." }'
    return files


def validate(files):
    catalog = fixtures()
    assert len(files) == 167
    assert not any('sprays_manifest' in name for name in files)
    root = parse(files[MULTIPLAYER].decode())[0]
    controls = {item.key: scalars(item.value) for item in root.value if isinstance(item.value, list)}
    assert 'DrpCSPSelector' in controls and controls['BtnBrowseSpraypaint']['navdown'] == 'DrpCSPSelector'
    assert controls['DrpColorBlind']['navup'] == 'DrpCSPSelector'
    current_blocks = {name: block for name, _, _, block in blocks(files[MULTIPLAYER].decode())}
    for name, _, _, block in blocks(SEED.read_bytes().decode('utf-8-sig')):
        changes = {'navdown': 'DrpCSPSelector'} if name == 'BtnBrowseSpraypaint' else {'navup': 'DrpCSPSelector'} if name == 'DrpColorBlind' else {}
        assert current_blocks[name] == set_fields(block, changes), 'Unrelated native menu block changed: ' + name
    for control in controls.values():
        if control.get('controlname') == 'FlyoutMenu' and control.get('fieldname', '').startswith('FlmCSP'):
            assert control['resourcefile'] in files
            target = {name: fields(block) for name, _, _, block in blocks(files[control['resourcefile']].decode())}
            assert control['initialfocus'] in target
            # Custom grids intentionally use a visual CSPBackground, not the
            # native PnlBackground/list autosizing and 0.7 button-Y transform.
            background = target['CSPBackground']
            assert (control['wide'], control['tall']) == (background['wide'], background['tall'])
            assert int(control['wide']) > 0 and int(control['tall']) > 0, 'Invisible zero-sized popup'
    for page in range(catalog.pages):
        resource = files[f'resource/ui/csp_test/page_{page + 1}.res'].decode()
        nodes = {name: fields(block) for name, _, _, block in blocks(resource)}
        picks = [name for name in nodes if name.startswith('CSPPick')]
        assert len(picks) == len(catalog.page(page))
        for props in nodes.values():
            if props.get('controlname') != 'Panel':
                assert 0 <= int(props['xpos']) <= 450 - int(props['wide'])
                assert 0 <= int(props['ypos']) <= 330 - int(props['tall'])
            for key in ('navup', 'navdown'):
                assert key not in props or props[key] in nodes
            if props.get('controlname') == 'ImagePanel':
                assert props['image'].startswith('logos/ui/') and not props['image'].startswith('vgui/')
                assert 'materials/vgui/' + props['image'] + '.vmt' in files
        reached, pending = set(), [f'CSPPick{page * 12 + 1:03}']
        while pending:
            name = pending.pop()
            if name not in reached:
                reached.add(name)
                pending.extend(nodes[name][key] for key in ('navup', 'navdown') if key in nodes[name])
        assert reached == set(picks) | {'CSPPrevPage', 'CSPNextPage', 'CSPClose'}, 'Keyboard navigation must reach page controls'
        for entry in catalog.page(page):
            number = int(entry.identifier[-3:])
            assert nodes[f'CSPPick{number:03}']['command'] == f'FlmCSPConfirm{number:03}'
            confirm = {name: fields(block) for name, _, _, block in blocks(files[f'resource/ui/csp_test/confirm_{number:03}.res'].decode())}
            assert confirm[f'CSPApply{number:03}']['command'] == f'CSP_TEST_APPLY_{number:03}'
            assert confirm['CSPCancel']['command'] == f'FlmCSPPage{page + 1}'
            assert confirm['CSPConfirmPreview']['image'] == 'logos/ui/' + entry.native_name
    c_files = read(ROOT / 'dist/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk')
    assert set(c_files) & set(files) == {'addoninfo.txt'}, 'Unexpected resource collision with C'


def main():
    files = build_files()
    validate(files)
    write(VPK, files)
    assert read(VPK) == files
    validate(read(VPK))
    built = json.loads((REPORT / 'native_build.json').read_text(encoding='utf-8'))
    assert not built['tests_only'] and all(item['exit_status'] == 0 for item in built['records'])
    assert sha(DLL.read_bytes()) == built['files']['CSPSelector.dll']
    payload = {'left4dead2/addons/' + VPK.name: VPK.read_bytes(), 'bin/neko/plugins/CSPSelector.dll': DLL.read_bytes()}
    manifest = dict(version='0.2.3', helper_version='0.2.3', runtime='NOT_TESTED', entries=40, page_size=12, ui='Options > Multiplayer > CSP TEST',
                    requires='Existing x86 L4N; exact pinned GameUI/engine/vstdlib', persistence='NOT_IMPLEMENTED',
                    files={name: sha(data) for name, data in payload.items()})
    payload['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    with zipfile.ZipFile(ZIP, 'w') as archive:
        for name, data in sorted(payload.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    with zipfile.ZipFile(ZIP) as archive:
        assert archive.testzip() is None and {name: archive.read(name) for name in archive.namelist()} == payload
    report = dict(status='STATIC_BUILD_PASS_RUNTIME_PENDING', vpk=str(VPK), zip=str(ZIP), members=len(files),
                  hashes={p.name: sha(p.read_bytes()) for p in (VPK, DLL, ZIP)}, menu_override=MULTIPLAYER,
                  pages=4, confirmations=40, entries=[asdict(item) for item in fixtures().entries],
                  runtime='No live window/click/render/network/persistence verification; NOT_DEPLOYED')
    (REPORT / 'selector_build.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert json.loads((REPORT / 'selector_build.json').read_text(encoding='utf-8')) == report
    print('PASS 4 pages / 40 confirmation screens / commands / references / navigation / 167 VPK members / DLL pair ZIP')
    print('NOT DEPLOYED; native Flyout routing, actual game setter/rendering and persistence remain pending')


if __name__ == '__main__':
    main()
