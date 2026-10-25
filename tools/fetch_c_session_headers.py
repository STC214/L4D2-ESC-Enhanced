"""Fetch narrowly scoped, primary-maintainer L4D2 ABI references."""

import json
import re
import urllib.request

from release_paths import ROOT


def main():
    output = ROOT / 'reports/c_session_inputs/sdk'
    output.mkdir(parents=True, exist_ok=True)
    for name in ('cdll_int.h', 'inetchannelinfo.h'):
        path = output / name
        if not path.exists():
            url = 'https://raw.githubusercontent.com/alliedmodders/hl2sdk/l4d2/public/' + name
            with urllib.request.urlopen(url, timeout=40) as response:
                raw = response.read()
            assert len(raw) > 1000
            path.write_bytes(raw)
    text = (output / 'cdll_int.h').read_text(encoding='utf-8-sig')
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    body = text.split('abstract_class IVEngineClient', 1)[1].split('\n};', 1)[0]
    methods = []
    for declaration in re.split(r'\bvirtual\s+', body)[1:]:
        declaration = declaration.split('= 0;', 1)[0]
        name = re.search(r'(\w+)\s*\(', declaration)
        assert name, declaration
        methods.append(name[1])
    report = {name: methods.index(name) for name in ('ClientCmd', 'IsInGame', 'IsConnected', 'GetNetChannelInfo', 'ClientCmd_Unrestricted')}
    (output / 'method_slots.json').write_text(json.dumps({'reported_slots': report, 'all_methods': methods}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))
    print(json.dumps(list(enumerate(methods[:32]))))


if __name__ == '__main__':
    main()
