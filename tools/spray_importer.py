"""40-slot CSP importer: static images, synchronized VPK/MOD assets, guarded rollback."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import uuid

from PIL import Image, ImageOps
from c_session_release import copy_verified, save, sha
from vpk import read, write

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experimental/spray_selector'))
from deploy import GAME, protected, stopped

HOME = ROOT / 'dist/spray_importer'
BASE = ROOT / 'dist/spray_selector_prototype/CSP_Numbered_Selector_TEST.vpk'
VPK_NAME = BASE.name
PREFIX = 'materials/vgui/logos/csp_test/'
SUFFIXES = {'.png', '.jpg', '.jpeg', '.bmp', '.tga', '.webp', '.vtf'}


def slot_number(slot):
    if type(slot) is not int or not 1 <= slot <= 40:
        raise ValueError('槽位必须为 1～40')
    return f'{slot:03}'


def decode_vtf(raw):
    if len(raw) < 64 or raw[:4] != b'VTF\0':
        raise ValueError('不是有效 VTF')
    major, minor, header = struct.unpack_from('<III', raw, 4)
    width, height, flags, frames = struct.unpack_from('<HHIH', raw, 16)
    fmt = struct.unpack_from('<I', raw, 52)[0]
    mips = raw[56]
    low_fmt = struct.unpack_from('<I', raw, 57)[0]
    depth = struct.unpack_from('<H', raw, 63)[0] if minor >= 2 and len(raw) >= 65 else 1
    if (major != 7 or minor > 5 or header < 64 or header > len(raw)
            or not 1 <= width <= 8192 or not 1 <= height <= 8192
            or frames != 1 or depth != 1 or flags & 0x4000
            or not 1 <= mips <= max(width, height).bit_length()):
        raise ValueError('仅支持单帧、二维、非环境贴图的 VTF 7.0～7.5')

    def size(w, h, kind):
        if kind in (13, 14, 15):
            return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * (8 if kind == 13 else 16)
        if kind in (0, 12):
            return w * h * 4
        if kind in (2, 3):
            return w * h * 3
        raise ValueError('VTF 像素格式未支持；请先导出为 PNG')

    start = header
    if minor >= 3:
        if header < 80:
            raise ValueError('VTF 资源表损坏')
        count = struct.unpack_from('<I', raw, 68)[0]
        if count > 32 or 80 + count * 8 > header:
            raise ValueError('VTF 资源表越界')
        matches = []
        for offset in range(80, 80 + count * 8, 8):
            if raw[offset:offset + 3] == b'\x30\0\0':
                if raw[offset + 3] & 2:
                    raise ValueError('VTF 图像资源不可内联')
                matches.append(struct.unpack_from('<I', raw, offset + 4)[0])
        if len(matches) != 1 or matches[0] < header:
            raise ValueError('VTF 高分辨率资源缺失或重复')
        start = matches[0]
    elif low_fmt != 0xFFFFFFFF and raw[61] and raw[62]:
        start += size(raw[61], raw[62], low_fmt)
    start += sum(size(max(1, width >> level), max(1, height >> level), fmt)
                 for level in range(1, mips))
    length = size(width, height, fmt)
    if start + length > len(raw):
        raise ValueError('VTF 图像数据被截断')
    data = raw[start:start + length]
    if fmt in (0, 2, 3, 12):
        mode, decoder = {0: ('RGBA', 'RGBA'), 2: ('RGB', 'RGB'),
                         3: ('RGB', 'BGR'), 12: ('RGBA', 'BGRA')}[fmt]
        return Image.frombytes(mode, (width, height), data, 'raw', decoder).convert('RGBA')
    # Let Pillow's DDS decoder handle standard block compression.
    dds = bytearray(128)
    dds[:4] = b'DDS '
    struct.pack_into('<7I', dds, 4, 124, 0x81007, height, width, length, 0, 1)
    struct.pack_into('<II4s', dds, 76, 32, 4, {13: b'DXT1', 14: b'DXT3', 15: b'DXT5'}[fmt])
    struct.pack_into('<I', dds, 108, 0x1000)
    with Image.open(io.BytesIO(bytes(dds) + data)) as image:
        return image.convert('RGBA')


def load_image(path):
    path = Path(path)
    if path.suffix.lower() not in SUFFIXES or path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('请选择不超过 32 MiB 的 PNG/JPG/BMP/TGA/WebP/VTF')
    if path.suffix.lower() == '.vtf':
        image = decode_vtf(path.read_bytes())
    else:
        with Image.open(path) as source:
            if getattr(source, 'n_frames', 1) != 1:
                raise ValueError('本版只导入静态图片')
            if max(source.size) > 8192:
                raise ValueError('图片边长超过 8192')
            image = ImageOps.exif_transpose(source).convert('RGBA')
    scaled = ImageOps.contain(image, (256, 256), Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    canvas.paste(scaled, ((256 - scaled.width) // 2, (256 - scaled.height) // 2))
    return canvas


def encode_vtf(image):
    if image.mode != 'RGBA' or image.size != (256, 256):
        raise ValueError('内部图像必须为 256×256 RGBA')
    header = bytearray(80)
    struct.pack_into('<4sIIIHHIHH', header, 0, b'VTF\0', 7, 2, 80, 256, 256, 0x230c, 1, 0)
    struct.pack_into('<fff', header, 32, .3, .3, .3)
    struct.pack_into('<fI', header, 48, 1., 0)
    header[56] = 1
    struct.pack_into('<I', header, 57, 0xFFFFFFFF)
    struct.pack_into('<H', header, 63, 1)
    raw = bytes(header) + image.tobytes()
    assert decode_vtf(raw).tobytes() == image.tobytes() and len(raw) < 512 * 1024
    return raw


def import_image(path, slot, home=HOME):
    number = slot_number(slot)
    image = load_image(path)
    # Keep immutable generations; reimport never destroys an earlier source.
    folder = home / 'imports' / uuid.uuid4().hex
    folder.mkdir(parents=True)
    image.save(folder / 'image.png')
    (folder / 'image.vtf').write_bytes(encode_vtf(image))
    state_path = home / 'slots.json'
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    state[number] = dict(title=Path(path).stem, image=str((folder / 'image.png').relative_to(home)),
                         texture=str((folder / 'image.vtf').relative_to(home)), sha256=sha(folder / 'image.vtf'))
    save(state_path, state)
    return folder / 'image.png'


def build(home=HOME, base=BASE):
    files = read(base)
    state = json.loads((home / 'slots.json').read_text(encoding='utf-8'))
    if not state:
        raise ValueError('请先导入至少一张图片')
    changed = {}
    for number, row in state.items():
        assert number == slot_number(int(number))
        source = (home / row['texture']).resolve()
        assert source.is_relative_to(home.resolve()) and sha(source) == row['sha256']
        raw = source.read_bytes()
        assert decode_vtf(raw).size == (256, 256)
        name = PREFIX + 'test_' + number + '.vtf'
        assert name in files
        files[name] = raw
        changed[number] = row['title']
    folder = home / 'builds' / uuid.uuid4().hex
    folder.mkdir(parents=True)
    output = folder / VPK_NAME
    write(output, files)
    assert read(output) == files
    original = read(base)
    assert set(files) == set(original)
    assert all(files[name] == data for name, data in original.items()
               if name not in {PREFIX + 'test_' + n + '.vtf' for n in state})
    # Existing VMTs already point at these stable slot paths; previews and world agree.
    payload = {name: data for name, data in files.items()
               if name.startswith(PREFIX) and Path(name).suffix in ('.vtf', '.vmt')}
    assert len(payload) == 80
    for name, data in payload.items():
        destination = folder / 'mod' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    manifest = dict(base_sha256=sha(base), vpk_sha256=sha(output), slots_sha256=sha(home / 'slots.json'), slots=changed,
                    files={name: sha(folder / 'mod' / name) for name in payload})
    save(folder / 'manifest.json', manifest)
    save(home / 'latest.json', dict(build=str(folder.relative_to(home))))
    return folder


def game_targets(game, folder):
    # Do not infer MOD from a different installation silently.
    from kv_audit import parse
    tree = parse((game / 'left4dead2/gameinfo.txt').read_text(encoding='utf-8'))[0]
    for key in ('filesystem', 'searchpaths'):
        tree = next(item for item in tree.value if item.key.casefold() == key)
    assert next(item.value for item in tree.value if item.key.casefold() == 'game') == 'update'
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    expected = {PREFIX + f'test_{n:03}' + ext for n in range(1, 41) for ext in ('.vtf', '.vmt')}
    assert set(manifest['files']) == expected
    packed = read(folder / VPK_NAME)
    assert all(hashlib.sha256(packed[name]).hexdigest() == digest
               for name, digest in manifest['files'].items()), 'VPK 与 MOD 素材不一致'
    sources = {'left4dead2/addons/' + VPK_NAME: (folder / VPK_NAME, manifest['vpk_sha256'])}
    for name, digest in manifest['files'].items():
        sources['update/' + name] = (folder / 'mod' / name, digest)
    for relative, (source, digest) in sources.items():
        path = game / relative
        assert path.resolve().is_relative_to(game.resolve()) and source.resolve().is_relative_to(folder.resolve())
        assert sha(source) == digest
        for parent in (path, *path.parents):
            assert not parent.is_symlink()
            if parent == game:
                break
        # Require the already installed working selector + MOD-path experiment.
        assert path.is_file(), f'请先安装并验证选择器基础组件：{path}'
    return sources


def deploy(folder, home=HOME, game=GAME, fixture=False):
    if not fixture:
        stopped()
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['slots_sha256'] == sha(home / 'slots.json'), '导入记录已更新，请重新构建后再部署'
    sources = game_targets(game, folder)
    guards = protected(game)
    guards.update({str(game / name): sha(game / name) for name in (
        'bin/engine.dll', 'bin/neko/plugins/CSPSelector.dll', 'left4dead2/cfg/config.cfg')
        if (game / name).exists()})
    transaction = home / 'transactions' / uuid.uuid4().hex
    transaction.mkdir(parents=True)
    rows = {}
    for relative, (source, digest) in sources.items():
        backup = transaction / 'before' / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes((game / relative).read_bytes())
        rows[relative] = dict(before=sha(backup), after=digest)
    journal = dict(game=str(game.resolve()), files=rows, guards=guards, status='PREPARED')
    save(transaction / 'transaction.json', journal)
    save(home / 'last_deploy.json', dict(transaction=str(transaction.relative_to(home))))
    for relative, (source, digest) in sources.items():
        assert sha(game / relative) == rows[relative]['before']
        copy_verified(source, game / relative, digest)
    assert all(sha(Path(path)) == digest for path, digest in guards.items())
    journal['status'] = 'INSTALLED_RUNTIME_PENDING'
    save(transaction / 'transaction.json', journal)
    return transaction


def rollback(transaction, game=GAME, fixture=False):
    if not fixture:
        stopped()
    journal = json.loads((transaction / 'transaction.json').read_text(encoding='utf-8'))
    assert journal['game'] == str(game.resolve())
    expected = {'left4dead2/addons/' + VPK_NAME} | {
        'update/' + PREFIX + f'test_{n:03}' + ext for n in range(1, 41) for ext in ('.vtf', '.vmt')}
    assert set(journal['files']) == expected
    # Check every destination/backup before the first restoration.
    for relative, row in journal['files'].items():
        assert (game / relative).resolve().is_relative_to(game.resolve())
        for parent in (game / relative, *(game / relative).parents):
            assert not parent.is_symlink()
            if parent == game:
                break
        assert (transaction / 'before' / relative).resolve().is_relative_to(transaction.resolve())
        assert sha(game / relative) in (row['after'], row['before']), '文件被外部修改，停止回退'
        assert sha(transaction / 'before' / relative) == row['before']
    for relative, row in journal['files'].items():
        copy_verified(transaction / 'before' / relative, game / relative, row['before'])
    journal['status'] = 'ROLLED_BACK'
    save(transaction / 'transaction.json', journal)


def gui(smoke=False):
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from PIL import ImageTk
    root = tk.Tk()
    root.title('CSP 喷漆导入工具 · 40 槽位')
    root.geometry('640x600')
    root.minsize(640, 600)
    slot = tk.IntVar(value=1)
    ttk.Label(root, text='选择槽位 → 导入图片 → 构建 → 退出游戏后部署', padding=10).pack()
    ttk.Spinbox(root, from_=1, to=40, textvariable=slot, width=8).pack()
    preview = ttk.Label(root)
    preview.pack(pady=10)
    status = tk.StringVar(value='未修改的槽位保留原图。请选择自己的静态图片。')
    ttk.Label(root, textvariable=status, wraplength=600).pack(pady=8)

    def run(action):
        try:
            action()
        except Exception as error:
            messagebox.showerror('操作未完成', str(error))

    def choose():
        path = filedialog.askopenfilename(filetypes=[('静态图片 / VTF', '*.png *.jpg *.jpeg *.bmp *.tga *.webp *.vtf')])
        if not path:
            return
        image = import_image(path, slot.get())
        with Image.open(image) as source:
            preview.image = ImageTk.PhotoImage(source.copy())
        preview.configure(image=preview.image)
        status.set(f'已导入槽位 {slot.get():03}；尚未部署。')

    def package():
        folder = build()
        status.set('构建完成：' + str(folder))

    def install():
        latest = json.loads((HOME / 'latest.json').read_text(encoding='utf-8'))
        folder = (HOME / latest['build']).resolve()
        assert folder.is_relative_to(HOME.resolve())
        if messagebox.askyesno('部署确认', '请先退出游戏。将同步替换选择器 VPK 和 80 个编号素材，并保留完整备份。继续？'):
            transaction = deploy(folder)
            status.set('部署完成。请重启游戏，进战役前选择对应编号。备份：' + transaction.name)

    def restore():
        latest = json.loads((HOME / 'last_deploy.json').read_text(encoding='utf-8'))
        transaction = (HOME / latest['transaction']).resolve()
        assert transaction.is_relative_to(HOME.resolve())
        if messagebox.askyesno('回退确认', '退出游戏后恢复上一次部署前的选择器及编号素材？'):
            rollback(transaction)
            status.set('已恢复部署前的 81 个文件。')

    for text, action in (('选择图片并导入当前槽位', choose), ('构建部署包', package),
                         ('部署到本机游戏', install), ('回退最近一次部署', restore)):
        ttk.Button(root, text=text, command=lambda fn=action: run(fn)).pack(pady=3)
    if smoke:
        preview.image = ImageTk.PhotoImage(Image.new('RGBA', (256, 256), 'teal'))
        preview.configure(image=preview.image)
        root.update()
        assert all(widget.winfo_y() + widget.winfo_height() <= root.winfo_height()
                   for widget in root.winfo_children()), '窗口控件越界'
        root.destroy()
        print('PASS Tk window, 256px preview and four buttons fit client area; manual clicks pending')
        return
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='gui', choices=('gui', 'import', 'build', 'deploy', 'rollback'))
    parser.add_argument('--slot', type=int)
    parser.add_argument('--image', type=Path)
    args = parser.parse_args()
    if args.action == 'gui':
        gui()
    elif args.action == 'import':
        print(import_image(args.image, args.slot))
    elif args.action == 'build':
        print(build())
    elif args.action == 'deploy':
        print(deploy(HOME / json.loads((HOME / 'latest.json').read_text(encoding='utf-8'))['build']))
    else:
        rollback(HOME / json.loads((HOME / 'last_deploy.json').read_text(encoding='utf-8'))['transaction'])
        print('PASS restored previous files')


if __name__ == '__main__':
    main()
