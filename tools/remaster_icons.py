#!/usr/bin/env python3
"""Remaster the 31 MuffinEMU app icons from their source SVGs.

    python3 tools/remaster_icons.py            # icons/source/*.svg -> assets/icons/

The source art (icons/source/<id>.svg, identical to the shipped app icons) is
never redrawn. Every icon is split at its ground shadow into a background
(gradients, flag stripes, motifs) and the muffin character, and three
variants are written per icon:

  <id>.svg         default ("any" appearance): background colours get more
                   chroma at the same hue and lightness; the character is
                   untouched.
  <id>-dark.svg    dark appearance: background colours are remapped to deep
                   values of the same hue (stripe order and contrast kept);
                   the character keeps its colours and is backlit.
  <id>-tinted.svg  tinted appearance (iOS 18): the character in greyscale on
                   black, for the system to tint.

On top of that, every variant gets the same lighting, built only from the
icon's own colours: a backlight bloom behind the muffin, a corner vignette, a
softer two-layer contact shadow, ambient occlusion and cylinder shading on
the paper liner, a rim light along the dome, and a glass top highlight and
edge rim.

Only the standard library and Pillow (for the one bitmap, the Autism
Acceptance infinity, which is embedded as WebP) are needed. File names are
the site's theme ids (bakery = the app's "original" icon).
"""
import colorsys
import copy
import math
import pathlib
import re
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "icons" / "source"
OUT = ROOT / "assets" / "icons"
SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG)
ET.register_namespace("xlink", XLINK)
Q = lambda t: "{%s}%s" % (SVG, t)

# ------------------------------------------------------------------ colour
def hex_to_rgb(h):
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]

def to_lin(v): return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
def from_lin(v): return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055

def to_oklch(hexc):
    r, g, b = (to_lin(c) for c in hex_to_rgb(hexc))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    A = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    B = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, math.hypot(A, B), math.atan2(B, A)

def _lin_rgb(L, C, H):
    A, B = C * math.cos(H), C * math.sin(H)
    l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3
    m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3
    s = (L - 0.0894841775 * A - 1.2914855480 * B) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)

def from_oklch(L, C, H):
    """Back to hex; chroma (never lightness or hue) is reduced to fit sRGB."""
    L = min(1.0, max(0.0, L))
    ok = lambda v: all(-0.0005 <= x <= 1.0005 for x in v)
    rgb = _lin_rgb(L, C, H)
    if not ok(rgb):
        lo, hi = 0.0, C
        for _ in range(24):
            mid = (lo + hi) / 2
            if ok(_lin_rgb(L, mid, H)): lo = mid
            else: hi = mid
        rgb = _lin_rgb(L, lo, H)
    return "#" + "".join("%02X" % round(min(1, max(0, from_lin(min(1, max(0, v))))) * 255) for v in rgb)

NAMED = {"white": "#FFFFFF", "black": "#000000"}

def norm_colour(v):
    if v is None: return None
    v = v.strip()
    if v.lower() in NAMED: return NAMED[v.lower()]
    if re.fullmatch(r"#[0-9a-fA-F]{3}|#[0-9a-fA-F]{6}", v): return v.upper() if len(v) == 7 else "#" + "".join(c * 2 for c in v[1:]).upper()
    return None

def vivid(hexc, k=1.22):
    L, C, H = to_oklch(hexc)
    return from_oklch(L, C * k if C >= 0.02 else C, H)

def deepen(hexc):
    """Dark appearance: same hue, lightness compressed into a deep band that
    keeps the original ordering (light stripes stay lighter than dark ones)."""
    L, C, H = to_oklch(hexc)
    return from_oklch(0.12 + 0.2 * L, C * 0.92 if C >= 0.02 else C, H)

# ------------------------------------------------------------------ geometry
def norm_d(d): return " ".join((d or "").split())

def is_dome(el):
    d = norm_d(el.get("d"))
    return el.tag == Q("path") and d.startswith("M300,650") and "L624,895" not in d

