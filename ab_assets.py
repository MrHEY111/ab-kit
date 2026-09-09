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
    schaltbild   Schaltplan aus Bauteilliste und Topologie (Reihe, Zweige)
    kreislauf    Stoffkreislauf, 2 bis 4 Stationen im Umlauf, Beschriftungsfelder je Pfeil

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


# ---------------------------------------------------------- schaltbild ---
#
# Deklarativer Schaltplan (Kit 1.4): Bauteile plus Topologie. Zeichenregeln,
# die auf den Arbeitsblaettern stehen und hier fest verdrahtet sind:
#   - nur waagerechte und senkrechte Leitungen, rechte Winkel
#   - genormte Schaltzeichen (DIN EN 60617)
#   - keine Bauteile in den Ecken (Eckabstand SB_ECKE)
#   - Schalter in Ruhestellung = offen; geschlossen nur auf Anforderung
#   - Voltmeter parallel (eigener Zweig), Amperemeter in Reihe
#
# Topologie: `reihe` ist der Umlauf im Uhrzeigersinn, Start auf der linken
# Seite. Ein Eintrag ist ein Bauteil {bauteil: …} oder eine Zweiggruppe
# {zweige: [[…], […]]}; jeder Zweig ist wieder eine Reihe aus Bauteilen
# (keine Verschachtelung). Gruppen auf einer senkrechten Seite werden als
# Leiter gezeichnet (Zweige parallel zur Seite, nach innen), Gruppen auf
# einer waagerechten Seite als Schleife nach aussen (Voltmeter-Bild).

SB_SEITEN = ("links", "oben", "rechts", "unten")
SB_ECKE = 24          # Eckabstand, Anzeige-px: kein Bauteil naeher an einer Ecke
SB_SLOT = 40          # Platzbedarf je Bauteil entlang der Leitung, Anzeige-px
SB_GRUPPE_RAND = 14   # Abstand Knoten <-> erstes Bauteil in einer Schleife
SB_RAND = 14          # Grundabstand Rechteck <-> Bildrand

_SB_ALIAS = {
    "batterie": "quelle", "spannungsquelle": "quelle",
    "gluehlampe": "lampe", "glühlampe": "lampe",
    "potentiometer": "widerstand_veraenderbar",
    "regelwiderstand": "widerstand_veraenderbar",
    "widerstand_veränderbar": "widerstand_veraenderbar",
    "verbindungspunkt": "verbindung", "knoten": "verbindung",
    "offen": "klemme", "offene_stelle": "klemme", "klemmstelle": "klemme",
    "pruefling": "klemme", "prüfling": "klemme",
    "leitung": "leer",
}
# Ausdehnung des Schaltzeichens nach aussen (Anzeige-px), fuer Raender/Labels
_SB_AUSSEN = {
    "quelle": 7, "lampe": 8, "schalter": 9, "taster": 14, "widerstand": 5.5,
    "widerstand_veraenderbar": 12, "amperemeter": 8, "voltmeter": 8,
    "motor": 8, "klingel": 9, "summer": 2, "led": 12, "diode": 6,
    "sicherung": 5.5, "kreuzung": 8, "verbindung": 2.5, "klemme": 3, "leer": 0,
}
_SB_LABEL_H = 11      # Hoehe einer Labelzeile (8 pt), Anzeige-px


