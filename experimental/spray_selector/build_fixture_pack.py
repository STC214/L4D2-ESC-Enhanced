"""Build only self-authored numbered textures; no existing spray assets read."""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import struct
import sys

from PIL import Image, ImageDraw, ImageFont
from catalog import fixtures

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from vpk import read, write
from kv_audit import parse, scalars

OUT = ROOT / 'dist/spray_selector_prototype'
REPORT = ROOT / 'reports/spray_selector'
VPK = OUT / 'CSP_Numbered_Test_Assets.vpk'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def texture(number):
    image = Image.new('RGBA', (256, 256), ((number * 43) % 150 + 30, (number * 71) % 150 + 30, (number * 97) % 150 + 30, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, 247, 247), outline='white', width=5)
    font = ImageFont.truetype(str(Path(r'C:\Windows\Fonts\consolab.ttf')), 86)
    small = ImageFont.truetype(str(Path(r'C:\Windows\Fonts\consolab.ttf')), 21)
    draw.text((128, 125), f'{number:03}', font=font, anchor='mm', fill='white', stroke_width=2, stroke_fill='black')
    draw.text((128, 208), 'CSP TEST ONLY', font=small, anchor='mm', fill='white')
    header = bytearray(80)
    struct.pack_into('<4sIIIHHIHH', header, 0, b'VTF\0', 7, 2, 80, 256, 256, 0x030c, 1, 0)
    struct.pack_into('<fff', header, 32, .3, .3, .3)
    struct.pack_into('<fI', header, 48, 1.0, 0)  # RGBA8888
    header[56] = 1  # one mip
    struct.pack_into('<I', header, 57, 0xFFFFFFFF)  # no low-resolution thumbnail
    struct.pack_into('<H', header, 63, 1)  # depth
    return bytes(header) + image.tobytes(), image


def validate(files, catalog):
    assert len(files) == 122
    assert not any('sprays_manifest' in name or name.endswith('.res') for name in files)
    for entry in catalog.entries:
        raw = files[entry.texture]
        assert raw[:4] == b'VTF\0' and struct.unpack_from('<III', raw, 4) == (7, 2, 80)
        assert struct.unpack_from('<HH', raw, 16) == (256, 256)
        assert struct.unpack_from('<I', raw, 52)[0] == 0 and raw[56] == 1
        assert len(raw) == 80 + 256 * 256 * 4
        assert set(raw[83::4]) == {255}
        for path in (entry.texture[:-4] + '.vmt', 'materials/vgui/logos/ui/' + entry.native_name + '.vmt'):
            nodes = parse(files[path].decode('utf-8'))
            props = scalars(nodes[0].value)
            assert 'materials/' + props['$basetexture'] + '.vtf' == entry.texture
    tree = parse(files['addoninfo.txt'].decode('utf-8'))
    assert scalars(tree[0].value)['addonsteamappid'] == '550'
    assert json.loads(files['scripts/csp_test/catalog.json'])['entries'] == [asdict(entry) for entry in catalog.entries]


def main():
    catalog = fixtures()
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    protected = (ROOT / 'dist/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk', ROOT / 'dist/c_session_helper/CSessionDefaults.dll')
    before = {str(path): sha(path.read_bytes()) for path in protected}
    files, preview = {}, Image.new('RGB', (8 * 128, 5 * 128), 'black')
    for number, entry in enumerate(catalog.entries, 1):
        raw, image = texture(number)
        files[entry.texture] = raw
        preview.paste(image.resize((128, 128)).convert('RGB'), (((number - 1) % 8) * 128, ((number - 1) // 8) * 128))
        base = entry.native_name
        files[entry.texture[:-4] + '.vmt'] = (
            '"LightmappedGeneric"\n{\n"$basetexture" "vgui/logos/' + base + '"\n"$translucent" "1"\n"$decal" "1"\n}\n').encode()
        files['materials/vgui/logos/ui/' + base + '.vmt'] = (
            '"UnlitGeneric"\n{\n"$basetexture" "vgui/logos/' + base + '"\n"$translucent" "1"\n"$vertexcolor" "1"\n"$vertexalpha" "1"\n"$ignorez" "1"\n}\n').encode()
    manifest = dict(version='0.1.0', kind='Numbered test assets, NOT a functioning selector UI', page_size=12,
                    entries=[asdict(entry) for entry in catalog.entries])
    files['scripts/csp_test/catalog.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    files['addoninfo.txt'] = b'"AddonInfo"\n{\n"addonSteamAppID" "550"\n"addontitle" "CSP numbered test assets 0.1.0"\n"addonversion" "0.1.0"\n"addonauthor" "Local numbered fixtures"\n"addonContent_Spray" "1"\n"addonDescription" "40 self-authored numbered textures; no selector menu or automatic application yet."\n}\n'
    validate(files, catalog)
    write(VPK, files)
    assert read(VPK) == files
    validate(read(VPK), catalog)
    duplicate = REPORT / 'fixture_replayed.vpk'
    write(duplicate, files)
    assert duplicate.read_bytes() == VPK.read_bytes()
    preview.save(OUT / 'numbered_contact_sheet.png')
    with Image.open(OUT / 'numbered_contact_sheet.png') as check:
        check.load()
        assert check.size == (1024, 640)
    assert before == {str(path): sha(path.read_bytes()) for path in protected}
    report = dict(status='PASS', scope='VPK CRC/readback, VTF header/payload, VMT references, deterministic replay; engine rendering not tested',
                  artifact=str(VPK), sha256=sha(VPK.read_bytes()), members=len(files), numbered_textures=40,
                  native_manifest_overridden=False, C_artifacts_unchanged=before,
                  files={name: sha(data) for name, data in files.items()},
                  deploy_status='NOT_DEPLOYED', runtime='UI/plugin not built yet; resource fixture pack only')
    (REPORT / 'fixture_pack.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    assert json.loads((REPORT / 'fixture_pack.json').read_text(encoding='utf-8')) == report
    print('PASS 40 numbered VTFs + 40 world VMTs + 40 UI VMTs; 122 CRC members; all references resolve')
    print('PASS deterministic rebuild and C artifacts unchanged; NOT a selector UI, NOT deployed')
    print(VPK)


if __name__ == '__main__':
    main()
