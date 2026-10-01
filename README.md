# MuffinEMU site

The redesigned website for [MuffinEMU](https://github.com/kiddreads/MuffinEMU), the
Wii U emulator for iPhone and iPad. Plain HTML, CSS and JavaScript with a small
Python build step; no npm, no framework, no runtime dependencies.

```sh
python3 build.py --serve   # build into site/ and serve it on http://localhost:8000
```

## What's in it

- **Dark-first, theme-driven colour.** All 31 app themes (the app's own colour data)
  drive four accent channels registered with `@property`, so switching theme
  cross-fades every glow, gradient and border on the page. With View Transitions
  available, the switch is a circular reveal from the point you clicked. Light mode
  follows the system or the toggle in the header.
- **Motion.** Cross-page View Transitions, a staggered wordmark intro, scroll reveals,
  hero parallax, a pinned horizontal feature rail, count-up stats, cursor spotlight
  on cards, magnetic buttons and a scroll progress line. Everything that moves is
  switched off under `prefers-reduced-motion`; the rail becomes a swipe carousel on
  touch-width screens.
- **Command palette.** <kbd>⌘K</kbd> / <kbd>Ctrl K</kbd> / <kbd>/</kbd> searches
  pages, sections on the current page, themes and actions (copy the SideStore
  source, cycle colour mode, random theme). Type `theme …` to filter themes.
- **Self-hosted fonts** (Space Grotesk, Inter, JetBrains Mono; SIL OFL), so the only
  third-party request is GoatCounter, the same as the current site.

## Layout

| Path | What |
| --- | --- |
| `content/home.html` | Home page body, laid out by hand |
| `content/docs/*.html` | Docs page bodies, imported verbatim from the live site |
| `content/head/*.html` | Each page's SEO head (title, Open Graph, JSON-LD), imported verbatim |
| `content/404.html` | 404 body (absolute paths; Pages serves it at any missing URL) |
| `assets/` | `site.css`, `theme.js` (theme data + engine), `app.js` (interactions), fonts, icon |
| `static/` | Files served from the site root: `sitemap.xml`, the IndexNow key |
| `build.py` | Wraps every body in the shared shell and writes `site/` |
| `tools/import_live.py` | Re-imports content from the MuffinEMU repo's `docs/` |

## Keeping it in step with the live site

The live site in `kiddreads/MuffinEMU/docs` stays the source of truth for the words,
the metadata and the theme data; this repo owns only the presentation.

```sh
python3 tools/import_live.py /path/to/MuffinEMU/docs
python3 build.py
```

The importer copies every docs page body, every SEO head, the 404, the sitemap, the
IndexNow key and the theme table. The home page is laid out by hand, so the importer
instead checks that every heading, paragraph and list item on the live home page
appears word for word in `content/home.html`, and exits non-zero if anything is
missing.

## Going live

Nothing here is published. Two ways to ship it when it's approved:

1. **Preview:** set this repo's Pages source to GitHub Actions and run the
   *Publish preview to Pages* workflow by hand.
2. **Replace the live site:** copy the contents of `site/` into `MuffinEMU/docs/`.
   Leave everything else there alone: the SideStore/AltStore/TrollStore feeds
   (`*.json`), `gamepad-layout/`, the Markdown notes, `_config.yml` and
   `_includes/`. The SideStore source URL and every page URL stay the same.
   The old `site.css`, `docs.css` and `theme.js` can be deleted afterwards; nothing
   outside the old pages loads them.