class _SbRahmen:
    """
    Lokales Koordinatensystem eines Punktes auf dem Umlauf: u laeuft entlang
    der Leitung in Umlaufrichtung (Uhrzeigersinn), v zeigt nach aussen (vom
    Rechteck weg). Eingaben in Anzeige-px, Ausgaben in Renderpixeln.
    """

    def __init__(self, d, seite, cx, cy):
        self.d, self.seite, self.cx, self.cy = d, seite, cx, cy
        self.k = {"oben": 0, "rechts": 90, "unten": 180, "links": 270}[seite]

    def p(self, u, v):
        u, v = s(u), s(v)
        if self.seite == "oben":
            return (self.cx + u, self.cy - v)
        if self.seite == "rechts":
            return (self.cx + v, self.cy + u)
        if self.seite == "unten":
            return (self.cx - u, self.cy + v)
        return (self.cx - v, self.cy - u)                       # links

    def box(self, u0, v0, u1, v1):
        (xa, ya), (xb, yb) = self.p(u0, v0), self.p(u1, v1)
        return [min(xa, xb), min(ya, yb), max(xa, xb), max(ya, yb)]

    def line(self, pts, col, w):
        self.d.line([self.p(u, v) for u, v in pts], fill=col, width=w)

    def rect(self, u0, v0, u1, v1, **kw):
        self.d.rectangle(self.box(u0, v0, u1, v1), **kw)

    def ellipse(self, u0, v0, u1, v1, **kw):
        self.d.ellipse(self.box(u0, v0, u1, v1), **kw)

    def polygon(self, pts, **kw):
        self.d.polygon([self.p(u, v) for u, v in pts], **kw)

    def arc(self, u0, v0, u1, v1, t0, t1, col, w):
        """Bogen von t0 bis t1 (lokale Winkel, gegen den Uhrzeigersinn)."""
        self.d.arc(self.box(u0, v0, u1, v1), self.k - t1, self.k - t0,
                   fill=col, width=w)

    def text(self, u, v, txt, f, col, anchor="mm"):
        self.d.text(self.p(u, v), txt, font=f, fill=col, anchor=anchor)

    def pfeil(self, p0, p1, col, w):
        """Pfeil von p0 nach p1 (lokal) mit kleiner Spitze."""
        (u0, v0), (u1, v1) = p0, p1
        L = math.hypot(u1 - u0, v1 - v0) or 1
        du, dv = (u1 - u0) / L, (v1 - v0) / L
        self.line([p0, p1], col, w)
        self.polygon([(u1, v1),
                      (u1 - 4 * du + 2 * dv, v1 - 4 * dv - 2 * du),
                      (u1 - 4 * du - 2 * dv, v1 - 4 * dv + 2 * du)], fill=col)


def _sb_draht(d, x0, y0, x1, y1, lw, col):
    """Achsenparallele Leitung als Rechteck: pixelgenau, egal wer sie zeichnet."""
    h = lw // 2
    if y0 == y1:
        d.rectangle([min(x0, x1) - h, y0 - h, max(x0, x1) + h - 1, y0 + h - 1], fill=col)
    elif x0 == x1:
        d.rectangle([x0 - h, min(y0, y1) - h, x0 + h - 1, max(y0, y1) + h - 1], fill=col)
    else:
        raise ValueError("schaltbild: Leitung muss waagerecht oder senkrecht sein")


def _sb_knoten(d, x, y, col):
    r = s(2.5)
    d.ellipse([x - r, y - r, x + r, y + r], fill=col)


def _sb_bauteil(e):
    """Eintrag normalisieren; bei unbekanntem Bauteil abbrechen."""
    name = str(e.get("bauteil", "")).strip().lower()
    name = _SB_ALIAS.get(name, name)
    if name not in _SB_AUSSEN:
        sys.exit(f"Abbruch: schaltbild — unbekanntes Bauteil '{e.get('bauteil')}'. "
                 f"Bekannt: {', '.join(_SB_AUSSEN)}")
    e = dict(e)
    e["bauteil"] = name
    if name == "schalter":
        z = str(e.get("zustand", "offen")).lower()
        if z not in ("offen", "geschlossen"):
            sys.exit(f"Abbruch: schaltbild — schalter.zustand '{z}' unbekannt "
                     "(offen | geschlossen).")
        e["zustand"] = z
    return e


def _sb_aussen(e):
    """Ausdehnung nach aussen inkl. Polzeichen und Label (Anzeige-px)."""
    ext = _SB_AUSSEN[e["bauteil"]]
    if e["bauteil"] == "quelle" and e.get("pole"):
        ext = 17
    return ext


