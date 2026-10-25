"""Strict, independent KeyValues parser preserving duplicate keys and source spans."""

from dataclasses import dataclass


@dataclass
class Token:
    value: str
    start: int
    end: int
    kind: str


@dataclass
class Node:
    key: str
    value: object
    start: int
    end: int
    conditions: tuple = ()


def tokenize(text):
    tokens = []
    i = 0
    while i < len(text):
        if text[i].isspace() or text[i] == "\ufeff":
            i += 1
        elif text.startswith("//", i):
            end = text.find("\n", i)
            i = len(text) if end < 0 else end + 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                raise ValueError(f"Unterminated comment at offset {i}")
            i = end + 2
        elif text[i] in "{}":
            tokens.append(Token(text[i], i, i + 1, "brace"))
            i += 1
        elif text[i] == '"':
            start = i
            i += 1
            value = []
            while i < len(text):
                if text[i] == '"':
                    i += 1
                    break
                if text[i] == "\\" and i + 1 < len(text) and text[i + 1] == '"':
                    value.append('"')
                    i += 2
                else:
                    value.append(text[i])
                    i += 1
            else:
                raise ValueError(f"Unterminated string at offset {start}")
            tokens.append(Token("".join(value), start, i, "string"))
        elif text[i] == "[":
            end = text.find("]", i)
            if end < 0:
                raise ValueError(f"Unterminated condition at offset {i}")
            tokens.append(Token(text[i:end + 1], i, end + 1, "condition"))
            i = end + 1
        else:
            start = i
            while i < len(text) and not text[i].isspace() and text[i] not in '{}"':
                i += 1
            tokens.append(Token(text[start:i], start, i, "bare"))
    return tokens


def parse(text):
    tokens = tokenize(text)
    cursor = 0

    def entries(nested=False):
        nonlocal cursor
        result = []
        while cursor < len(tokens):
            key = tokens[cursor]
            if key.value == "}" and key.kind == "brace":
                if not nested:
                    raise ValueError(f"Surplus closing brace at offset {key.start}")
                cursor += 1
                return result
            if key.kind in ("brace", "condition"):
                raise ValueError(f"Expected key at offset {key.start}: {key.value}")
            cursor += 1
            conditions = []
            while cursor < len(tokens) and tokens[cursor].kind == "condition":
                conditions.append(tokens[cursor].value)
                cursor += 1
            if cursor == len(tokens):
                raise ValueError(f"Missing value for {key.value} at offset {key.start}")
            value = tokens[cursor]
            cursor += 1
            if value.value == "{" and value.kind == "brace":
                data = entries(True)
                end = tokens[cursor - 1].end
            elif value.kind in ("brace", "condition"):
                raise ValueError(f"Missing value for {key.value} at offset {key.start}")
            else:
                data = value.value
                end = value.end
            while cursor < len(tokens) and tokens[cursor].kind == "condition":
                conditions.append(tokens[cursor].value)
                cursor += 1
            result.append(Node(key.value, data, key.start, end, tuple(conditions)))
        if nested:
            raise ValueError("Missing closing brace at EOF")
        return result

    return entries()


def walk(nodes, path=""):
    for node in nodes:
        location = path + "/" + node.key
        yield location, node
        if isinstance(node.value, list):
            yield from walk(node.value, location)


def scalars(nodes):
    return {n.key.lower(): n.value for n in nodes if isinstance(n.value, str)}


if __name__ == "__main__":
    sample = '"Root" { key "a" key "b" [$WIN32] Panel { xpos "0" } }'
    tree = parse(sample)
    assert len(tree[0].value) == 3
    assert scalars(tree[0].value)["key"] == "b"
    for invalid in ('"Root" { key }', '"Root" { key "a"', '"Root" { } orphan', '"Root" { } }'):
        try:
            parse(invalid)
        except ValueError:
            continue
        raise AssertionError(invalid)
    print("PASS strict KeyValues parser: duplicate/conditional keys; malformed pair/brace rejection")
