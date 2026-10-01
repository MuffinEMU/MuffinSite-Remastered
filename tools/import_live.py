#!/usr/bin/env python3
"""Pull content from the MuffinEMU repo's docs/ folder (the live site) into content/.

    python3 tools/import_live.py /path/to/MuffinEMU/docs

The live site stays the source of truth for words and metadata; this repo only
owns the presentation. For every page this copies:

  - the SEO head (title, description, canonical, Open Graph, Twitter, JSON-LD,
    verification comments) verbatim -> content/head/<page>.html
  - the inside of <main> verbatim -> content/docs/<page>.html (docs pages)
    or content/404.html

The home page is hand-laid-out in content/home.html, so instead of copying it
this runs a parity check: every heading, paragraph and list item in the live
home page's <main> must appear, word for word, in content/home.html. Anything
missing is printed and the script exits non-zero.

The theme table comes from the app itself, not the site: see
tools/themes_from_swift.py.

Static files the site needs at its root (sitemap, IndexNow key) are copied to
static/.
"""
import html
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"

# Head lines the new shell writes itself.
DROP = [
    r'<meta charset[^>]*>',
    r'<meta name="viewport"[^>]*>',
    r'<meta name="theme-color"[^>]*>',
    r'<link rel="(?:icon|apple-touch-icon|stylesheet)"[^>]*>',
    r'<script src="[^"]*theme\.js"></script>',
    r'<svg xmlns.*?</svg>',
    r'<!-- One sprite.*?-->',
]


def head_block(src):
    m = re.search(r"<head>(.*?)</head>", src, re.S)
    h = m.group(1)
    for pat in DROP:
        h = re.sub(pat, "", h, flags=re.S)
    return re.sub(r"\n\s*\n+", "\n", h).strip() + "\n"


def main_block(src):
    return re.search(r"<main[^>]*>(.*?)</main>", src, re.S).group(1).strip() + "\n"


def texts(fragment):
    out = []
    for m in re.finditer(r"<(h[1-4]|p|li)\b[^>]*>(.*?)</\1>", fragment, re.S):
        t = re.sub(r"<[^>]+>", " ", m.group(2))
        t = " ".join(html.unescape(t).split())
        if t:
            out.append(t)
    return out


def norm(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment)
    return " ".join(html.unescape(t).split())


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    live = pathlib.Path(sys.argv[1])
    (CONTENT / "head").mkdir(parents=True, exist_ok=True)
    (CONTENT / "docs").mkdir(parents=True, exist_ok=True)

    (CONTENT / "head" / "index.html").write_text(head_block((live / "index.html").read_text()))
    for f in sorted((live / "docs").glob("*.html")):
        src = f.read_text()
        (CONTENT / "head" / f"docs-{f.stem}.html").write_text(head_block(src))
        (CONTENT / "docs" / f.name).write_text(main_block(src))
    if (live / "404.html").exists():
        src = (live / "404.html").read_text()
        (CONTENT / "head" / "404.html").write_text(head_block(src))
        (CONTENT / "404.html").write_text(main_block(src))

    static = ROOT / "static"
    static.mkdir(exist_ok=True)
    for f in live.iterdir():
        if f.name == "sitemap.xml" or re.fullmatch(r"[0-9a-f]{32}\.txt", f.name):
            shutil.copy2(f, static / f.name)

    # Parity check for the hand-laid-out home page.
    home = norm((CONTENT / "home.html").read_text())
    live_main = main_block((live / "index.html").read_text())
    # Screen-reader-only spans are presentation, not copy.
    live_main = re.sub(r'<span class="visually-hidden">.*?</span>', "", live_main, flags=re.S)
    missing = [t for t in texts(live_main) if t not in home]
    print(f"imported {len(list((live / 'docs').glob('*.html')))} docs pages")
    if missing:
        print("\nhome.html is missing live copy:")
        for t in missing:
            print("  -", t)
        sys.exit(1)
    print("home.html carries every line of the live home page")


if __name__ == "__main__":
    main()