def _sb_symbol(fr, e, col, lw, fonts):
    """Schaltzeichen um den Ursprung des Rahmens; Leitung liegt schon darunter."""
    name = e["bauteil"]
    W = "white"
    f_sym, f_pol = fonts["sym"], fonts["pol"]
    flip = -1 if e.get("umgekehrt") else 1
    if name == "leer":
        return
    if name == "quelle":
        n = max(1, int(e.get("zellen", 1)))
        b = (n - 1) * 8 + 4
        fr.rect(-b / 2 - 1, -8, b / 2 + 1, 8, fill=W)
        for i in range(n):
            c = (i - (n - 1) / 2) * 8
            # langer Strich = Pluspol, in Umlaufrichtung hinten (links: oben)
            fr.line([(c + 2 * flip, -7), (c + 2 * flip, 7)], col, lw)
            fr.line([(c - 2 * flip, -4), (c - 2 * flip, 4)], col, lw * 2)
        if e.get("pole"):
            fr.text((b / 2 + 2) * flip, 12, "+", f_pol, col)
            fr.text(-(b / 2 + 2) * flip, 12, "–", f_pol, col)
    elif name == "lampe":
        fr.ellipse(-8, -8, 8, 8, outline=col, width=lw, fill=W)
        k = 8 * 0.707
        fr.line([(-k, -k), (k, k)], col, lw)
        fr.line([(-k, k), (k, -k)], col, lw)
    elif name in ("amperemeter", "voltmeter", "motor"):
        fr.ellipse(-8, -8, 8, 8, outline=col, width=lw, fill=W)
        fr.text(0, 0, {"amperemeter": "A", "voltmeter": "V", "motor": "M"}[name],
                f_sym, col)
    elif name in ("widerstand", "sicherung", "widerstand_veraenderbar"):
        fr.rect(-15, -5.5, 15, 5.5, outline=col, width=lw, fill=W)
        if name == "sicherung":
            fr.line([(-15, 0), (15, 0)], col, lw)
        elif name == "widerstand_veraenderbar":
            fr.pfeil((-11, -11), (11, 11), col, lw)
    elif name == "schalter":
        fr.rect(-11, -2, 11, 10, fill=W)
        if e["zustand"] == "geschlossen":
            fr.line([(-10, 0), (10, 0)], col, lw)
        else:
            fr.line([(-10, 0), (9, 8)], col, lw)
        fr.ellipse(-12, -2, -8, 2, fill=col)
    elif name == "taster":
        fr.rect(-9, -2, 9, 3, fill=W)
        fr.line([(-8, 0), (-8, 4)], col, lw)
        fr.line([(8, 0), (8, 4)], col, lw)
        fr.line([(-10, 7), (10, 7)], col, lw)
        fr.line([(0, 7), (0, 13)], col, lw)
        fr.line([(-5, 13), (5, 13)], col, lw)
    elif name == "klingel":
        fr.arc(-9, -9, 9, 9, 0, 180, col, lw)
    elif name == "summer":
        fr.arc(-9, -9, 9, 9, 180, 360, col, lw)
    elif name in ("diode", "led"):
        fr.polygon([(-6 * flip, -6), (-6 * flip, 6), (6 * flip, 0)], fill=col)
        fr.line([(6 * flip, -6), (6 * flip, 6)], col, lw)
        if name == "led":
            fr.pfeil((-1, 6), (4, 11), col, lw)
            fr.pfeil((4, 5), (9, 10), col, lw)
    elif name == "kreuzung":
        fr.line([(0, -8), (0, 8)], col, lw)
    elif name == "verbindung":
        fr.ellipse(-2.5, -2.5, 2.5, 2.5, fill=col)
    elif name == "klemme":
        fr.rect(-9, -4, 9, 4, fill=W)
        fr.ellipse(-11, -3, -5, 3, outline=col, width=lw, fill=W)
        fr.ellipse(5, -3, 11, 3, outline=col, width=lw, fill=W)
    # Label nach aussen, immer aufrecht
    lbl = e.get("label")
    if lbl not in (None, ""):
        f = fonts["lbl_i"] if e.get("label_stil") == "kursiv" else fonts["lbl"]
        anchor = {"oben": "md", "rechts": "lm", "unten": "ma", "links": "rm"}[fr.seite]
        fr.text(0, _sb_aussen(e) + 3, str(lbl), f, col, anchor)


def _sb_items(a):
    """`reihe` einlesen: Bauteile normalisieren, Gruppen pruefen."""
    reihe = a.get("reihe")
    if not isinstance(reihe, list) or not reihe:
        sys.exit("Abbruch: schaltbild — 'reihe' fehlt oder ist leer.")
    items = []
    for it in reihe:
        if not isinstance(it, dict):
            sys.exit(f"Abbruch: schaltbild — Eintrag muss ein Mapping sein: {it!r}")
        if "zweige" in it:
            zw = it["zweige"]
            if not isinstance(zw, list) or not zw or not all(isinstance(z, list) and z for z in zw):
                sys.exit("Abbruch: schaltbild — 'zweige' muss eine Liste nichtleerer Listen sein.")
            zweige = []
            for z in zw:
                bt = []
                for e in z:
                    if not isinstance(e, dict) or "zweige" in e:
                        sys.exit("Abbruch: schaltbild — Zweige duerfen nur Bauteile "
                                 "enthalten (keine Verschachtelung).")
                    bt.append(_sb_bauteil(e))
                zweige.append(bt)
            g = {"zweige": zweige}
            if it.get("seite"):
                g["seite"] = it["seite"]
            items.append(g)
        else:
            items.append(_sb_bauteil(it))
    return items


