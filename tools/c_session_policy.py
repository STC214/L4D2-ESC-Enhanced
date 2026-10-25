"""C policy: defaults belong to a connection session, never to ESC creation."""

import hashlib

from inspect_menu import blocks, fields
from prepare_menu_patch import set_fields
from release_paths import ROOT
from vpk import read


BASE = ROOT / 'originals/C_before_session_defaults.vpk'
BASE_HASH = '97fa1e054d0676042b9da149b421e645aad493160db98b7f04668a2503e463da'
MENU = 'resource/ui/l4d360ui/ingamemainmenu.res'
CFG = 'cfg/l4d2esc_defaults.cfg'
FLASHLIGHT_FOV_DEFAULT = '53'


def transform_menu(content):
    text = content.decode('utf-8-sig')
    removed = set()
    for name, start, end, block in reversed(blocks(text)):
        if name.startswith('Init_'):
            text = text[:start] + text[end:]
            removed.add(name)
        elif name == 'Flashlightfov':
            # Old minimum 100 would clamp native default 53 on reopening ESC.
            text = text[:start] + set_fields(block, {'minvalue': '50'}) + text[end:]
    assert len(removed) == 12
    return text.encode('utf-8')


def apply(files):
    result = dict(files)
    result[MENU] = transform_menu(result[MENU])
    return result


def validate(files, width=1280, height=720):
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == BASE_HASH
    before = read(BASE)
    assert set(files) == set(before), 'Session policy must not alter HUD/resource inventory'
    changed = {name for name in before if before[name] != files[name]}
    assert {MENU, CFG} <= changed
    assert changed <= {MENU, CFG, 'resource/ui/l4d360ui/dropdownnetgraph.res'}
    old = {n: fields(b) for n, _, _, b in blocks(before[MENU].decode('utf-8-sig'))}
    new = {n: fields(b) for n, _, _, b in blocks(files[MENU].decode('utf-8-sig'))}
    assert set(new) == {n for n in old if not n.startswith('Init_')}
    for name, props in new.items():
        expected = dict(old[name])
        if name == 'Flashlightfov':
            expected['minvalue'] = '50'
        if name == 'Expanded_SldHeight':
            expected['maxvalue'] = str(height - 100)
        assert props == expected, name
    for name in ('Flashlightfov', 'GuangSheJiao'):
        assert new[name]['concommand'] == 'r_flashlightfov'
        assert float(new[name]['minvalue']) <= 53 <= float(new[name]['maxvalue'])
    cfg = files[CFG].decode('utf-8')
    assert '\nr_flashlightfov 53\n' in cfg
    assert '\nr_flashlightfov 200\n' not in cfg
    print('PASS no ESC initializer controls; both shared flashlight controls accept native default 53')
    print('PASS session policy modifies only ESC/default cfg and optional network-height profile')
