"""Retrieve the two selected Workshop items and preserve acquisition evidence."""

import argparse
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "originals"
ITEMS = {"A": "3467154613", "B": "2906960647"}


def fetch(url, data=None):
    request = urllib.request.Request(
        url, data=data, headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--item", nargs=2, metavar=("LABEL", "WORKSHOP_ID"))
    args = parser.parse_args()
    items = {args.item[0]: args.item[1]} if args.item else ITEMS
    OUT.mkdir(exist_ok=True)
    for label, item in items.items():
        assert label.isalnum() and item.isdigit()
        target = OUT / f"{label}_{item}.vpk"
        if target.exists():
            print(label, "preserved", target, hashlib.sha256(target.read_bytes()).hexdigest())
            continue
        metadata = OUT / f"{label}_{item}.json"
        page = f"https://steamcommunity.com/sharedfiles/filedetails/?id={item}"
        try:
            if not metadata.exists():
                body = fetch(page)
                (OUT / f"{label}_{item}.html").write_bytes(body)
                print(label, "page saved", len(body))
        except Exception as exc:
            print(label, "page error:", repr(exc))
        data = urllib.parse.urlencode(
            {"itemcount": "1", "publishedfileids[0]": item}
        ).encode()
        try:
            if metadata.exists():
                body = metadata.read_bytes()
            else:
                body = fetch(
                    "https://api.steampowered.com/ISteamRemoteStorage/"
                    "GetPublishedFileDetails/v1/",
                    data,
                )
                metadata.write_bytes(body)
            details = json.loads(body)["response"]["publishedfiledetails"][0]
            print(label, json.dumps(details, ensure_ascii=True))
            url = details.get("file_url")
            if url:
                try:
                    content = fetch(url)
                except (urllib.error.URLError, OSError):
                    content = fetch(url.replace("cdn.steamusercontent.com", "steamuserimages-a.akamaihd.net"))
                if content[:4] != b"\x34\x12\xaa\x55":
                    raise ValueError("Downloaded payload is not a VPK")
                assert len(content) == int(details["file_size"])
                target.write_bytes(content)
                print(label, target, hashlib.sha256(content).hexdigest())
        except Exception as exc:
            print(label, "API/download error:", repr(exc))


if __name__ == "__main__":
    main()
