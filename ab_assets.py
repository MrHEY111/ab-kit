#!/usr/bin/env python3
r"""
ab_assets.py — AB-Kit · Asset-Generatoren (PNG)
=====================================================================
Liest den Block `assets:` einer Spec (YAML) und erzeugt jedes Asset als
RGB-PNG plus Sidecar `<name>.json` mit der natuerlichen Anzeigegroesse in
Pixeln (96 dpi), die ab_kit.js beim Einbetten verwendet.

Aufruf:
    python ab_assets.py <spec.yaml> [--out DIR]

    --out DIR   Zielordner (Default: <kit>\_build\<ausgabe-stamm>\)

Generatoren (Feld `typ` je Asset):
    scaffold     um 180 Grad gedrehter Merksatz-Notanker (Zeilen [stil, text])
    balkenraster leeres Balkendiagramm-Raster (y-Achse, Kategorien)
    achsenkreuz  leeres Achsenkreuz, optional Gitter und leere Beschriftungsfelder
    schaltplan   Stromkreis Quelle/Bauteil, optional mit Messgeraeten (Loesung)
    kennlinien   U-I-Diagramm mit Messreihen und Ausgleichskurven (Loesung)
    bilddatei    vorhandene Bilddatei (Foto, Scan) mit Zuschnitt und Graustufen

Fallen, die hier gekapselt sind (siehe README.md):
  - Alle PNGs RGB, nie RGBA (RGBA laesst den docx-Render abstuerzen).
  - Gedrehte Texte als Bild (PIL), nie als OOXML-Rotation.
  - Fonts ueber Fallbackkette (Liberation -> Arial -> DejaVu), keine festen
    Pfade — Liberation Sans und Arial sind metrisch kompatibel.
  - Renderskalierung SCALE (4x): das PNG traegt 4x so viele Pixel wie es im
    Dokument breit ist; die Anzeigegroesse steht im Sidecar-JSON.
"""
import json
import math
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML fehlt: pip install pyyaml")

KIT_DIR = Path(__file__).resolve().parent
SPEC_DIR = KIT_DIR              # Ordner der Spec, fuer relative Bildpfade
SCALE = 4                       # Renderaufloesung relativ zu 96 dpi

# --------------------------------------------------------------- Fonts ---