def _sb_seiten(items):
    """Seitenzuordnung: entweder alle Eintraege mit `seite` oder automatisch."""
    pinned = [it.get("seite") for it in items]
    seiten = {sd: [] for sd in SB_SEITEN}
    if any(pinned):
        if not all(pinned):
            sys.exit("Abbruch: schaltbild — entweder tragen alle Eintraege in "
                     "'reihe' ein Feld 'seite' oder keiner.")
        for it in items:
            sd = str(it["seite"]).lower()
            if sd not in SB_SEITEN:
                sys.exit(f"Abbruch: schaltbild — seite '{it['seite']}' unbekannt "
                         f"({' | '.join(SB_SEITEN)}).")
            seiten[sd].append(it)
    else:
        if "zweige" in items[0]:
            sys.exit("Abbruch: schaltbild — der erste Eintrag der Reihe darf ohne "
                     "'seite' keine Zweiggruppe sein (er kommt auf die linke Seite).")
        seiten["links"].append(items[0])
        rest = items[1:]
        gidx = [i for i, it in enumerate(rest) if "zweige" in it]
        if gidx:
            g = gidx[0]
            seiten["oben"], seiten["rechts"], seiten["unten"] = rest[:g], [rest[g]], rest[g + 1:]
        else:
            base, extra = divmod(len(rest), 3)
            n_o = base + (1 if extra >= 1 else 0)
            n_u = base + (1 if extra >= 2 else 0)
            seiten["oben"] = rest[:n_o]
            seiten["rechts"] = rest[n_o:n_o + base]
            seiten["unten"] = rest[n_o + base:]
    for sd in ("links", "rechts"):
        if any("zweige" in it for it in seiten[sd]) and len(seiten[sd]) > 1:
            sys.exit(f"Abbruch: schaltbild — auf der Seite '{sd}' kann eine "
                     "Zweiggruppe (Leiter) nicht mit weiteren Bauteilen stehen.")
    return seiten


