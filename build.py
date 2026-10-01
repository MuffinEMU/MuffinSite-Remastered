#!/usr/bin/env python3
"""Build the MuffinEMU site into site/.

content/home.html        -> site/index.html
content/docs/<page>.html -> site/docs/<page>.html
content/404.html         -> site/404.html
content/head/<page>.html -> each page's SEO head (imported from the live site)
static/*                 -> site/ root (sitemap, IndexNow key)
assets/                  -> site/assets/

Content files hold only what goes inside <main>; this script wraps every page
in the shared shell (head, header, command palette, footer) so the chrome is
written once. No dependencies beyond the standard library.

    python3 build.py            # build
    python3 build.py --serve    # build, then serve site/ on :8000
"""
import html
import os
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent
# Where the site is served from (for the 404 page's absolute paths).
SITE_BASE = os.environ.get("SITE_BASE", "/MuffinEMU/")
# A preview build (PREVIEW=1) is kept out of search engines and out of the
# real site's GoatCounter numbers. The canonical URLs still point at the
# real site.
PREVIEW = os.environ.get("PREVIEW") == "1"
CONTENT = ROOT / "content"
OUT = ROOT / "site"
# Pages that stay in the MuffinEMU repo (the SideStore feeds, the GamePad
# measurement tool) are linked there absolutely.
LIVE = "https://kiddreads.github.io/MuffinEMU/"

DOCS_NAV = [
    ("index", "Overview"),
    ("installation", "Installation"),
    ("features", "Features overview"),
    ("screen-layout", "Screen Layout"),
    ("save-states", "Save States"),
    ("controls", "Controls &amp; GamePad"),
    ("themes", "Themes &amp; Icons"),
    ("troubleshooting", "Troubleshooting"),
    ("faq", "FAQ"),
]

EXTRA_ICONS = """
    <symbol id="i-github" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.5a9.5 9.5 0 0 0-3 18.5c.5.1.7-.2.7-.5v-1.7c-2.6.6-3.2-1.2-3.2-1.2-.4-1.1-1-1.4-1-1.4-.9-.6 0-.6 0-.6 1 .1 1.5 1 1.5 1 .9 1.5 2.3 1 2.9.8.1-.6.3-1 .6-1.3-2.1-.2-4.3-1-4.3-4.7 0-1 .4-1.9 1-2.6-.1-.2-.4-1.2.1-2.5 0 0 .8-.3 2.6 1a9 9 0 0 1 4.8 0c1.8-1.3 2.6-1 2.6-1 .5 1.3.2 2.3.1 2.5.6.7 1 1.6 1 2.6 0 3.7-2.2 4.5-4.3 4.7.3.3.6.9.6 1.8v2.7c0 .3.2.6.7.5A9.5 9.5 0 0 0 12 2.5z"/></symbol>
    <symbol id="i-copy" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="8.5" y="8.5" width="12" height="12" rx="2.5"/><path d="M15.5 8.5V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7.5a2 2 0 0 0 2 2h2.5"/></symbol>
    <symbol id="i-search" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/></symbol>
    <symbol id="i-menu" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 8h16M4 16h16"/></symbol>
    <symbol id="i-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/></symbol>
    <symbol id="i-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></symbol>
    <symbol id="i-auto" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor"/></symbol>
"""


def sprite():
    base = (ROOT / "tools" / "sprite_base.svg").read_text()
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false" '
        'style="position:absolute;width:0;height:0;overflow:hidden"><defs>\n'
        + base + EXTRA_ICONS + "</defs></svg>"
    )


def head(seo, prefix):
    """Shared head. `seo` is the page's SEO block, imported verbatim from the live site."""
    return f"""<!doctype html>
<html lang="en" class="no-js">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
{seo.strip()}
<link rel="icon" href="{prefix}assets/favicon-32.png" sizes="32x32">
<link rel="apple-touch-icon" href="{prefix}assets/icon-180.png">
<meta name="theme-color" content="#05060B" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#F4F5FA" media="(prefers-color-scheme: light)">
<link rel="preload" href="{prefix}assets/fonts/space-grotesk.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{prefix}assets/fonts/inter.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{prefix}assets/fonts/jetbrains-mono.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{prefix}assets/site.css">
<script src="{prefix}assets/theme.js"></script>
<script type="speculationrules">
{{"prerender": [{{"where": {{"and": [{{"href_matches": "{SITE_BASE}*"}}, {{"not": {{"selector_matches": "[target], [download]"}}}}]}}, "eagerness": "moderate"}}]}}
</script>
</head>"""