_FONT_CHAIN = {
    "regular": [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/calibri.ttf",
    ],
    "bold": [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
    ],
    "italic": [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
        "C:/Windows/Fonts/ariali.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    ],
}
_font_cache = {}


def font(style, pt):
    """Schrift in Punkt (bezogen auf 96 dpi) x SCALE, ueber Fallbackkette."""
    px = int(round(pt * SCALE * 96 / 72))
    key = (style, px)
    if key in _font_cache:
        return _font_cache[key]
    for pfad in _FONT_CHAIN[style]:
        if os.path.isfile(pfad):
            f = ImageFont.truetype(pfad, px)
            _font_cache[key] = f
            return f
    print(f"  Warnung: kein TrueType-Font fuer '{style}' gefunden, "
          "PIL-Default (Metrik weicht ab).")
    f = ImageFont.load_default()
    _font_cache[key] = f
    return f


def s(v):
    """Punkt -> Renderpixel."""
    return int(round(v * SCALE))


def farbe(v, default=(60, 60, 60)):
    if v is None:
        return default
    if isinstance(v, (list, tuple)):
        return tuple(v)
    v = str(v).lstrip("#")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def speichern(img, out, name):
    """RGB erzwingen, PNG + Sidecar mit Anzeigegroesse schreiben."""
    img = img.convert("RGB")
    png = out / f"{name}.png"
    img.save(png, "PNG", dpi=(96 * SCALE, 96 * SCALE))
    dims = {"breite_px": round(img.width / SCALE),
            "hoehe_px": round(img.height / SCALE)}
    (out / f"{name}.json").write_text(json.dumps(dims), encoding="utf-8")
    print(f"  {name}.png  {img.width}x{img.height}px  "
          f"-> {dims['breite_px']}x{dims['hoehe_px']}px im Dokument")


# ------------------------------------------------------------ scaffold ---

def gen_scaffold(a):
    """
    zeilen:   Liste [stil, text]; stil 'b' fett, 'r' regular, 'i' kursiv
    pt:       Schriftgroesse (Default 9)
    zeilenabstand: Faktor (Default 1.55)
    innenabstand:  pt (Default 8)
    farbe:    Textfarbe (Default 404040)
    """
    pt = a.get("pt", 9)
    gap = a.get("zeilenabstand", 1.55)
    pad = s(a.get("innenabstand", 8) * 96 / 72)
    col = farbe(a.get("farbe"), (64, 64, 64))
    zeilen = a["zeilen"]
    px = int(round(pt * SCALE * 96 / 72))
    lh = int(px * gap)
    stile = {"b": "bold", "r": "regular", "i": "italic"}

    probe = ImageDraw.Draw(Image.new("RGB", (10, 10), "white"))
    width = 0
    for stil, text in zeilen:
        width = max(width, int(probe.textlength(text, font=font(stile[stil], pt))))
    W, H = width + 2 * pad, lh * len(zeilen) + 2 * pad
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    if a.get("rahmen"):
        d.rectangle([1, 1, W - 2, H - 2], outline=(140, 140, 140), width=SCALE)
    y = pad
    for stil, text in zeilen:
        d.text((pad, y), text, font=font(stile[stil], pt), fill=col)
        y += lh
    return img.rotate(180)


# ---------------------------------------------------------- stromkreis ---

def gen_stromkreis(a):
    """
    Stromkreis im Stil PH-10.SGE-WH (Wiederholung.py): Lampe oben, Quelle
    unten mit Polen, optional Amperemeter in Reihe oder Voltmeter parallel.
    breite:      Anzeigegroesse px (Default 245; Hoehe folgt)
    messgeraet:  null | A | V
    """
    mess = a.get("messgeraet")
    W_PT = a.get("breite", 245)
    H_PT = int(W_PT * 0.60)
    W, H = s(W_PT), s(H_PT)
    dark, rot = (0, 0, 0), farbe(a.get("farbe_mess"), (220, 20, 60))
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    lw = int(1.5 * SCALE)
    f = font("regular", 7)
    f_b = font("bold", 10)
    f_lbl = font("bold", 7)

    x0, x1 = s(24), W - s(24)
    y0 = s(38 if mess == "V" else 24)          # obere Leitung
    y1 = H - s(26)                             # untere Leitung
    lx, lr = (x0 + x1) / 2, s(9)               # Lampe
    ax_, ar = x0 + (lx - x0) * 0.45, s(8)      # Amperemeter

    # obere Leitung mit Luecken
    luecken = [(lx - lr, lx + lr)]
    if mess == "A":
        luecken.insert(0, (ax_ - ar, ax_ + ar))
    x = x0
    for a_, b_ in luecken:
        d.line([(x, y0), (a_, y0)], fill=dark, width=lw)
        x = b_
    d.line([(x, y0), (x1, y0)], fill=dark, width=lw)
    d.line([(x0, y0), (x0, y1)], fill=dark, width=lw)
    d.line([(x1, y0), (x1, y1)], fill=dark, width=lw)
    # Lampe
    d.ellipse([lx - lr, y0 - lr, lx + lr, y0 + lr], outline=dark, width=lw, fill="white")
    k = lr * 0.707
    d.line([(lx - k, y0 - k), (lx + k, y0 + k)], fill=dark, width=lw)
    d.line([(lx - k, y0 + k), (lx + k, y0 - k)], fill=dark, width=lw)
    tw = d.textlength("Lampe", font=f)
    d.text((lx - tw / 2, y0 + lr + s(3)), "Lampe", font=f, fill=dark)
    # untere Leitung mit Quelle
    qx = (x0 + x1) / 2
    d.line([(x0, y1), (qx - s(7), y1)], fill=dark, width=lw)
    d.line([(qx + s(7), y1), (x1, y1)], fill=dark, width=lw)
    d.line([(qx - s(4), y1 - s(11)), (qx - s(4), y1 + s(11))], fill=dark, width=int(2.2 * SCALE))
    d.line([(qx + s(3), y1 - s(5)), (qx + s(3), y1 + s(5))], fill=dark, width=int(4.5 * SCALE))
    d.text((qx - s(9), y1 - s(22)), "+", font=f_b, fill=dark)
    d.text((qx + s(4), y1 - s(22)), "–", font=f_b, fill=dark)
    tw = d.textlength("Quelle", font=f)
    d.text((qx - tw / 2, y1 + s(12)), "Quelle", font=f, fill=dark)
    # Messgeraete
    if mess == "A":
        d.ellipse([ax_ - ar, y0 - ar, ax_ + ar, y0 + ar], outline=rot, width=lw, fill="white")
        tw = d.textlength("A", font=f_b)
        d.text((ax_ - tw / 2, y0 - s(7)), "A", font=f_b, fill=rot)
        tw = d.textlength("in Reihe", font=f_lbl)
        d.text((ax_ - tw / 2, y0 - ar - s(11)), "in Reihe", font=f_lbl, fill=rot)
    elif mess == "V":
        vy = y0 - s(20)
        al, arr = lx - s(23), lx + s(23)
        d.line([(al, y0), (al, vy), (lx - ar, vy)], fill=rot, width=lw, joint="curve")
        d.line([(lx + ar, vy), (arr, vy), (arr, y0)], fill=rot, width=lw, joint="curve")
        d.ellipse([lx - ar, vy - ar, lx + ar, vy + ar], outline=rot, width=lw, fill="white")
        tw = d.textlength("V", font=f_b)
        d.text((lx - tw / 2, vy - s(7)), "V", font=f_b, fill=rot)
        d.text((arr + s(6), vy - s(5)), "parallel zur Lampe", font=f_lbl, fill=rot)
    return img


# -------------------------------------------------------- balkenraster ---

def gen_balkenraster(a):
    """
    breite, hoehe:  Anzeigegroesse in px (Default 300 x 190)
    y_titel:        Achsentitel (gedreht)
    y_max, y_schritt
    kategorien:     Liste; Zeilenumbruch mit \\n
    """
    W_PT, H_PT = a.get("breite", 300), a.get("hoehe", 190)
    ymax, ystep = a.get("y_max", 12), a.get("y_schritt", 2)
    W, H = s(W_PT), s(H_PT)
    f_ax = font("regular", 8)
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    left, right = s(62), W - s(10)
    top, bottom = s(10), H - s(34)

    for v in range(0, ymax + 1, ystep):
        y = bottom - (bottom - top) * v / ymax
        d.line([(left, y), (right, y)], fill=(200, 200, 200), width=SCALE)
        lbl = str(v)
        tw = d.textlength(lbl, font=f_ax)
        d.text((left - s(8) - tw, y - s(5)), lbl, font=f_ax, fill=(80, 80, 80))
    d.line([(left, top), (left, bottom)], fill=(60, 60, 60), width=SCALE)
    d.line([(left, bottom), (right, bottom)], fill=(60, 60, 60), width=SCALE)

    title = a.get("y_titel", "")
    if title:
        tw = int(d.textlength(title, font=f_ax))
        strip = Image.new("RGB", (tw + s(4), s(12)), "white")
        ImageDraw.Draw(strip).text((s(2), 0), title, font=f_ax, fill=(80, 80, 80))
        strip = strip.rotate(90, expand=True)
        img.paste(strip, (s(6), int((top + bottom) / 2 - strip.height / 2)))

    cats = a.get("kategorien", [])
    span = (right - left) / max(len(cats), 1)
    for i, c in enumerate(cats):
        cx = left + span * (i + 0.5)
        for j, line in enumerate(str(c).split("\n")):
            lw = d.textlength(line, font=f_ax)
            d.text((cx - lw / 2, bottom + s(6 + j * 11)), line,
                   font=f_ax, fill=(60, 60, 60))
        d.line([(cx, bottom), (cx, bottom + s(3))], fill=(60, 60, 60), width=SCALE)
    return img


# --------------------------------------------------------- achsenkreuz ---

def gen_achsenkreuz(a):
    """
    breite, hoehe:  Anzeigegroesse px (Default 160 x 130)
    x_label, y_label: Achsenbeschriftung ('U in V', 'I')
    gitter:         [nx, ny] Kaestchen (optional)
    felder:         {x: n, y: n} leere Beschriftungskaestchen (optional)
    pfeile:         Pfeilspitzen an den Achsen (Default true)
    """
    W_PT, H_PT = a.get("breite", 160), a.get("hoehe", 130)
    W, H = s(W_PT), s(H_PT)
    f = font("regular", 8)
    f_it = font("italic", 9)
    dark = (40, 40, 40)
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    felder = a.get("felder") or {}
    gitter = a.get("gitter")
    # Platz fuer Felder links / unten
    left = s(30 if felder.get("y") else 18)
    bottom = H - s(24 if felder.get("x") else 16)
    top, right = s(12), W - s(14)

    if gitter:
        nx, ny = gitter
        for i in range(nx + 1):
            x = left + (right - left) * i / nx
            d.line([(x, top), (x, bottom)], fill=(190, 190, 190), width=SCALE)
        for j in range(ny + 1):
            y = bottom - (bottom - top) * j / ny
            d.line([(left, y), (right, y)], fill=(190, 190, 190), width=SCALE)
    lw = int(1.4 * SCALE)
    d.line([(left, bottom), (right, bottom)], fill=dark, width=lw)
    d.line([(left, bottom), (left, top)], fill=dark, width=lw)
    if a.get("pfeile", True):
        ah = s(4)
        d.polygon([(right, bottom), (right - ah * 1.6, bottom - ah),
                   (right - ah * 1.6, bottom + ah)], fill=dark)
        d.polygon([(left, top), (left - ah, top + ah * 1.6),
                   (left + ah, top + ah * 1.6)], fill=dark)
    xl, yl = a.get("x_label", ""), a.get("y_label", "")
    if yl:
        d.text((left + s(5), top - s(2)), yl, font=f_it, fill=dark)
    if xl:
        tw = d.textlength(xl, font=f_it)
        d.text((right - tw, bottom + s(3)), xl, font=f_it, fill=dark)
    # leere Beschriftungsfelder
    fx, fy = felder.get("x", 0), felder.get("y", 0)
    box_w, box_h = s(14), s(9)
    if fx and gitter:
        nx = gitter[0]
        for i in range(1, fx + 1):
            x = left + (right - left) * i / nx
            d.rectangle([x - box_w / 2, bottom + s(4), x + box_w / 2,
                         bottom + s(4) + box_h], outline=(120, 120, 120),
                        width=SCALE, fill="white")
    if fy and gitter:
        ny = gitter[1]
        for j in range(1, fy + 1):
            y = bottom - (bottom - top) * j / ny
            d.rectangle([left - s(4) - box_w, y - box_h / 2, left - s(4),
                         y + box_h / 2], outline=(120, 120, 120),
                        width=SCALE, fill="white")
    return img


# ---------------------------------------------------------- schaltplan ---

def gen_schaltplan(a):
    """
    breite:      Anzeigegroesse px (Default 170; Hoehe folgt)
    quelle:      Beschriftung der Quelle (Default 'U')
    bauteil:     Beschriftung des Bauteils (Default 'Bauteil')
    messgeraete: false | true — Voltmeter parallel + Amperemeter in Reihe (rot)
    """
    mess = bool(a.get("messgeraete", False))
    W_PT = a.get("breite", 170)
    H_PT = int(W_PT * (0.62 if not mess else 0.78))
    W, H = s(W_PT), s(H_PT)
    dark, rot = (26, 26, 26), farbe(a.get("farbe_mess"), (179, 38, 30))
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    lw = int(1.6 * SCALE)
    f = font("regular", 8)
    f_b = font("bold", 10)
    f_it = font("italic", 9)

    # Rechteck
    pad_x, pad_top = s(22), s(30 if mess else 14)
    pad_bot = s(30 if mess else 14)
    x0, x1 = pad_x, W - pad_x
    y0, y1 = pad_top, H - pad_bot
    bw, bh = s(30), s(11)
    bx = (x0 + x1) / 2
    # oberer Draht mit Bauteil
    d.line([(x0, y0), (bx - bw / 2, y0)], fill=dark, width=lw)
    d.line([(bx + bw / 2, y0), (x1, y0)], fill=dark, width=lw)
    d.rectangle([bx - bw / 2, y0 - bh / 2, bx + bw / 2, y0 + bh / 2],
                outline=dark, width=lw, fill="white")
    bt = a.get("bauteil", "Bauteil")
    tw = d.textlength(bt, font=f)
    d.text((bx - tw / 2, y0 - bh / 2 - s(10)), bt, font=f, fill=dark)
    # rechter Draht
    d.line([(x1, y0), (x1, y1)], fill=dark, width=lw)
    # linker Draht mit Quelle
    qy = (y0 + y1) / 2
    d.line([(x0, y0), (x0, qy - s(7))], fill=dark, width=lw)
    d.line([(x0, qy + s(7)), (x0, y1)], fill=dark, width=lw)
    for k, (halb, dick) in enumerate([(s(7), lw), (s(4), lw * 2),
                                      (s(7), lw), (s(4), lw * 2)]):
        yy = qy - s(6) + k * s(4)
        d.line([(x0 - halb, yy), (x0 + halb, yy)], fill=dark, width=dick)
    ql = a.get("quelle", "U")
    tw = d.textlength(ql, font=f_it)
    d.text((x0 - s(10) - tw, qy - s(6)), ql, font=f_it, fill=dark)
    # unterer Draht
    if mess:
        ar = s(8)
        d.line([(x0, y1), (bx - ar, y1)], fill=dark, width=lw)
        d.line([(bx + ar, y1), (x1, y1)], fill=dark, width=lw)
        d.ellipse([bx - ar, y1 - ar, bx + ar, y1 + ar], outline=rot,
                  width=lw, fill="white")
        tw = d.textlength("A", font=f_b)
        d.text((bx - tw / 2, y1 - s(7)), "A", font=f_b, fill=rot)
        lbl = "Amperemeter \u2014 in Reihe"
        tw = d.textlength(lbl, font=f)
        d.text((bx - tw / 2, y1 + ar + s(3)), lbl, font=f, fill=rot)
        # Voltmeter parallel
        vy = y0 - s(20)
        al, arr = bx - s(38), bx + s(38)
        d.line([(al, y0), (al, vy)], fill=rot, width=lw)
        d.line([(arr, y0), (arr, vy)], fill=rot, width=lw)
        d.line([(al, vy), (bx - ar, vy)], fill=rot, width=lw)
        d.line([(bx + ar, vy), (arr, vy)], fill=rot, width=lw)
        for xx in (al, arr):
            d.ellipse([xx - s(2), y0 - s(2), xx + s(2), y0 + s(2)], fill=rot)
        d.ellipse([bx - ar, vy - ar, bx + ar, vy + ar], outline=rot,
                  width=lw, fill="white")
        tw = d.textlength("V", font=f_b)
        d.text((bx - tw / 2, vy - s(7)), "V", font=f_b, fill=rot)
        lbl = "Voltmeter \u2014 parallel zum Bauteil"
        tw = d.textlength(lbl, font=f)
        d.text((bx - tw / 2, vy - ar - s(12)), lbl, font=f, fill=rot)
    else:
        d.line([(x0, y1), (x1, y1)], fill=dark, width=lw)
    return img


# ---------------------------------------------------------- kennlinien ---

def gen_kennlinien(a):
    """
    breite, hoehe:  Anzeigegroesse px (Default 300 x 245)
    x_max, x_schritt, y_max, y_schritt, y_dezimal (Nachkommastellen)
    x_label, y_label
    reihen: [{name, u: [...], i: [...], farbe, marker: kreis|quadrat,
              kurve: gerade|potenz|keine}]
    """
    W_PT, H_PT = a.get("breite", 300), a.get("hoehe", 245)
    W, H = s(W_PT), s(H_PT)
    xmax, xstep = a.get("x_max", 12), a.get("x_schritt", 2)
    ymax, ystep = a.get("y_max", 0.58), a.get("y_schritt", 0.1)
    ydez = a.get("y_dezimal", 1)
    dark = (26, 26, 26)
    f = font("regular", 8)
    f_it = font("italic", 9)
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    left, right = s(34), W - s(12)
    top, bottom = s(16), H - s(26)

    def X(u):
        return left + (right - left) * u / xmax

    def Y(i):
        return bottom - (bottom - top) * i / ymax

    # Gitter + Ticks
    v = 0
    while v <= xmax + 1e-9:
        d.line([(X(v), top), (X(v), bottom)], fill=(200, 200, 200), width=SCALE)
        lbl = str(v)
        tw = d.textlength(lbl, font=f)
        d.text((X(v) - tw / 2, bottom + s(3)), lbl, font=f, fill=dark)
        v += xstep
    v = 0
    while v <= ymax + 1e-9:
        d.line([(left, Y(v)), (right, Y(v))], fill=(200, 200, 200), width=SCALE)
        lbl = f"{v:.{ydez}f}".replace(".", ",")
        tw = d.textlength(lbl, font=f)
        d.text((left - s(4) - tw, Y(v) - s(5)), lbl, font=f, fill=dark)
        v = round(v + ystep, 6)
    lw = int(1.4 * SCALE)
    d.line([(left, bottom), (right, bottom)], fill=dark, width=lw)
    d.line([(left, bottom), (left, top)], fill=dark, width=lw)
    xl, yl = a.get("x_label", "U in V"), a.get("y_label", "I in A")
    tw = d.textlength(xl, font=f_it)
    d.text((right - tw, bottom + s(12)), xl, font=f_it, fill=dark)
    d.text((left + s(4), top - s(13)), yl, font=f_it, fill=dark)

    # Reihen
    leg = []
    for r in a.get("reihen", []):
        col = farbe(r.get("farbe"), dark)
        us, is_ = r["u"], r["i"]
        kurve = r.get("kurve", "keine")
        pts = None
        if kurve == "gerade" and us:
            k = sum(i / u for u, i in zip(us, is_) if u) / len(us)
            pts = [(X(u), Y(k * u)) for u in
                   [xmax * t / 200 for t in range(201)] if k * u <= ymax]
        elif kurve == "potenz" and len(us) >= 2:
            # Fit i = c * u^e ueber Log-Regression
            lu = [math.log(u) for u in us]
            li = [math.log(i) for i in is_]
            n = len(lu)
            mu, mi = sum(lu) / n, sum(li) / n
            e = sum((x - mu) * (y - mi) for x, y in zip(lu, li)) / \
                sum((x - mu) ** 2 for x in lu)
            c = math.exp(mi - e * mu)
            pts = [(X(u), Y(c * u ** e)) for u in
                   [xmax * t / 200 for t in range(201)] if c * u ** e <= ymax]
        if pts and len(pts) > 1:
            d.line(pts, fill=col, width=int(1.8 * SCALE), joint="curve")
        ms = s(3)
        for u, i in zip(us, is_):
            x, y = X(u), Y(i)
            if r.get("marker", "kreis") == "quadrat":
                d.rectangle([x - ms, y - ms, x + ms, y + ms], fill=col)
            else:
                d.ellipse([x - ms, y - ms, x + ms, y + ms], fill=col)
        leg.append((r.get("name", ""), col, r.get("marker", "kreis")))
    # Legende unten rechts
    if leg:
        lh = s(12)
        tw = max(d.textlength(n, font=f) for n, _, _ in leg)
        bw, bh = tw + s(24), lh * len(leg) + s(6)
        bx1, by1 = right - s(6), bottom - s(6)
        d.rectangle([bx1 - bw, by1 - bh, bx1, by1], fill="white",
                    outline=(200, 200, 200), width=SCALE)
        for k, (n, col, mk) in enumerate(leg):
            cy = by1 - bh + s(3) + lh * k + lh / 2
            cx = bx1 - bw + s(9)
            ms = s(3)
            if mk == "quadrat":
                d.rectangle([cx - ms, cy - ms, cx + ms, cy + ms], fill=col)
            else:
                d.ellipse([cx - ms, cy - ms, cx + ms, cy + ms], fill=col)
            d.text((cx + s(8), cy - s(5)), n, font=f, fill=dark)
    return img


# ----------------------------------------------------------- bilddatei ---

def gen_bilddatei(a):
    """
    Bindet eine vorhandene Bilddatei ein (Foto, Scan, extern erzeugtes PNG).

    pfad:         Pfad zur Datei; relative Pfade gegen den Ordner der Spec
    breite:       Anzeigebreite in px bei 96 dpi, Hoehe proportional (Default 160)
    beschnitt:    {links, oben, rechts, unten} als Anteil 0..1, vor dem Skalieren
    graustufen:   true -> Graustufen (Default false)
    autokontrast: true -> Tonwertspreizung (Default false)
    cutoff:       Prozent fuer autokontrast (Default 1)
    rahmen:       true -> duenner Rahmen; rahmenfarbe optional
    """
    pfad = Path(str(a["pfad"]))
    if not pfad.is_absolute():
        pfad = (SPEC_DIR / pfad).resolve()
    if not pfad.is_file():
        sys.exit(f"Abbruch: Bilddatei nicht gefunden: {pfad}")

    img = Image.open(pfad)
    if img.mode in ("RGBA", "LA", "P"):        # Transparenz auf Weiss legen
        img = img.convert("RGBA")
        hg = Image.new("RGB", img.size, "white")
        hg.paste(img, mask=img.split()[-1])
        img = hg
    else:
        img = img.convert("RGB")

    b = a.get("beschnitt") or {}
    if b:
        W, H = img.size
        img = img.crop((int(round(b.get("links", 0) * W)),
                        int(round(b.get("oben", 0) * H)),
                        int(round((1 - b.get("rechts", 0)) * W)),
                        int(round((1 - b.get("unten", 0)) * H))))

    if a.get("graustufen"):
        img = img.convert("L")
    if a.get("autokontrast"):
        img = ImageOps.autocontrast(img, cutoff=a.get("cutoff", 1))
    img = img.convert("RGB")

    zb = s(a.get("breite", 160))
    img = img.resize((zb, max(1, int(round(img.height * zb / img.width)))),
                     Image.LANCZOS)

    if a.get("rahmen"):
        ImageDraw.Draw(img).rectangle(
            [0, 0, img.width - 1, img.height - 1],
            outline=farbe(a.get("rahmenfarbe"), (140, 140, 140)), width=SCALE)
    return img


GENERATOREN = {
    "scaffold": gen_scaffold,
    "balkenraster": gen_balkenraster,
    "achsenkreuz": gen_achsenkreuz,
    "schaltplan": gen_schaltplan,
    "stromkreis": gen_stromkreis,
    "kennlinien": gen_kennlinien,
    "bilddatei": gen_bilddatei,
}


# ---------------------------------------------------------------- main ---

def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    global SPEC_DIR
    spec_pfad = Path(argv[1]).resolve()
    SPEC_DIR = spec_pfad.parent
    out = None
    if "--out" in argv:
        out = Path(argv[argv.index("--out") + 1]).resolve()
    spec = yaml.safe_load(spec_pfad.read_text(encoding="utf-8"))
    if out is None:
        stamm = Path(spec.get("ausgabe", spec_pfad.stem)).stem
        out = KIT_DIR / "_build" / stamm
    out.mkdir(parents=True, exist_ok=True)

    kit_version = (KIT_DIR / "KIT_VERSION").read_text(encoding="utf-8").strip()
    sv = str(spec.get("kit_version", ""))
    if sv.split(".")[0] != kit_version.split(".")[0]:
        sys.exit(f"Abbruch: Spec kit_version {sv} passt nicht zu KIT_VERSION "
                 f"{kit_version} (Major).")
    if sv != kit_version:
        print(f"  Hinweis: Spec kit_version {sv}, Kit ist {kit_version}.")

    assets = spec.get("assets") or {}
    if not assets:
        print("Keine assets in der Spec.")
        return
    print(f"Assets -> {out}")
    for name, a in assets.items():
        typ = a.get("typ")
        if typ not in GENERATOREN:
            sys.exit(f"Abbruch: Asset '{name}' hat unbekannten typ '{typ}'. "
                     f"Bekannt: {', '.join(GENERATOREN)}")
        speichern(GENERATOREN[typ](a), out, name)


if __name__ == "__main__":
    main(sys.argv)
