"""Snapshot the three selected Workshop pages/API identities; optionally cache packages.

Downloaded code is never executed and nothing is installed into the game.
"""

import argparse
import datetime
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import urllib.parse
import urllib.request
import zipfile

from release_paths import ROOT

ITEMS = ('3787239937', '3558049615', '3785109042')
API = 'https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/'


class Description(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.text = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        if props.get('id') == 'highlightContent' or props.get('class') == 'workshopItemDescription':
            self.depth = 1
        elif self.depth and tag not in ('br', 'img', 'hr', 'input', 'meta', 'link'):
            self.depth += 1
        if self.depth:
            if tag in ('br', 'div', 'p', 'li'):
                self.text.append('\n')
            if tag == 'a' and props.get('href'):
                self.links.append(props['href'])

    def handle_endtag(self, tag):
        if self.depth and tag not in ('br', 'img', 'hr', 'input', 'meta', 'link'):
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.text.append(data)


def fetch(url, data=None):
    request = urllib.request.Request(url, data=data, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read(), {'requested_url': url, 'final_url': response.url, 'http_status': response.status}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert json.loads(path.read_text(encoding='utf-8')) == value


def download(details, folder):
    item = details['publishedfileid']
    target = folder / (item + '.vpk')
    # Reuse only the exactly matched content identity of the previously studied package.
    old = ROOT / 'research/workshop_3785109042'
    if item == '3785109042' and (old / 'workshop_metadata.json').exists():
        previous = json.loads((old / 'workshop_metadata.json').read_text(encoding='utf-8'))['response']['publishedfiledetails'][0]
        candidate = old / (item + '.vpk')
        if all(str(previous.get(k)) == str(details.get(k)) for k in ('hcontent_file', 'file_size', 'time_updated')) and candidate.exists():
            raw = candidate.read_bytes()
            assert len(raw) == int(details['file_size'])
            target.write_bytes(raw)
            return target, {'source': 'existing identity-matched project archive', 'path': str(candidate)}
    url = details.get('file_url')
    if not url:
        return None, {'source': 'Steam client/offline package required; no public file_url'}
    parsed = urllib.parse.urlsplit(url)
    assert parsed.scheme in ('http', 'https') and parsed.hostname
    url = urllib.parse.urlunsplit(parsed._replace(scheme='https'))
    attempts = []
    urls = [url]
    if parsed.hostname == 'cdn.steamusercontent.com':
        urls.append(url.replace('cdn.steamusercontent.com', 'steamuserimages-a.akamaihd.net', 1))
    size = int(details['file_size'])
    assert 0 < size <= 1024 * 1024 * 1024, 'Review unexpectedly large package before downloading'
    for candidate in urls:
        try:
            raw, response = fetch(candidate)
            assert len(raw) == size, 'API/file length mismatch'
            target.write_bytes(raw)
            response['source'] = 'public metadata file_url'
            response['previous_failures'] = attempts
            return target, response
        except Exception as exc:
            attempts.append({'url': candidate, 'error': repr(exc)})
    raise RuntimeError(json.dumps(attempts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder = ROOT / 'reports/platform_comparison' / stamp
    folder.mkdir(parents=True)
    request = {'itemcount': str(len(ITEMS))}
    request.update({f'publishedfileids[{i}]': item for i, item in enumerate(ITEMS)})
    raw, response = fetch(API, urllib.parse.urlencode(request).encode())
    (folder / 'api_response.json').write_bytes(raw)
    details = json.loads(raw)['response']['publishedfiledetails']
    assert {str(d['publishedfileid']) for d in details} == set(ITEMS)
    report = {'captured_utc': stamp, 'api': {'method': 'POST', 'url': API, 'form': request, **response},
              'scope': 'web acquisition and static package inventory only; no payload execution or game writes', 'items': []}
    for detail in details:
        item = str(detail['publishedfileid'])
        row = {'id': item, 'page_url': f'https://steamcommunity.com/sharedfiles/filedetails/?id={item}', 'metadata': detail}
        report['items'].append(row)
        try:
            page, transport = fetch(row['page_url'] + '&l=schinese')
            (folder / (item + '.html')).write_bytes(page)
            reader = Description()
            reader.feed(page.decode('utf-8', errors='replace'))
            text = ''.join(reader.text)
            (folder / (item + '_description.txt')).write_text(text, encoding='utf-8')
            row['page'] = {'transport': transport, 'sha256': hashlib.sha256(page).hexdigest(), 'description_links': list(dict.fromkeys(reader.links)), 'description_chars': len(text)}
        except Exception as exc:
            row['page_error'] = repr(exc)
        if args.download and detail.get('result') == 1:
            try:
                path, transport = download(detail, folder)
                row['download'] = transport
                if path:
                    raw = path.read_bytes()
                    row['package'] = {'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'magic': raw[:16].hex()}
                    if zipfile.is_zipfile(path):
                        with zipfile.ZipFile(path) as archive:
                            assert archive.testzip() is None
                            row['package']['format'] = 'ZIP, despite .vpk suffix'
                            inventory = [{'path': e.filename, 'bytes': e.file_size, 'compressed': e.compress_size} for e in archive.infolist()]
                            save(folder / (item + '_inventory.json'), inventory)
                            row['package']['members'] = len(inventory)
                    elif raw[:4] == b'\x34\x12\xaa\x55':
                        row['package']['format'] = 'Valve VPK'
                    else:
                        raise ValueError('Unexpected package magic; do not execute/extract')
            except Exception as exc:
                row['download_error'] = repr(exc)
        print(item, detail.get('title'), 'result=', detail.get('result'), 'bytes=', detail.get('file_size'))
        print(json.dumps({k: v for k, v in row.items() if k not in ('metadata', 'page')}, ensure_ascii=False))
        save(folder / 'sources.json', report)
    print('REPORT ' + str(folder / 'sources.json'))
    if any(r.get('download_error') or r['metadata'].get('result') != 1 for r in report['items']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