# Loaded only once the page is actually shown: a page prerendered on hover
# and never opened is not a visit.
GOATCOUNTER = """<script>
(function () {
  function load() {
    var s = document.createElement("script");
    s.async = true; s.src = "//gc.zgo.at/count.js";
    s.setAttribute("data-goatcounter", "https://muffinemu.goatcounter.com/count");
    document.body.appendChild(s);
  }
  if (document.prerendering) document.addEventListener("prerenderingchange", load, { once: true });
  else load();
})();
</script>"""

FINEPRINT = (
    'This is a preview of the redesigned site. The official MuffinEMU site is '
    '<a href="https://kiddreads.github.io/MuffinEMU/">kiddreads.github.io/MuffinEMU</a>.'
    if PREVIEW else
    'This site counts page visits with <a href="https://www.goatcounter.com">GoatCounter</a>: '
    'no cookies, no tracking across sites, no personal data. Fonts are served from this site.'
)


def seo(name):
    block = (CONTENT / "head" / f"{name}.html").read_text()
    if PREVIEW:
        block = re.sub(r'<meta name="robots"[^>]*>\n?', "", block)
        block = '<meta name="robots" content="noindex, nofollow">\n' + block
    return block


def header(prefix, current, slug=None):
    def cur(name):
        return ' aria-current="page"' if current == name else ""

    docs_links = "\n".join(
        f'          <a href="{prefix}docs/{s}.html"{" aria-current=\"page\"" if s == slug else ""}>{"All documentation" if s == "index" else label}</a>'
        for s, label in DOCS_NAV
    )
    return f"""
<a class="skip-link" href="#main">Skip to content</a>
<div class="backdrop" aria-hidden="true"><div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div><div class="grid-lines"></div><div class="grain"></div></div>

<header class="site-header">
  <div class="header-inner">
    <a class="brand" href="{prefix}index.html"><img src="{prefix}assets/icon-64.png" alt="" width="30" height="30"><span>MuffinEMU</span></a>
    <nav class="site-nav" id="site-nav" aria-label="Main">
      <a href="{prefix}index.html"{cur("home")}>Home</a>
      <a href="{prefix}docs/installation.html"{cur("installation")}>Install</a>
      <details class="nav-dropdown">
        <summary{' aria-current="page"' if current == "docs" else ""}>Docs <span class="chev" aria-hidden="true">▾</span></summary>
        <div class="dropdown-panel">
{docs_links}
        </div>
      </details>
      <a href="https://github.com/kiddreads/MuffinEMU">GitHub</a>
      <button class="nav-theme" type="button" data-palette-open="theme "><span class="theme-dot" aria-hidden="true"></span>Theme: <span data-theme-name>Bakery (Original)</span></button>
    </nav>
    <div class="header-tools">
      <button class="icon-btn search-btn" type="button" data-palette-open aria-label="Search and commands"><svg aria-hidden="true"><use href="#i-search"/></svg><span class="label">Search</span><span class="kbd" data-shortcut>⌘K</span></button>
      <button class="icon-btn theme-btn" type="button" data-palette-open="theme "><span class="theme-dot" aria-hidden="true"></span><span class="label" data-theme-name>Bakery (Original)</span></button>
      <button class="icon-btn mode-btn" type="button" data-mode-cycle aria-label="Colour mode"><svg class="auto" aria-hidden="true"><use href="#i-auto"/></svg><svg class="moon" aria-hidden="true"><use href="#i-moon"/></svg><svg class="sun" aria-hidden="true"><use href="#i-sun"/></svg></button>
      <button class="icon-btn nav-toggle" type="button" data-nav-toggle aria-controls="site-nav" aria-expanded="false" aria-label="Menu"><svg aria-hidden="true"><use href="#i-menu"/></svg></button>
    </div>
    <div class="progress" aria-hidden="true"></div>
  </div>
</header>
"""


def footer(prefix):
    return f"""
<footer class="site-footer">
  <div class="wrap">
    <div class="footer-grid">
      <div>
        <a class="brand" href="{prefix}index.html" style="margin-bottom:12px"><img src="{prefix}assets/icon-64.png" alt="" width="30" height="30"><span>MuffinEMU</span></a>
        <p style="margin:0">Wii U emulation for iPhone and iPad.</p>
      </div>
      <nav aria-label="Footer">
        <a href="{prefix}docs/installation.html">Install</a>
        <a href="{prefix}docs/index.html">Docs</a>
        <a href="{prefix}docs/faq.html">FAQ</a>
        <a href="{prefix}docs/licenses.html">Licences</a>
        <a href="https://github.com/kiddreads/MuffinEMU">GitHub</a>
        <a href="https://github.com/kiddreads/MuffinEMU/issues">Report an issue</a>
      </nav>
    </div>
    <p class="fineprint">{FINEPRINT}</p>
    <div class="footer-mark" aria-hidden="true">MuffinEMU</div>
  </div>
</footer>

<dialog class="palette" data-palette aria-label="Search and commands">
  <div class="palette-input">
    <svg aria-hidden="true"><use href="#i-search"/></svg>
    <input type="text" placeholder="Search pages, sections, themes…" aria-label="Search" role="combobox" aria-expanded="false" aria-autocomplete="list" aria-controls="palette-list" autocomplete="off" spellcheck="false">
    <span class="kbd">esc</span>
  </div>
  <p class="palette-count visually-hidden" role="status" aria-live="polite"></p>
  <ul class="palette-list" id="palette-list" role="listbox"></ul>
  <div class="palette-foot"><span>↑↓ move</span><span>↵ open</span><span>“theme …” filters themes</span></div>
</dialog>

<script src="{prefix}assets/app.js"></script>
{"" if PREVIEW else GOATCOUNTER}
</body>
</html>
"""


