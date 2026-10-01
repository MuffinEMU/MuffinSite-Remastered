# MuffinSite Remastered

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

## Theme colours

The 31 themes come straight from the iOS app, not from the old site:

```sh
python3 tools/themes_from_swift.py /path/to/MuffinEMU/src/ios/App/MuffinThemePresets.swift
```

Each token is used for the role it plays in the app: the background gradient
(drawn exactly as `MuffinTheme.backgroundGradient` does, including Autism Muffin's
rainbow header stops) feeds the glows; the button gradient (`muffinTopLight` →
`muffinTopDark`, with `sparkleCream` text) styles every primary button and icon tile;
`pixelBlue` and `blushPink` are the accents. Light and dark values follow the site's
mode. The theme lab shows each theme as a small piece of the app (background, card,
button) with its matching app icon, and the hero icon changes with it.

## Older iPhones and iPads

The site is built for current Safari and checked to work back to iOS 15 (the
app's own minimum), with content still readable and usable on iOS 12-14.

- `build.py` adds a plain fallback declaration in front of every declaration
  older Safari can't read (`color-mix()`, `dvh`/`svh`, `overflow: clip`,
  `inset`, logical properties), and refuses to publish if the result doesn't
  balance.
- `site.css` ends with the rest: `<dialog>` hidden where unsupported (the
  search buttons hide themselves), and `aspect-ratio` fallbacks for iOS 14.
- The scripts are plain ES5 with every newer API feature-tested. Reveal-on-
  scroll only hides content once `app.js` is running, so a device that can't
  run it still sees everything.

## App icons, remastered

`icons/source/` holds the 31 original icon SVGs (identical to the icons the app
ships; `bakery.svg` is the app's "original" icon). `tools/remaster_icons.py`
rebuilds each one into three variants in `assets/icons/`:

| File | Appearance |
| --- | --- |
| `<id>.svg` | Default: background hues richer at the same hue and lightness |
| `<id>-dark.svg` | Dark: background deepened at the same hue, muffin backlit |
| `<id>-tinted.svg` | Tinted (iOS 18): greyscale muffin on black, for the system tint |

The artwork itself is never redrawn: the background and the character are
split at the ground shadow, and lighting is added from each icon's own colours
(key light, backlight bloom, vignette, material-coloured shading on the dome
and liner, dome rim light, glass highlight and edge rim). The site uses the
default or dark variant to match its mode.

```sh
python3 tools/remaster_icons.py
```

The app still ships the original icons. To adopt these, render each SVG to a
1024px PNG (any renderer with SVG filter and blend support, e.g. Chrome or
resvg) and add them to the app's `AltIcon-<id>.appiconset` as the "any",
"dark" and "tinted" appearances.

## Keeping it in step with the live site

The live site in `kiddreads/MuffinEMU/docs` stays the source of truth for the words
and the metadata (the app's Swift source is the source for theme colours); this repo owns only the presentation.

```sh
python3 tools/import_live.py /path/to/MuffinEMU/docs
python3 build.py
```

The importer copies every docs page body, every SEO head, the 404, the sitemap and
the IndexNow key. The home page is laid out by hand, so the importer
instead checks that every heading, paragraph and list item on the live home page
appears word for word in `content/home.html`, and exits non-zero if anything is
missing.

## Going live

**Preview:** every push to `main` publishes a preview build to
<https://kiddreads.github.io/MuffinSite-Remastered/> (`PREVIEW=1`: kept out of search
engines, not counted in GoatCounter, footer points to the official site; canonical
URLs stay on the official site).

**Replace the live site:** build without `PREVIEW` (`python3 build.py`), then copy
the contents of `site/` into `MuffinEMU/docs/`. Leave everything else there alone:
the SideStore/AltStore/TrollStore feeds (`*.json`), `gamepad-layout/`, the Markdown
notes, `_config.yml` and `_includes/`. The SideStore source URL and every page URL
stay the same. The old `site.css`, `docs.css` and `theme.js` can be deleted
afterwards; nothing outside the old pages loads them.