def gen_schaltbild(a):
    """
    breite:       Anzeigebreite px (Default 260); hoehe optional (sonst aus Inhalt)
    reihe:        Umlauf im Uhrzeigersinn ab links: Bauteile
                  {bauteil, label, label_stil: kursiv, zustand (schalter),
                   zellen, pole, umgekehrt (quelle/diode/led), farbe, seite}
                  oder Zweiggruppen {zweige: [[…], […]], seite}
    zweigabstand: Abstand paralleler Zweige, Anzeige-px (Default 44)
    farbe:        Linienfarbe (Default 1A1A1A); je Bauteil ueberschreibbar
    Bauteile: quelle, lampe, schalter, taster, widerstand,
      widerstand_veraenderbar (potentiometer), amperemeter, voltmeter, motor,
      klingel, summer, led, diode, sicherung, kreuzung, verbindung, klemme
      (offene Stelle), leer (Leitungsstueck). Aliasse siehe _SB_ALIAS.
    """
    items = _sb_items(a)
    seiten = _sb_seiten(items)
    W_PT = int(a.get("breite", 260))
    dz = a.get("zweigabstand", 44)
    dark = farbe(a.get("farbe"), (26, 26, 26))
    lw = int(1.6 * SCALE)
    fonts = {"lbl": font("regular", 8), "lbl_i": font("italic", 8),
             "sym": font("bold", 10), "pol": font("bold", 9)}
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10), "white"))

    def label_w(e):
        lbl = e.get("label")
        if lbl in (None, ""):
            return 0
        f = fonts["lbl_i"] if e.get("label_stil") == "kursiv" else fonts["lbl"]
        return probe.textlength(str(lbl), font=f) / SCALE

    def ext_h(e):                       # Ausdehnung nach aussen, waagerechte Seite
        return _sb_aussen(e) + (3 + _SB_LABEL_H if label_w(e) else 0)

    def ext_v(e):                       # Ausdehnung nach aussen, senkrechte Seite
        return _sb_aussen(e) + (3 + label_w(e) if label_w(e) else 0)

    # --- Raender aus dem Inhalt
    leiter = {}                          # senkrechte Seite -> Zweigzahl (Leiter)
    for sd in ("links", "rechts"):
        for it in seiten[sd]:
            if "zweige" in it:
                leiter[sd] = len(it["zweige"])
    pad = {}
    for sd in SB_SEITEN:
        ext = 0
        for it in seiten[sd]:
            if "zweige" in it:
                if sd in ("oben", "unten"):
                    aussen_zweig = it["zweige"][-1]
                    ext = max(ext, (len(it["zweige"]) - 1) * dz +
                              max(ext_h(e) for e in aussen_zweig))
                else:
                    ext = max(ext, max(ext_v(e) for e in it["zweige"][0]))
            else:
                ext = max(ext, ext_h(it) if sd in ("oben", "unten") else ext_v(it))
        pad[sd] = max(22, SB_RAND + ext)

    rect_w = W_PT - pad["links"] - pad["rechts"]

    # --- Platzbedarf entlang der Seiten
    def slot(it):
        if "zweige" in it:
            n = max(len(z) for z in it["zweige"])
            return 2 * SB_GRUPPE_RAND + n * SB_SLOT
        return SB_SLOT

    need_v = 2 * SB_ECKE
    for sd in ("links", "rechts"):
        for it in seiten[sd]:
            if "zweige" in it:
                need_v = max(need_v, 2 * SB_ECKE + max(len(z) for z in it["zweige"]) * SB_SLOT)
            else:
                need_v = max(need_v, 2 * SB_ECKE + len(seiten[sd]) * SB_SLOT)
    if "hoehe" in a:
        rect_h = int(a["hoehe"]) - pad["oben"] - pad["unten"]
    else:
        rect_h = max(int(0.55 * rect_w), need_v, 60)
    if rect_h < need_v:
        sys.exit(f"Abbruch: schaltbild — hoehe {a.get('hoehe')} zu klein, "
                 f"mindestens {need_v + pad['oben'] + pad['unten']} noetig.")

    # nutzbarer Bereich je Seite (Leiter auf links/rechts rueckt die Enden ein)
    off_l = (leiter.get("links", 1) - 1) * dz
    off_r = (leiter.get("rechts", 1) - 1) * dz
    bereich = {
        "oben": (SB_ECKE + off_l, rect_w - SB_ECKE - off_r),
        "unten": (SB_ECKE + off_r, rect_w - SB_ECKE - off_l),
        "links": (SB_ECKE, rect_h - SB_ECKE),
        "rechts": (SB_ECKE, rect_h - SB_ECKE),
    }
    for sd in SB_SEITEN:
        its = [it for it in seiten[sd] if not ("zweige" in it and sd in ("links", "rechts"))]
        bedarf = sum(slot(it) for it in its)
        frei = bereich[sd][1] - bereich[sd][0]
        if bedarf > frei:
            sys.exit(f"Abbruch: schaltbild — Seite '{sd}' zu kurz ({frei:.0f} px "
                     f"frei, {bedarf} px noetig); breite/hoehe erhoehen oder "
                     "Bauteile anders verteilen.")

    # --- Bild und Rechteck
    W = s(W_PT)
    H = s(pad["oben"] + rect_h + pad["unten"])
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    x0, y0 = s(pad["links"]), s(pad["oben"])
    x1, y1 = x0 + s(rect_w), y0 + s(rect_h)
    _sb_draht(d, x0, y0, x1, y0, lw, dark)
    _sb_draht(d, x1, y0, x1, y1, lw, dark)
    _sb_draht(d, x1, y1, x0, y1, lw, dark)
    _sb_draht(d, x0, y1, x0, y0, lw, dark)
    # Umlaufrahmen je Seite: Ursprung am Seitenanfang (Uhrzeigersinn)
    start = {"oben": (x0, y0), "rechts": (x1, y0), "unten": (x1, y1), "links": (x0, y1)}
    laenge = {"oben": rect_w, "unten": rect_w, "links": rect_h, "rechts": rect_h}

    zeichnen = []                        # (Rahmen, Bauteil) — nach den Leitungen

    def platziere(sd, its, t0, t1, v):
        """Bauteile `its` gleichmaessig zwischen t0 und t1 auf Hoehe v."""
        fr = _SbRahmen(d, sd, *start[sd])
        bedarf = sum(slot(it) for it in its)
        luecke = (t1 - t0 - bedarf) / (len(its) + 1)
        t = t0
        for it in its:
            t += luecke
            mitte = t + slot(it) / 2
            if "zweige" in it:           # Schleife nach aussen (waagerechte Seite)
                ta, tb = t + 4, t + slot(it) - 4
                k = len(it["zweige"])
                for j in range(1, k):
                    _sb_draht(d, *fr.p(ta, j * dz), *fr.p(tb, j * dz), lw, dark)
                if k > 1:
                    _sb_draht(d, *fr.p(ta, 0), *fr.p(ta, (k - 1) * dz), lw, dark)
                    _sb_draht(d, *fr.p(tb, 0), *fr.p(tb, (k - 1) * dz), lw, dark)
                    _sb_knoten(d, *fr.p(ta, 0), dark)
                    _sb_knoten(d, *fr.p(tb, 0), dark)
                for j, zweig in enumerate(it["zweige"]):
                    platziere(sd, zweig, t + SB_GRUPPE_RAND, t + slot(it) - SB_GRUPPE_RAND, v + j * dz)
            else:
                cx, cy = fr.p(mitte, v)
                zeichnen.append((_SbRahmen(d, sd, cx, cy), it))
            t += slot(it)

    for sd in SB_SEITEN:
        its = seiten[sd]
        if sd in ("links", "rechts") and its and "zweige" in its[0]:
            # Leiter: Zweig 0 ist die Seite selbst, weitere nach innen
            fr = _SbRahmen(d, sd, *start[sd])
            L = laenge[sd]
            for j, zweig in enumerate(its[0]["zweige"]):
                if j:
                    _sb_draht(d, *fr.p(0, -j * dz), *fr.p(L, -j * dz), lw, dark)
                    _sb_knoten(d, *fr.p(0, -j * dz), dark)
                    _sb_knoten(d, *fr.p(L, -j * dz), dark)
                platziere(sd, zweig, *bereich[sd], -j * dz)
        else:
            platziere(sd, its, *bereich[sd], 0)

    for fr, e in zeichnen:
        _sb_symbol(fr, e, farbe(e.get("farbe"), dark), lw, fonts)
    return img