def wrap_tables(body):
    """Give tables that aren't already in a .table-wrap one, so wide tables
    scroll inside the page and can be reached by keyboard."""
    out, pos = [], 0
    for m in re.finditer(r"<table\b.*?</table>", body, re.S):
        before = body[max(0, m.start() - 200):m.start()]
        out.append(body[pos:m.start()])
        if 'class="table-wrap"' in before.rsplit("</div>", 1)[-1]:
            out.append(m.group(0))
        else:
            out.append('<div class="table-wrap" tabindex="0" role="region" aria-label="Table">' + m.group(0) + "</div>")
        pos = m.end()
    out.append(body[pos:])
    return "".join(out)


def fix_links(body):
    return body.replace('href="../gamepad-layout/"', f'href="{LIVE}gamepad-layout/"')


def build_home():
    body = (CONTENT / "home.html").read_text()
    page = (
        head(seo("index"), "")
        + '\n<body data-base="">\n' + sprite() + header("", "home")
        + '\n<main id="main" tabindex="-1">\n' + body + "</main>\n" + footer("")
    )
    (OUT / "index.html").write_text(page)


def build_docs():
    (OUT / "docs").mkdir(parents=True, exist_ok=True)
    for path in sorted((CONTENT / "docs").glob("*.html")):
        slug = path.stem
        body = fix_links(path.read_text())
        current = "installation" if slug == "installation" else "docs"
        body = wrap_tables(body)
        shell = head(seo(f"docs-{slug}"), "../") + '\n<body data-base="../">\n' + sprite() + header("../", current, slug)
        if slug == "index":
            main = f'\n<main class="wrap docs-hub" id="main" tabindex="-1">\n{body}</main>\n'
        else:
            side = "\n".join(
                f'      <a href="{s}.html"{" aria-current=\"page\"" if s == slug else ""}>{label}</a>'
                for s, label in DOCS_NAV + ([("licenses", "Open-source licences")] if slug == "licenses" else [])
            )
            main = f"""
<div class="docs-shell">
  <aside class="docs-sidebar">
    <p class="sidebar-title">Documentation</p>
    <nav aria-label="Documentation">
{side}
    </nav>
  </aside>
  <main class="docs-content" id="main" tabindex="-1">
{body}  </main>
</div>
"""
        (OUT / "docs" / f"{slug}.html").write_text(shell + main + footer("../"))


def build_404():
    # GitHub Pages serves this at whatever missing URL was asked for, so every
    # path in it is absolute.
    p = SITE_BASE.rstrip("/") + "/"
    body = (CONTENT / "404.html").read_text().replace('"/MuffinEMU/icon.png"', f'"{p}assets/icon-180.png"')
    body = body.replace('"/MuffinEMU/', f'"{p}')
    page = (
        head(seo("404"), p) + f'\n<body data-base="{p}">\n' + sprite() + header(p, "")
        + '\n<main id="main" class="wrap notfound" tabindex="-1">\n' + body + "</main>\n" + footer(p)
    )
    (OUT / "404.html").write_text(page)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "assets", OUT / "assets")
    (OUT / ".nojekyll").write_text("")
    for f in (ROOT / "static").iterdir():
        shutil.copy2(f, OUT / f.name)
    # Absolute URLs in the imported metadata (og:image, JSON-LD logo) point at
    # the site root, so these two also live there.
    for name in ("icon.png", "social-preview.png"):
        shutil.copy2(ROOT / "assets" / name, OUT / name)
    build_home()
    build_docs()
    build_404()
    print(f"built {sum(1 for _ in OUT.rglob('*.html'))} pages -> {OUT.relative_to(ROOT)}/")
    if "--serve" in sys.argv:
        import functools
        import http.server
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
        print("serving http://localhost:8000")
        http.server.ThreadingHTTPServer(("127.0.0.1", 8000), handler).serve_forever()


if __name__ == "__main__":
    main()
