"""Finite scalar model of Valve's public material math proxies (not a renderer).

Integer-vs-float destination behavior matters: Frac keeps integer destinations
integer, whereas Add/Subtract/Multiply/Divide store float results.
"""

import math
import re

from kv_audit import parse, scalars


class ScalarModel:
    def __init__(self, text):
        root = parse(text)[0].value
        self.values = {"$frame": (0, "int")}
        for key, value in scalars(root).items():
            if key.startswith("$"):
                try:
                    kind = "int" if re.fullmatch(r"[-+]?\d+", value) else "float"
                    self.values[key] = (float(value), kind)
                except ValueError:
                    pass
        sections = [n for n in root if n.key.lower() == "proxies" and isinstance(n.value, list)]
        self.proxies = sections[0].value if sections else []

    def bind(self, speed, time=1.0):
        def get(name, integer=False):
            value = self.values[name.lower()][0]
            return int(value) if integer else value

        for node in self.proxies:
            p = scalars(node.value)
            kind = node.key.lower()
            result = p.get("resultvar", "").lower()
            if kind == "playerspeed":
                self.values[result] = (speed * float(p.get("scale", "0.005")), "float")
                continue
            if kind == "currenttime":
                self.values[result] = (time, "float")
                continue
            if kind not in ("add", "subtract", "multiply", "divide", "frac", "int", "equals", "lessorequal", "clamp"):
                raise ValueError("Unsupported proxy in finite model: " + node.key)
            destination = self.values.get(result, (0, "float"))[1]
            integer = destination == "int"
            a = get(p["srcvar1"], integer)
            if kind in ("add", "subtract", "multiply", "divide"):
                b = get(p["srcvar2"], integer)
                if kind == "add":
                    value = a + b
                elif kind == "subtract":
                    value = a - b
                elif kind == "multiply":
                    value = a * b
                else:
                    value = a / b if b else a
                    if integer:
                        value = math.trunc(value)
                destination = "float"
            elif kind == "frac":
                value = a if integer else a - math.trunc(a)
            elif kind == "int":
                value = math.trunc(a)
            elif kind == "equals":
                value = a
            elif kind == "lessorequal":
                name = p["lessequalvar"] if get(p["srcvar1"]) <= get(p["srcvar2"]) else p["greatervar"]
                value = get(name, integer)
                destination = "float" if integer else destination
            else:
                value = min(float(p.get("max", "1")), max(float(p.get("min", "0")), a))
                destination = "float"
            self.values[result] = (value, destination)
        return int(self.values["$frame"][0])


def speed_samples(files):
    models = [ScalarModel(files[f"materials/vgui/hud/digits_{n}.vmt"].decode("utf-8-sig"))
              for n in (8, 17, 18, 19)]
    rows = []
    for speed in (0, 85, 220, 250, 999, 1205, 9, 10, 99, 100, 9999,
                  0.5, 9.99, 10.01, 99.99, 100.01, 999.99, 1000.01, 10000, -1):
        # Bind twice to exercise type changes after the first frame.
        for repeat in range(2):
            digits = [m.bind(speed, len(rows) + repeat / 60) for m in models]
        actual = "".join(str(d) for d in digits)
        expected = f"{int(min(9999, max(0, speed))):04d}"
        rows.append({"speed": speed, "actual_frames": digits, "actual_text": actual,
                     "expected_text": expected, "pass": actual == expected})
    return rows


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path
    from vpk import read

    from release_paths import OUTPUT
    path = OUTPUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", action="store_true")
    args = parser.parse_args()
    files = read(path)
    if args.metrics:
        for title, numbers in (("max", (16, 13, 14, 15)), ("average", (12, 9, 10, 11))):
            models = [ScalarModel(files[f"materials/vgui/hud/digits_{n}.vmt"].decode("utf-8-sig")) for n in numbers]
            for t, speed in enumerate((0, 85, 220, 250, 999, 1205, 9)):
                digits = [m.bind(speed, t + 1) for m in models]
                print(title, speed, digits)
        raise SystemExit(0)
    rows = speed_samples(files)
    for row in rows:
        print(json.dumps(row))
    raise SystemExit(any(not row["pass"] for row in rows))
