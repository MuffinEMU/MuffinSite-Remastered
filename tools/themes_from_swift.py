#!/usr/bin/env python3
"""Regenerate the theme table in assets/theme.js from the iOS app's own source.

    python3 tools/themes_from_swift.py /path/to/MuffinEMU/src/ios/App/MuffinThemePresets.swift

Every MuffinThemeDefinition in the file is read (id, name, iconId, the 14
light/dark token pairs and, where present, the multi-stop background), in the
order of the file's `all` array. Themes whose icon id starts with "pro-" are
the code-unlocked Pro themes. The result replaces the THEMES array in
assets/theme.js and is also written to tools/themes_data.js.
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Swift token name -> (site key, light field, dark field)
TOKENS = [
    ("top", "backgroundTop"), ("bottom", "backgroundBottom"),
    ("muffinTop", "muffinTopLight"), ("muffinDark", "muffinTopDark"),
    ("cream", "cream"), ("wrapper", "wrapper"),
    ("navy", "blueberryNavy"), ("pixel", "pixelBlue"), ("blush", "blushPink"),
    ("brownDarkest", "brownDarkest"), ("brownDark", "brownDark"), ("brownMid", "brownMid"),
    ("sparkle", "sparkleCream"), ("shadow", "shadow"),
]


def parse(src):
    defs = {}
    for m in re.finditer(r"static let (\w+) = MuffinThemeDefinition\((.*?)\n    \)", src, re.S):
        var, body = m.group(1), re.sub(r"//[^\n]*", "", m.group(2))
        def s(key):
            mm = re.search(r"\b" + key + r':\s*"([^"]*)"', body)
            if not mm:
                raise SystemExit(f"{var}: missing {key}")
            return mm.group(1)
        def arr(key):
            mm = re.search(r"\b" + key + r":\s*\[(.*?)\]", body, re.S)
            return None if not mm else [x.strip().strip('"') for x in mm.group(1).split(",") if x.strip()]
        t = {"id": s("id"), "name": s("name"), "iconId": s("iconId")}
        for key, swift in TOKENS:
            t[key] = [s(swift + "Light"), s(swift + "Dark")]
        light, dark, locs = arr("backgroundStopsLight"), arr("backgroundStopsDark"), arr("backgroundStopLocations")
        if light and dark and locs:
            t["stops"] = {"light": light, "dark": dark, "locations": [float(x) for x in locs]}
        if t["iconId"].startswith("pro-"):
            t["pro"] = True
        defs[var] = t
    order = re.search(r"static let all: \[MuffinThemeDefinition\] = \[(.*?)\]", src, re.S).group(1)
    return [defs[v.strip()] for v in order.split(",") if v.strip()]


def js(themes):
    lines = ["  var THEMES = ["]
    for i, t in enumerate(themes):
        q = json.dumps
        parts = [f'{{ id: {q(t["id"])}, name: {q(t["name"])}, iconId: {q(t["iconId"])},']
        if t.get("pro"):
            parts[0] = parts[0][:-1] + ", pro: true,"
        row = []
        for key, _ in TOKENS:
            row.append(f'{key}: [{q(t[key][0])}, {q(t[key][1])}]')
        for k in range(0, len(row), 3):
            parts.append("      " + ", ".join(row[k:k + 3]) + ",")
        if "stops" in t:
            st = t["stops"]
            parts.append("      stops: {")
            parts.append(f'        light: {q(st["light"])},')
            parts.append(f'        dark: {q(st["dark"])},')
            parts.append(f'        locations: {q(st["locations"])}')
            parts.append("      },")
        parts[-1] = parts[-1].rstrip(",")
        body = "\n".join(["    " + parts[0]] + parts[1:]) + " }" + ("," if i < len(themes) - 1 else "")
        lines.append(body)
    lines.append("  ];")
    return "\n".join(lines) + "\n"


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    themes = parse(pathlib.Path(sys.argv[1]).read_text())
    table = js(themes)
    (ROOT / "tools" / "themes_data.js").write_text(table)
    tj = ROOT / "assets" / "theme.js"
    new = re.sub(r"^  var THEMES = \[.*?^  \];\n", lambda _: table, tj.read_text(), flags=re.S | re.M)
    tj.write_text(new)
    print(f"{len(themes)} themes from the app source"
          f" ({sum(1 for t in themes if t.get('pro'))} pro, {sum(1 for t in themes if 'stops' in t)} multi-stop)")


if __name__ == "__main__":
    main()