COLOUR_ATTRS = ("fill", "stroke", "stop-color", "flood-color")

def walk(el):
    yield el
    for c in el:
        yield from walk(c)

def refs(el):
    out = set()
    for e in walk(el):
        for a in ("fill", "stroke", "filter", "clip-path", "mask"):
            m = re.match(r"url\(#([^)]+)\)", e.get(a) or "")
            if m: out.add(m.group(1))
    return out

# ------------------------------------------------------------------ remaster
def palette(bg_elems, defs, src_dir):
    """Every colour the background uses (directly, via gradients, or in its
    bitmap), as hex."""
    cols = []
    ids = set()
    for el in bg_elems:
        ids |= refs(el)
        for e in walk(el):
            for a in COLOUR_ATTRS:
                c = norm_colour(e.get(a))
                if c: cols.append(c)
            if e.tag == Q("image"):
                cols += image_colours(src_dir / (e.get("href") or e.get("{%s}href" % XLINK)))
    for g in defs:
        if g.get("id") in ids:
            for s in walk(g):
                c = norm_colour(s.get("stop-color"))
                if c: cols.append(c)
    return cols or ["#808080"]

def image_colours(path):
    from PIL import Image
    im = Image.open(path).convert("RGBA").resize((70, 47))
    out = []
    for r, g, b, a in (im.get_flattened_data() if hasattr(im, 'get_flattened_data') else im.getdata()):
        if a > 200:
            out.append("#%02X%02X%02X" % (r, g, b))
    return out

_embedded = {}
def embed(path):
    if path not in _embedded:
        import base64, io
        from PIL import Image
        im = Image.open(path).convert("RGBA")
        im = im.resize((720, round(720 * im.height / im.width)), Image.LANCZOS)
        buf = io.BytesIO(); im.save(buf, "WEBP", quality=86, method=6)
        _embedded[path] = "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()
    return _embedded[path]

def pick(cols):
    lch = [(c,) + to_oklch(c) for c in set(cols)]
    light = max(lch, key=lambda x: x[1])
    dark = min(lch, key=lambda x: x[1])
    accent = max(lch, key=lambda x: x[2])
    return light, dark, accent

def recolour_tree(el, fn):
    for e in walk(el):
        for a in COLOUR_ATTRS:
            c = norm_colour(e.get(a))
            if c: e.set(a, fn(c))

