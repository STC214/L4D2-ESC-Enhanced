"""Acquire the selected Workshop archive; preserve bytes and identify format."""

import argparse
import hashlib
import json
from pathlib import Path
import stat
import urllib.parse
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "research/workshop_3785109042"
ITEM = "3785109042"


def fetch(url, data=None):
    request = urllib.request.Request(url, data=data, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--extract", action="store_true")
    args = parser.parse_args()
    DEST.mkdir(parents=True, exist_ok=True)
    meta = DEST / "workshop_metadata.json"
    if not meta.exists():
        body = urllib.parse.urlencode({"itemcount": "1", "publishedfileids[0]": ITEM}).encode()
        payload = fetch("https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/", body)
        data = json.loads(payload)
        assert data["response"]["publishedfiledetails"][0]["result"] == 1
        meta.write_bytes(payload)
    details = json.loads(meta.read_bytes())["response"]["publishedfiledetails"][0]
    print(json.dumps(details, ensure_ascii=False, indent=2))
    if not args.download and not args.extract:
        return
    target = DEST / (ITEM + ".vpk")
    if not target.exists():
        url = details["file_url"]
        try:
            content = fetch(url)
        except (OSError, TimeoutError):
            content = fetch(url.replace("cdn.steamusercontent.com", "steamuserimages-a.akamaihd.net"))
        assert len(content) == int(details["file_size"])
        target.write_bytes(content)
    raw = target.read_bytes()
    assert len(raw) == int(details["file_size"])
    print("ORIGINAL " + str(target))
    print("SHA256 " + hashlib.sha256(raw).hexdigest())
    print("MAGIC " + raw[:32].hex())
    if args.extract:
        assert zipfile.is_zipfile(target), "Payload is not a ZIP; inspect before choosing a suffix"
        renamed = DEST / (ITEM + ".zip")
        if renamed.exists():
            assert renamed.read_bytes() == raw
        else:
            renamed.write_bytes(raw)
        output = DEST / "unpacked"
        with zipfile.ZipFile(renamed) as archive:
            assert archive.testzip() is None, "ZIP CRC failure"
            entries = archive.infolist()
            assert sum(i.file_size for i in entries) < 512 * 1024 * 1024
            names, inventory = set(), []
            for entry in entries:
                name = entry.filename.replace("\\", "/")
                parts = name.split("/")
                assert not name.startswith("/") and ".." not in parts and ":" not in name
                assert name.casefold() not in names, "Case-insensitive ZIP path collision"
                names.add(name.casefold())
                assert not stat.S_ISLNK(entry.external_attr >> 16)
                path = (output / name).resolve()
                assert path.is_relative_to(output.resolve())
                if entry.is_dir():
                    continue
                data = archive.read(entry)
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists():
                    assert path.read_bytes() == data, "Preserve existing modified extracted file"
                else:
                    path.write_bytes(data)
                assert path.read_bytes() == data
                row = {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                inventory.append(row)
                print("MEMBER " + json.dumps(row, ensure_ascii=False))
        report = {"item": ITEM, "original": str(target), "zip_copy": str(renamed),
                  "sha256": hashlib.sha256(raw).hexdigest(), "format": "ZIP (not Valve VPK)",
                  "extracted": str(output), "members": inventory, "executed_payloads": False}
        record = DEST / "extraction_verification.json"
        record.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        assert json.loads(record.read_text(encoding="utf-8")) == report
        print("VERIFIED " + str(record))


if __name__ == "__main__":
    main()