# ----------------------------------------------------------- kreislauf ---

def gen_kreislauf(a):
    """
    Stoffkreislauf mit 2 bis 4 Stationen im Umlauf (Uhrzeigersinn, erste
    Station oben) und einem Beschriftungskaestchen auf jedem Uebergang.
    Aussen bleibt ein freier Rand, in den die SuS eigene Pfeile eintragen.

    Langform:
      stationen:  Liste der Stationstexte, 2 bis 4 (Pflicht)
      pfeile:     je Uebergang ein {label: "..."} — Station 1 -> 2, 2 -> 3,
                  ..., letzte -> 1 (Umlauf schliesst sich). Genau so viele
                  Eintraege wie stationen; fehlt der Block: leere Kaestchen.
    Kurzform (Zweistationen-Fall, rendert bitgleich zur Vorstufe
    kreislauf_gen.py vom 09.09.2026):
      oben, unten:    Text in den beiden Kaesten
      rechts, links:  je {label: "..."} — rechter (abwaerts) bzw. linker
                      (aufwaerts) Pfeil; fehlendes oder leeres label = leeres
                      Kaestchen zum Eintragen
    Kurz- und Langform gemischt = Abbruch.

    breite, hoehe:  Anzeigegroesse px (Default 430 x 205)
    feld:           [breite, hoehe] des Beschriftungskaestchens (Default 112 x 30)
    aussenrand:     freier Rand links und rechts (Default 46); die senkrechten
                    Leitungen liegen bei aussenrand + feld[0]/2
    pt:             Schriftgroesse in Punkt (Default 10)
    farbe:          Linienfarbe (Default 1A1A1A)

    Anordnung: 2 Stationen oben/unten, 3 Stationen Dreieck (oben, unten
    rechts, unten links), 4 Stationen Rechteck (Ecken). Nur waagerechte und
    senkrechte Leitungen, rechte Winkel, Labels aufrecht, kein Kaestchen in
    einer Ecke. Reicht der Platz nicht (Kasten breiter als der Leitungs-
    abstand, Kasten ueber dem Bildrand, Label breiter als feld, Leitung
    kuerzer als das Kaestchen), Abbruch mit Angabe der Seite.
    """
    kurz = [k for k in ("oben", "unten", "rechts", "links") if k in a]
    lang = [k for k in ("stationen", "pfeile") if k in a]
    if kurz and lang:
        sys.exit("Abbruch: kreislauf — Kurzform (" + ", ".join(kurz) + ") und "
                 "Langform (" + ", ".join(lang) + ") gemischt. Entweder "
                 "oben/unten/rechts/links oder stationen/pfeile.")
    if lang:
        st = a.get("stationen")
        if not isinstance(st, list) or not 2 <= len(st) <= 4:
            sys.exit("Abbruch: kreislauf — 'stationen' braucht 2 bis 4 Eintraege, "
                     f"hat {len(st) if isinstance(st, list) else st!r}.")
        st = [str(x) for x in st]
        pf = a.get("pfeile")
        if pf is None:
            pf = [{} for _ in st]
        if not isinstance(pf, list) or len(pf) != len(st):
            sys.exit(f"Abbruch: kreislauf — 'pfeile' braucht genau {len(st)} "
                     "Eintraege (einen je Uebergang, Station 1 -> 2 zuerst), hat "
                     f"{len(pf) if isinstance(pf, list) else pf!r}.")
        for p in pf:
            if p is not None and not isinstance(p, dict):
                sys.exit("Abbruch: kreislauf — Eintrag in 'pfeile' muss ein "
                         f"Mapping {{label: ...}} sein: {p!r}")
        labels = [str((p or {}).get("label", "") or "") for p in pf]
    else:
        st = [str(a.get("oben", "")), str(a.get("unten", ""))]
        labels = [str((a.get(seite) or {}).get("label", "") or "")
                  for seite in ("rechts", "links")]
    n = len(st)

    W_PT = a.get("breite", 430)
    H_PT = a.get("hoehe", 205)
    W, H = s(W_PT), s(H_PT)
    col = farbe(a.get("farbe"), (26, 26, 26))
    pt = a.get("pt", 10)
    f_b = font("bold", pt)
    f_r = font("regular", pt)
    lw = int(round(1.6 * SCALE))
    ah = s(6)                                   # Pfeilspitze
    A = ah * 1.7                                # Laenge der Spitze

    fw_pt, fh_pt = (a.get("feld") or [112, 30])[:2]
    fw, fh = s(fw_pt), s(fh_pt)
    rand = s(a.get("aussenrand", 46))
    g = s(14)                                   # Mindestlaenge Leitung vor Kasten/Kaestchen

    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    cx = W / 2
    pad_x, pad_y = s(10), s(6)
    bh = int(round(pt * SCALE * 96 / 72)) + 2 * pad_y
    y_o = s(3) + bh / 2                         # Mitte obere Kaesten
    y_u = H - s(3) - bh / 2                     # Mitte untere Kaesten
    x_r = W - rand - fw / 2                     # senkrechte Leitung rechts
    x_l = rand + fw / 2                         # senkrechte Leitung links

    if n == 2:
        pos = [(cx, y_o), (cx, y_u)]
    elif n == 3:
        pos = [(cx, y_o), (x_r, y_u), (x_l, y_u)]
    else:
        pos = [(x_l, y_o), (x_r, y_o), (x_r, y_u), (x_l, y_u)]

    # --- Platzpruefung vor dem Zeichnen: Abbruch statt stiller Ueberlappung
    bw = [d.textlength(txt, font=f_b) + 2 * pad_x for txt in st]

    def px(v):
        return f"{v / SCALE:.0f} px"

    def mittig(i, seite):
        frei = 2 * (x_r - cx - g)
        if bw[i] > frei:
            sys.exit(f"Abbruch: kreislauf — Kasten '{st[i]}' ({px(bw[i])}) zu breit "
                     f"fuer die Seite '{seite}' ({px(frei)} zwischen den Leitungen): "
                     "breite erhoehen, aussenrand/feld verkleinern oder Text kuerzen.")

    def paar(i, j, seite):
        frei = (x_r - x_l) - fw - 2 * g
        if bw[i] / 2 + bw[j] / 2 > frei:
            sys.exit(f"Abbruch: kreislauf — Kaesten '{st[i]}' und '{st[j]}' lassen auf "
                     f"der Seite '{seite}' keinen Platz fuer das Kaestchen "
                     f"({px(bw[i] / 2 + bw[j] / 2)} belegt, {px(frei)} frei): breite "
                     "erhoehen, aussenrand/feld verkleinern oder Text kuerzen.")

    def bildrand(i, seite):
        x, _ = pos[i]
        if x - bw[i] / 2 < s(3) or x + bw[i] / 2 > W - s(3):
            sys.exit(f"Abbruch: kreislauf — Kasten '{st[i]}' ({px(bw[i])}) ragt auf der "
                     f"Seite '{seite}' ueber den Bildrand: breite oder aussenrand "
                     "erhoehen oder Text kuerzen.")

    def leitung(laenge, seite):
        if laenge < fh + 2 * g:
            sys.exit(f"Abbruch: kreislauf — hoehe {H_PT} zu klein: die Leitung "
                     f"'{seite}' ({px(laenge)}) fasst das Kaestchen ({fh_pt} px) "
                     f"plus 2 x 14 px nicht.")

    if n == 2:
        mittig(0, "oben")
        mittig(1, "unten")
        leitung(y_u - y_o, "rechts")
    elif n == 3:
        mittig(0, "oben")
        paar(1, 2, "unten")
        bildrand(1, "rechts")
        bildrand(2, "links")
        leitung((y_u - bh / 2) - y_o, "rechts")
    else:
        paar(0, 1, "oben")
        paar(2, 3, "unten")
        bildrand(0, "links")
        bildrand(1, "rechts")
        bildrand(2, "rechts")
        bildrand(3, "links")
        leitung((y_u - bh / 2) - (y_o + bh / 2), "rechts")
    pad_l = s(5)
    for label in labels:
        if label and d.textlength(label, font=f_r) + 2 * pad_l > fw:
            sys.exit(f"Abbruch: kreislauf — Label '{label}' "
                     f"({px(d.textlength(label, font=f_r) + 2 * pad_l)}) passt nicht in "
                     f"feld {fw_pt} px: feld verbreitern oder Label kuerzen.")

    # --- Stationen
    def kasten(txt, xm, ym, w):
        x0, x1 = xm - w / 2, xm + w / 2
        d.rounded_rectangle([x0, ym - bh / 2, x1, ym + bh / 2], radius=s(5),
                            outline=col, width=lw, fill="white")
        d.text((xm, ym), txt, font=f_b, fill=col, anchor="mm")
        return x0, x1, ym - bh / 2, ym + bh / 2

    kanten = [kasten(st[i], *pos[i], bw[i]) for i in range(n)]

    def spitze(p, richtung):
        x, y = p
        if richtung == "links":
            d.polygon([(x, y), (x + ah * 1.7, y - ah), (x + ah * 1.7, y + ah)], fill=col)
        elif richtung == "rechts":
            d.polygon([(x, y), (x - ah * 1.7, y - ah), (x - ah * 1.7, y + ah)], fill=col)
        elif richtung == "oben":
            d.polygon([(x, y), (x - ah, y + ah * 1.7), (x + ah, y + ah * 1.7)], fill=col)
        else:
            d.polygon([(x, y), (x - ah, y - ah * 1.7), (x + ah, y - ah * 1.7)], fill=col)

    def weg(pts):
        d.line(pts, fill=col, width=lw, joint="curve")

    # --- Pfeile im Uhrzeigersinn; Kaestchen auf der Mitte eines geraden
    #     Stuecks, nie in einer Ecke
    if n == 2:
        (xo0, xo1, _, _), (xu0, xu1, _, _) = kanten
        # rechter Pfeil: oberer Kasten -> rechts -> abwaerts -> unterer Kasten
        weg([(xo1, y_o), (x_r, y_o), (x_r, y_u), (xu1 + A, y_u)])
        spitze((xu1 + s(1), y_u), "links")
        # linker Pfeil: unterer Kasten -> links -> aufwaerts -> oberer Kasten
        weg([(xu0, y_u), (x_l, y_u), (x_l, y_o), (xo0 - A, y_o)])
        spitze((xo0 - s(1), y_o), "rechts")
        ym = (y_o + y_u) / 2
        felder = [(x_r, ym), (x_l, ym)]
    elif n == 3:
        (xo0, xo1, _, _), (xr0, xr1, yr0, _), (xl0, xl1, yl0, _) = kanten
        weg([(xo1, y_o), (x_r, y_o), (x_r, yr0 - A)])
        spitze((x_r, yr0 - s(1)), "unten")
        weg([(xr0, y_u), (xl1 + A, y_u)])
        spitze((xl1 + s(1), y_u), "links")
        weg([(x_l, yl0), (x_l, y_o), (xo0 - A, y_o)])
        spitze((xo0 - s(1), y_o), "rechts")
        felder = [(x_r, (y_o + yr0) / 2), ((xr0 + xl1) / 2, y_u),
                  (x_l, (yl0 + y_o) / 2)]
    else:
        (a0, a1, ay0, ay1), (b0, b1, by0, by1), (c0, c1, cy0, cy1), \
            (e0, e1, ey0, ey1) = kanten
        weg([(a1, y_o), (b0 - A, y_o)])
        spitze((b0 - s(1), y_o), "rechts")
        weg([(x_r, by1), (x_r, cy0 - A)])
        spitze((x_r, cy0 - s(1)), "unten")
        weg([(c0, y_u), (e1 + A, y_u)])
        spitze((e1 + s(1), y_u), "links")
        weg([(x_l, ey0), (x_l, ay1 + A)])
        spitze((x_l, ay1 + s(1)), "oben")
        felder = [((a1 + b0) / 2, y_o), (x_r, (by1 + cy0) / 2),
                  ((c0 + e1) / 2, y_u), (x_l, (ey0 + ay1) / 2)]

    # Beschriftungskaestchen
    for (x, y), label in zip(felder, labels):
        d.rectangle([x - fw / 2, y - fh / 2, x + fw / 2, y + fh / 2],
                    outline=col, width=lw, fill="white")
        if label:
            d.text((x, y), label, font=f_r, fill=col, anchor="mm")
    return img


GENERATOREN = {
    "scaffold": gen_scaffold,
    "balkenraster": gen_balkenraster,
    "achsenkreuz": gen_achsenkreuz,
    "schaltplan": gen_schaltplan,
    "stromkreis": gen_stromkreis,
    "kennlinien": gen_kennlinien,
    "bilddatei": gen_bilddatei,
    "schaltbild": gen_schaltbild,
    "kreislauf": gen_kreislauf,
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