def build(src_path, variant):
    tree = ET.parse(src_path)
    root = tree.getroot()
    defs = root.find(Q("defs"))
    if defs is None:
        defs = ET.SubElement(root, Q("defs")); root.remove(defs); root.insert(0, defs)
    kids = [c for c in root if c.tag not in (Q("title"), Q("desc"), Q("defs"))]
    gs = next(i for i, c in enumerate(kids)
              if c.tag == Q("ellipse") and c.get("cx") == "512" and float(c.get("cy", 0)) >= 900)
    bg, fg = kids[:gs], kids[gs:]
    ground = kids[gs]

    cols = palette(bg, defs, src_path.parent)
    light, dark, accent = pick(cols)
    # The liner's own shadow colour (its drop-shadow flood), else the darkest bg tone.
    flood = next((norm_colour(e.get("flood-color")) for e in walk(defs) if e.get("flood-color")), None) or dark[0]

    # Shadows take the colour of the material they fall on: the dome's own
    # darker gradient stop and the liner's darker pleat colour, deepened.
    def material_shadow(hexc, k):
        L, C, H = to_oklch(hexc)
        return from_oklch(L * k, min(0.2, C * 1.25 + 0.015), H)
    dome_dark = None
    for e in walk(root):
        if is_dome(e):
            m = re.match(r"url\(#([^)]+)\)", e.get("fill") or "")
            g = next((g for g in defs if m and g.get("id") == m.group(1)), None)
            stops = [c for c in (norm_colour(x.get("stop-color")) for x in walk(g)) if c] if g is not None else []
            if stops:
                dome_dark = min(stops, key=lambda c: to_oklch(c)[0]); break
            if norm_colour(e.get("fill")):
                dome_dark = norm_colour(e.get("fill")); break
    pleats = [norm_colour(e.get("fill")) for e in walk(root) if e.tag == Q("polygon") and norm_colour(e.get("fill"))]
    dome_shadow = material_shadow(dome_dark or flood, 0.66)
    liner_shadow = material_shadow(min(pleats, key=lambda c: to_oklch(c)[0]) if pleats else flood, 0.6)

    def add_def(xml):
        el = ET.fromstring('<svg xmlns="%s" xmlns:xlink="%s">%s</svg>' % (SVG, XLINK, xml))
        for c in el: defs.append(c)

    # --- background colour transform (copies of any gradients it references)
    if variant in ("default", "dark"):
        fn = vivid if variant == "default" else deepen
        ids = set()
        for el in bg: ids |= refs(el)
        for g in list(defs):
            gid = g.get("id")
            if gid in ids and g.tag in (Q("linearGradient"), Q("radialGradient")):
                ng = copy.deepcopy(g); ng.set("id", gid + "-rm")
                recolour_tree(ng, fn); defs.append(ng)
                for el in bg:
                    for e in walk(el):
                        for a in ("fill", "stroke"):
                            if e.get(a) == "url(#%s)" % gid: e.set(a, "url(#%s-rm)" % gid)
        for el in bg: recolour_tree(el, fn)
        # The one bitmap (Autism Acceptance infinity) goes through an equivalent filter.
        imgs = [e for el in bg for e in walk(el) if e.tag == Q("image")]
        # An SVG shown through <img> can't load other files, so the bitmap is
        # embedded (as a small WebP; it is drawn at most ~260 CSS px wide).
        for im in imgs:
            im.set("href", embed(src_path.parent / (im.get("href") or im.get("{%s}href" % XLINK))))
        if imgs:
            if variant == "default":
                add_def('<filter id="rmImg" color-interpolation-filters="sRGB"><feColorMatrix type="saturate" values="1.22"/></filter>')
            else:
                # The symbol itself stays vivid on the deep canvas.
                add_def('<filter id="rmImg" color-interpolation-filters="sRGB"><feComponentTransfer>'
                        '<feFuncR type="linear" slope="0.82"/><feFuncG type="linear" slope="0.82"/>'
                        '<feFuncB type="linear" slope="0.82"/></feComponentTransfer>'
                        '<feColorMatrix type="saturate" values="1.2"/></filter>')
            for im in imgs: im.set("filter", "url(#rmImg)")
    else:  # tinted: system tint over black; background art drops out
        for el in bg: root.remove(el)
        black = ET.Element(Q("rect"), {"width": "1024", "height": "1024", "fill": "#000000"})
        root.insert(list(root).index(ground), black)
        bg = [black]

    # --- lighting layers, coloured from this icon's own palette
    # A near-white canvas (Autism Muffin) gets a much lighter vignette, which
    # would otherwise read as grey haze.
    canvas = bg[0] if bg else None
    canvas_c = norm_colour(canvas.get("fill")) if canvas is not None and canvas.tag == Q("rect") else None
    light_canvas = bool(canvas_c) and to_oklch(canvas_c)[0] > 0.88
    if variant == "default":
        lL, lC, lH = to_oklch(light[0])
        bloom = from_oklch(max(lL, 0.9), lC * 0.55, lH); bloom_a = 0.45
        vig = from_oklch(dark[1] * 0.5, dark[2], dark[3]); vig_a = 0.42
        gloss_a, edge_a, key_a, rim_a = 0.22, 0.34, 0.5, 0.72
        if light_canvas:
            vig, vig_a, key_a = from_oklch(0.55, 0.02, dark[3]), 0.16, 0.2
    elif variant == "dark":
        aL, aC, aH = accent[1:]
        bloom = from_oklch(0.72, max(aC, 0.13) if aC >= 0.02 else aC, aH); bloom_a = 0.58
        vig = "#000000"; vig_a = 0.55
        gloss_a, edge_a, key_a, rim_a = 0.12, 0.26, 0.22, 0.6
    else:
        bloom = "#FFFFFF"; bloom_a = 0.16
        vig = "#000000"; vig_a = 0.0
        gloss_a, edge_a, key_a, rim_a = 0.06, 0.14, 0.0, 0.4

    add_def(
        f'<radialGradient id="rmBloom" cx="512" cy="560" r="500" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{bloom}" stop-opacity="{bloom_a}"/>'
        f'<stop offset=".42" stop-color="{bloom}" stop-opacity="{bloom_a * 0.42:.3f}"/>'
        f'<stop offset="1" stop-color="{bloom}" stop-opacity="0"/></radialGradient>'
        f'<radialGradient id="rmVig" cx="512" cy="470" r="760" gradientUnits="userSpaceOnUse">'
        f'<stop offset=".5" stop-color="{vig}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="{vig}" stop-opacity="{vig_a}"/></radialGradient>'
        f'<filter id="rmBlur18" x="-40%" y="-200%" width="180%" height="500%"><feGaussianBlur stdDeviation="18"/></filter>'
        f'<filter id="rmBlur6" x="-20%" y="-200%" width="140%" height="500%"><feGaussianBlur stdDeviation="6"/></filter>'
        f'<linearGradient id="rmLinerShade" x1="300" y1="0" x2="724" y2="0" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{liner_shadow}" stop-opacity=".42"/><stop offset=".34" stop-color="{liner_shadow}" stop-opacity="0"/>'
        f'<stop offset=".6" stop-color="{liner_shadow}" stop-opacity="0"/><stop offset="1" stop-color="{liner_shadow}" stop-opacity=".5"/></linearGradient>'
        f'<linearGradient id="rmAO" x1="0" y1="660" x2="0" y2="730" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{liner_shadow}" stop-opacity=".55"/><stop offset="1" stop-color="{liner_shadow}" stop-opacity="0"/></linearGradient>'
        f'<clipPath id="rmLinerClip"><polygon points="300,662 724,662 624,895 400,895"/></clipPath>'
        f'<linearGradient id="rmRim" x1="0" y1="290" x2="0" y2="560" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="#FFFFFF" stop-opacity=".85"/><stop offset=".55" stop-color="#FFFFFF" stop-opacity=".18"/>'
        f'<stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>'
        f'<radialGradient id="rmGloss" cx="330" cy="-80" r="660" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="#FFFFFF" stop-opacity="{gloss_a}"/><stop offset=".55" stop-color="#FFFFFF" stop-opacity="{gloss_a * 0.35:.3f}"/>'
        f'<stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></radialGradient>'
        f'<radialGradient id="rmKey" cx="170" cy="110" r="900" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="#FFFFFF" stop-opacity="{key_a}"/><stop offset=".7" stop-color="#FFFFFF" stop-opacity="0"/></radialGradient>'
        f'<linearGradient id="rmDomeShade" x1="0" y1="470" x2="0" y2="660" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{dome_shadow}" stop-opacity="0"/><stop offset="1" stop-color="{dome_shadow}" stop-opacity=".42"/></linearGradient>'
        f'<filter id="rmBlur14" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="14"/></filter>'
        f'<linearGradient id="rmEdge" x1="0" y1="0" x2="1024" y2="1024" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="#FFFFFF" stop-opacity="{edge_a}"/><stop offset=".45" stop-color="#FFFFFF" stop-opacity="{edge_a * 0.1:.3f}"/>'
        f'<stop offset="1" stop-color="#FFFFFF" stop-opacity="{edge_a * 0.5:.3f}"/></linearGradient>'
    )

    def el(tag, **attrs):
        return ET.Element(Q(tag), {k.replace("_", "-"): str(v) for k, v in attrs.items()})

    gi = list(root).index(ground)
    # Background lighting sits between the background art and the character.
    root.insert(gi, el("rect", width=1024, height=1024, fill="url(#rmVig)"))
    root.insert(gi, el("circle", cx=512, cy=560, r=500, fill="url(#rmBloom)"))
    if key_a:
        root.insert(gi, el("rect", width=1024, height=1024, fill="url(#rmKey)", style="mix-blend-mode:soft-light"))
    # Softer, deeper contact shadow under the existing one.
    gi = list(root).index(ground)
    root.insert(gi, el("ellipse", cx=512, cy=914, rx=268, ry=40, fill=flood,
                       opacity=0.42 if variant != "tinted" else 0.5, filter="url(#rmBlur18)"))

    # Rim light along the dome, right after the dome and its sheen, under
    # berries, face and accessories.
    domes = [e for e in walk(root) if is_dome(e)]
    if domes:
        parent = next(p for p in walk(root) if domes[-1] in list(p))
        d = domes[0].get("d")
        add_def(f'<clipPath id="rmDomeClip"><path d="{norm_d(d)}"/></clipPath>')
        idx = list(parent).index(domes[-1]) + 1
        dome_fx = el("g", clip_path="url(#rmDomeClip)")
        dome_fx.append(el("rect", x=220, y=470, width=590, height=200, fill="url(#rmDomeShade)"))
        dome_fx.append(el("ellipse", cx=418, cy=388, rx=96, ry=46, fill="#FFFFFF",
                          opacity=0.3 if variant != "tinted" else 0.2, transform="rotate(-24 418 388)", filter="url(#rmBlur14)"))
        dome_fx.append(el("path", d=norm_d(d), fill="none", stroke="url(#rmRim)", stroke_width=18, opacity=rim_a))
        parent.insert(idx, dome_fx)

    # Liner: ambient occlusion under the dome's lip and cylinder shading.
    shade = el("g", clip_path="url(#rmLinerClip)")
    shade.append(el("rect", x=300, y=662, width=424, height=240, fill="url(#rmLinerShade)"))
    shade.append(el("rect", x=300, y=662, width=424, height=70, fill="url(#rmAO)"))
    li = [i for i, c in enumerate(root) if any(e.tag == Q("polygon") for e in walk(c))]
    root.insert((li[0] + 1) if li else len(root), shade)

    # Glass: top highlight and edge rim, over everything.
    root.append(el("rect", width=1024, height=1024, fill="url(#rmGloss)"))
    root.append(el("rect", x=3, y=3, width=1018, height=1018, rx=228, fill="none",
                   stroke="url(#rmEdge)", stroke_width=4))

    if variant == "tinted":
        # iOS tints by luminance, so dark artwork (Neon Cyber) is lifted to
        # stay visible: greyscale, then a gamma curve that raises the darks.
        add_def('<filter id="rmMono" color-interpolation-filters="sRGB"><feColorMatrix type="saturate" values="0"/>'
                '<feComponentTransfer><feFuncR type="gamma" exponent="0.62"/><feFuncG type="gamma" exponent="0.62"/>'
                '<feFuncB type="gamma" exponent="0.62"/></feComponentTransfer></filter>')
        g = el("g", filter="url(#rmMono)")
        for c in [c for c in root if c.tag not in (Q("title"), Q("desc"), Q("defs"))]:
            root.remove(c); g.append(c)
        root.append(g)

    title = root.find(Q("title"))
    if title is not None:
        title.text = (title.text or "MuffinEMU icon") + {"default": "", "dark": " (dark)", "tinted": " (tinted)"}[variant]
    return tree


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for src in sorted(SRC.glob("*.svg")):
        for variant, suffix in (("default", ""), ("dark", "-dark"), ("tinted", "-tinted")):
            tree = build(src, variant)
            tree.write(OUT / f"{src.stem}{suffix}.svg", encoding="unicode", xml_declaration=False)
            n += 1
    print(f"{n} icons from {len(list(SRC.glob('*.svg')))} sources -> {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
