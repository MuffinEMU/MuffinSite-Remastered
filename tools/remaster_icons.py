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

The untouched originals are also written as <id>-original.svg (with any
bitmap embedded) so the site can compare them with the remaster.

On top of that, the default and dark variants get restrained lighting built
only from the icon's own colours: a soft key light, a backlight behind the
muffin in a lighter tone of the background's own hue (never white, which reads
as haze), a gentle corner vignette, a softer contact shadow, and shading on
the underside of the dome and the paper liner in the material's own darker
tone, clipped to the real shapes. Nothing is outlined or rimmed: iOS applies
its own mask, and baked-in borders or highlight strokes read as stray lines.
Tinted variants are the bare glyph: no glow, no shadows.

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
    """The colours of the background canvas itself: opaque fills, flag
    stripes, gradient stops and the bitmap. Soft overlays (the source art's
    faint glow circles, translucent shapes) are not canvas and are skipped,
    or a white glow would be read as the background colour."""
    gradients = {g.get("id"): g for g in defs}
    def stops_of(gid):
        g = gradients.get(gid)
        if g is None: return []
        return [(norm_colour(x.get("stop-color")), float(x.get("stop-opacity", 1))) for x in walk(g) if x.get("stop-color")]
    cols = []
    for el in bg_elems:
        for e in walk(el):
            if float(e.get("opacity", 1)) < 0.6:
                continue
            if e.tag == Q("image"):
                cols += image_colours(src_dir / (e.get("href") or e.get("{%s}href" % XLINK)))
                continue
            for a in ("fill", "stroke"):
                v = e.get(a) or ""
                m = re.match(r"url\(#([^)]+)\)", v)
                if m:
                    st = stops_of(m.group(1))
                    if st and min(o for _, o in st) >= 0.6:
                        cols += [c for c, _ in st if c]
                elif norm_colour(v):
                    cols.append(norm_colour(v))
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
    # The backlight comes from the lightest *coloured* tone when there is one
    # (a flag's white stripe would read as haze).
    chromatic = [x for x in lch if x[2] >= 0.04]
    light = max(chromatic or lch, key=lambda x: x[1])
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
    # An SVG shown through <img> can't load other files, so any bitmap is
    # embedded (as a small WebP; it is drawn at most ~260 CSS px wide).
    for im in [e for e in walk(root) if e.tag == Q("image")]:
        href = im.get("href") or im.get("{%s}href" % XLINK)
        if href and not href.startswith("data:"):
            im.set("href", embed(src_path.parent / href))
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
    pleat_els = [e for e in walk(root) if e.tag == Q("polygon") and (e.get("points") or "").strip()]
    pleats = [norm_colour(e.get("fill")) for e in pleat_els if norm_colour(e.get("fill"))]
    pleat_polys = ['<polygon points="%s"/>' % e.get("points") for e in pleat_els]
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
        if variant == "dark":
            for el in bg:
                for e in walk(el):
                    if e.get("filter") and e.tag != Q("image"): del e.attrib["filter"]
            # Autism Muffin cuts a white gap around the muffin so it reads
            # against the rings on a white canvas; on a dark canvas that gap
            # reads as a heavy outline, and the muffin already stands out.
            for el in list(bg):
                if el.tag == Q("path") and "L624,895" in norm_d(el.get("d")):
                    root.remove(el); bg.remove(el)
        # The one bitmap (Autism Acceptance infinity) goes through an equivalent filter.
        imgs = [e for el in bg for e in walk(el) if e.tag == Q("image")]
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
    else:  # tinted: system tint over black; the canvas drops out, symbols stay
        for el in bg:
            if not any(e.tag == Q("image") for e in walk(el)): root.remove(el)
        black = ET.Element(Q("rect"), {"width": "1024", "height": "1024", "fill": "#000000"})
        # Under everything that stayed (the symbol), not over it.
        root.insert(list(root).index(defs) + 1, black)
        bg = [black] + [el for el in bg if el in list(root)]

    # --- lighting layers, coloured from this icon's own palette
    # A near-white canvas (Autism Muffin) gets a much lighter vignette, which
    # would otherwise read as grey haze.
    canvas = bg[0] if bg else None
    canvas_c = norm_colour(canvas.get("fill")) if canvas is not None and canvas.tag == Q("rect") else None
    light_canvas = bool(canvas_c) and to_oklch(canvas_c)[0] > 0.88
    if variant == "default":
        # Backlight: the icon's own lightest background colour, a little
        # lighter, same hue and chroma (never white, which reads as haze).
        lL, lC, lH = to_oklch(light[0])
        bloom = from_oklch(min(0.96, lL + 0.09), lC, lH)
        flag = len(set(cols)) >= 5
        bloom_a = 0.22 if flag else 0.4    # flags: keep the stripes crisp
        vig = from_oklch(dark[1] * 0.55, dark[2], dark[3]); vig_a = 0.16 if flag else 0.3
        key_a = 0.28
        if light_canvas:
            vig, vig_a, key_a = from_oklch(0.55, 0.02, dark[3]), 0.12, 0.12
    elif variant == "dark":
        aL, aC, aH = accent[1:]
        bloom = from_oklch(0.66, max(aC, 0.12) if aC >= 0.02 else aC, aH); bloom_a = 0.5
        vig = "#000000"; vig_a = 0.5
        key_a = 0.12
    else:
        bloom = "#FFFFFF"; bloom_a = 0.1
        vig = "#000000"; vig_a = 0.0
        key_a = 0.0

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
        f'<clipPath id="rmLinerClip">{"".join(pleat_polys)}</clipPath>'
        f'<radialGradient id="rmKey" cx="170" cy="110" r="900" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="#FFFFFF" stop-opacity="{key_a}"/><stop offset=".7" stop-color="#FFFFFF" stop-opacity="0"/></radialGradient>'
        f'<linearGradient id="rmDomeShade" x1="0" y1="470" x2="0" y2="660" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{dome_shadow}" stop-opacity="0"/><stop offset="1" stop-color="{dome_shadow}" stop-opacity=".42"/></linearGradient>'

    )

    def el(tag, **attrs):
        return ET.Element(Q(tag), {k.replace("_", "-"): str(v) for k, v in attrs.items()})

    if variant == "tinted":
        ground.set("opacity", "0")
        for f in walk(defs):
            if f.tag == Q("feDropShadow"): f.set("flood-opacity", "0")
    gi = list(root).index(ground)
    # Background lighting sits between the background art and the character.
    if variant != "tinted":
        root.insert(gi, el("rect", width=1024, height=1024, fill="url(#rmVig)"))
        root.insert(gi, el("circle", cx=512, cy=560, r=500, fill="url(#rmBloom)"))
    if key_a:
        root.insert(gi, el("rect", width=1024, height=1024, fill="url(#rmKey)", style="mix-blend-mode:soft-light"))
    # Softer, deeper contact shadow under the existing one.
    gi = list(root).index(ground)
    if variant == "dark":
        ground.set("fill", "#000000")
        ground.set("opacity", str(max(0.3, float(ground.get("opacity", 0.2)))))
    if variant != "tinted":
        root.insert(gi, el("ellipse", cx=512, cy=914, rx=268, ry=40, fill=flood if variant == "default" else "#000000",
                           opacity=0.42 if variant == "default" else 0.5, filter="url(#rmBlur18)"))

    # Shading on the underside of the dome, right after the dome and its
    # sheen, under berries, face and accessories.
    domes = [e for e in walk(root) if is_dome(e)]
    if domes:
        parent = next(p for p in walk(root) if domes[-1] in list(p))
        d = domes[0].get("d")
        add_def(f'<clipPath id="rmDomeClip"><path d="{norm_d(d)}"/></clipPath>')
        idx = list(parent).index(domes[-1]) + 1
        dome_fx = el("g", clip_path="url(#rmDomeClip)")
        dome_fx.append(el("rect", x=220, y=470, width=590, height=200, fill="url(#rmDomeShade)"))
        parent.insert(idx, dome_fx)

    # Liner: ambient occlusion under the dome's lip and cylinder shading.
    shade = el("g", clip_path="url(#rmLinerClip)")
    shade.append(el("rect", x=300, y=662, width=424, height=240, fill="url(#rmLinerShade)"))
    shade.append(el("rect", x=300, y=662, width=424, height=70, fill="url(#rmAO)"))
    li = [i for i, c in enumerate(root) if any(e.tag == Q("polygon") for e in walk(c))]
    root.insert((li[0] + 1) if li else len(root), shade)


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
    # The untouched originals, for side-by-side comparison on the site. Only
    # change: any bitmap is embedded so the file works as an <img>.
    for src in sorted(SRC.glob("*.svg")):
        tree = ET.parse(src)
        for im in [e for e in walk(tree.getroot()) if e.tag == Q("image")]:
            href = im.get("href") or im.get("{%s}href" % XLINK)
            if href and not href.startswith("data:"):
                im.set("href", embed(src.parent / href))
        tree.write(OUT / f"{src.stem}-original.svg", encoding="unicode", xml_declaration=False)
    for src in sorted(SRC.glob("*.svg")):
        for variant, suffix in (("default", ""), ("dark", "-dark"), ("tinted", "-tinted")):
            tree = build(src, variant)
            tree.write(OUT / f"{src.stem}{suffix}.svg", encoding="unicode", xml_declaration=False)
            n += 1
    print(f"{n} icons from {len(list(SRC.glob('*.svg')))} sources -> {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
