#!/usr/bin/env node
/*
 * ab_kit.js — AB-Kit · Renderer (Spec -> docx)
 * ===========================================================================
 * Liest eine deklarative Spec (YAML) und baut daraus ein Arbeitsblatt oder
 * einen Erwartungshorizont als docx. Ein Renderer, alle Unterschiede zwischen
 * Blaettern stehen in der Spec (Inhalt) oder in deren `stil:`-Block
 * (Geometrie, Schrift, Kastenchrom). Profile liefern Defaults fuer `stil:`.
 *
 * Aufruf:
 *   node ab_kit.js <spec.yaml> [--out DIR] [--pdf] [--force] [--check]
 *
 *   --out DIR   Zielordner (Default: <kit>\_build\<ausgabe-stamm>\); dort
 *               muessen die Assets liegen (vorher: python ab_assets.py <spec>)
 *   --pdf       zusaetzlich PDF ueber soffice --headless erzeugen
 *   --force     Lauf trotz abweichender Major-Version in kit_version
 *   --check     nur Spec- und Bauplan-Check (kein docx, keine Assets noetig)
 *
 * Bauplan-Check (Kit 1.2): Jedes AB wird beim Bau gegen den Bauplan aus
 * _Grundsaetze\AB_Qualitaet.md Teil A geprueft (Stundenfrage, Merksatz-
 * Anschluss, verdeckter Scaffold, Sprinteraufgabe, AFB-Progression ueber
 * `afb:` und Materialbezug ueber `bezug:` je aufgabe). Nur Warnungen, nie
 * Abbruch — die Pruefung ersetzt die Prueffragen nicht, sie faengt
 * Strukturfehler.
 *
 * Pflichtfelder der Spec: kit_version, block, titel, zweig, ausgabe, stand,
 * seiten. Elementtypen: siehe ELEMENTE unten; unbekannter Typ = Abbruch.
 *
 * Aufgabenzitate (Kit 1.5): Eine Loesungs-Spec mit `ab_spec: <AB-Spec>` (Pfad
 * relativ zum Spec-Ordner) laesst `aufgabe`-Elemente mit `zitat: true` und
 * ohne `text` ihren Wortlaut aus der Aufgabe gleicher `nr` des Arbeitsblatts
 * holen. Kit 1.6: ebenso `teilaufgabe` mit `zitat: true` und `buchstabe`,
 * gematcht unter der vorangehenden aufgabe gleicher `nr`. Vorhandener `text`
 * gewinnt. Siehe zitateAufloesen().
 *
 * Uebungsblaetter (Kit 1.8): `dokumenttyp: uebung` baut ein Blatt wie eine
 * Arbeit — Aufgaben in AFB-Reihenfolge I -> II -> III, `punkte` je (Teil-)
 * Aufgabe rechtsbuendig, Kasten `afb3_hinweis` vor der ersten AFB-III-Aufgabe.
 * Der Stunden-Bauplan A-1..A-5 gilt dort nicht; stattdessen Ue-1..Ue-5
 * (AFB-Anteile gegen config\afb_richtwert.json je `zweig` oder
 * `afb_richtwert`, AFB III freiwillig, Reihenfolge, Punkte, Fremdelemente).
 * Eine Loesung mit `ab_spec` auf eine uebung-Spec uebernimmt punkte und afb
 * der zitierten Aufgaben und haengt ein Bewertungsraster (`punkteraster`) an.
 *
 * Fallen, die hier gekapselt sind (README.md fuehrt die Liste):
 *   - kein spacing.line im Default-Style (schneidet Bilder ab)
 *   - leerer Absatz nach jeder Tabelle (LibreOffice verschmilzt sonst
 *     aufeinanderfolgende Tabellen) — automatisch, siehe tabelleMitSpacer()
 *   - WidthType.DXA + columnWidths bei ungleichen Spalten
 *   - Bilder nur als RGB-PNG (ab_assets.py erzwingt das)
 *   - gedrehte Texte als PNG, nie OOXML-Rotation
 *   - nach dem letzten Tabstop mit Leader muss ein Zeichen folgen
 *     (lueckenzeile haengt sonst ein geschuetztes Leerzeichen an)
 *   - nutzbare Breite = 11906 - rand.links - rand.rechts (A4 in twips)
 *   - Notanker im Seitenfuss ueber Section-Footer, damit er nie auf eine
 *     Folgeseite rutscht; der untere Rand wird dafuer automatisch erhoeht
 */

"use strict";

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

// Modulaufloesung: lokales node_modules zuerst, sonst globales npm-Root.
// Grund: npm install auf Google Drive (G:) schreibt 0-Byte-Dateien — auf
// Windows deshalb `npm install -g docx yaml`, im Linux-Container lokal.
(() => {
  const kandidaten = [
    process.env.APPDATA ? path.join(process.env.APPDATA, "npm", "node_modules") : null,
    "/usr/local/lib/node_modules", "/usr/lib/node_modules",
  ].filter(Boolean);
  for (const k of kandidaten) if (fs.existsSync(k)) module.paths.push(k);
})();

const YAML = require("yaml");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, Footer,
  WidthType, BorderStyle, AlignmentType, ImageRun, HeightRule, VerticalAlign,
  TabStopType, LeaderType, PageBreak, LineRuleType,
} = require("docx");

const KIT_DIR = __dirname;
const KIT_VERSION = fs.readFileSync(path.join(KIT_DIR, "KIT_VERSION"), "utf8").trim();
// AFB-Richtwerte je Schulzweig (Kit 1.8). Kopie des lernkontrolle-Skills,
// Quelle und Stand stehen in der Datei; Schluessel mit "_" sind Kommentar.
const AFB_RICHTWERT = (() => {
  const roh = JSON.parse(fs.readFileSync(path.join(KIT_DIR, "config", "afb_richtwert.json"), "utf8"));
  return Object.fromEntries(Object.entries(roh).filter(([k]) => !k.startsWith("_")));
})();
const AFB_TOLERANZ_DEFAULT = 5;       // Prozentpunkte, wie die LK (lernkontrolle-Skill: ±5)
const AFB3_HINWEIS_DEFAULT = "Zusatz \u2014 freiwillig. Diese Aufgaben zeigen, was f\u00fcr eine sehr gute Leistung gebraucht wird.";
const A4_BREITE = 11906;                       // twips

/* ======================================================= Profile / Stil == */

const FARBEN_BASIS = {
  text: "000000", dunkel: "1A1A1A", grau: "595959", hellgrau: "8C8C8C",
  rahmen: "808080", hell: "F2F2F2", akzent: "B3261E",
};

const PROFILE = {
  // CH-09.WAS · AB_Wasserbestandteile_GR (build_ab.js, 31.08.2026)
  kompakt: {
    font: "Calibri", groesse: 22, farbe_text: "text",
    rand: { oben: 850, unten: 850, links: 850, rechts: 850 },
    kaesten: "schlicht", kopfzeile_variante: "zeile",
    kopfzeile_groesse: 18, titel_groesse: 32, untertitel_groesse: 20,
    abschnitt_groesse: 24, aufgabe_groesse: 24, aufgabe_text_groesse: 24,
    anweisung_groesse: 20, ritual_groesse: 21, tabelle_groesse: 20,
    abschnitt_vor: 240, abschnitt_nach: 60,
    zelle: { oben: 80, unten: 80, links: 120, rechts: 120 },
    rahmen_staerke: 4, rahmen_farbe: "rahmen",
    ritual_vermuten: "Ich vermute zuerst \u2013 dann pr\u00fcfe ich.",
    ritual_punkt: "Auf den Punkt \u2014 ich fasse es in meinen eigenen Worten zusammen.",
  },
  // PH-10.SGE · AB_Widerstand_GR (Layout_wh.js-Kanon, 19./30.08.2026)
  kanon: {
    font: "Calibri", groesse: 20, farbe_text: "text",
    rand: { oben: 500, unten: 500, links: 900, rechts: 900 },
    kaesten: "rahmen", kopfzeile_variante: "tabelle",
    kopfzeile_groesse: 17, titel_groesse: 30, untertitel_groesse: 17,
    abschnitt_groesse: 21, aufgabe_groesse: 23, aufgabe_text_groesse: 21,
    anweisung_groesse: 20, ritual_groesse: 21, tabelle_groesse: 20,
    abschnitt_vor: 90, abschnitt_nach: 30, tabellenabstand: 60,
    kasten_zelle: { oben: 60, unten: 60, links: 160, rechts: 160 },
    zelle: { oben: 70, unten: 70, links: 110, rechts: 110 },
    rahmen_staerke: 4, rahmen_farbe: "hellgrau",
    ritual_vermuten: "Ich vermute zuerst \u2013 dann pr\u00fcfe ich.",
    ritual_punkt: "Ich fasse es in meinen eigenen Worten zusammen.",
    ritual_label_vermuten: "Vermuten\u2013Pr\u00fcfen",
    ritual_label_punkt: "Auf den Punkt",
  },
  // CH-09.WAS · Loesung_Wasserbestandteile (build_loesung.js)
  "loesung-kompakt": {
    font: "Calibri", groesse: 21, farbe_text: "text",
    rand: { oben: 850, unten: 850, links: 850, rechts: 850 },
    kaesten: "schlicht", kopfzeile_variante: "zeile",
    kopfzeile_groesse: 18, titel_groesse: 32, untertitel_groesse: 19,
    abschnitt_groesse: 23, aufgabe_groesse: 23, aufgabe_text_groesse: 23,
    anweisung_groesse: 21, ritual_groesse: 21, tabelle_groesse: 20,
    abschnitt_vor: 220, abschnitt_nach: 60, absatz_nach: 90,
    ueberschrift1_groesse: 26, ueberschrift2_groesse: 23,
    zelle: { oben: 70, unten: 70, links: 110, rechts: 110 },
    rahmen_staerke: 4, rahmen_farbe: "rahmen", marker: "\u25b6",
  },
  // PH-10.SGE · Loesung_Widerstand (build_loesung_widerstand.js)
  "loesung-kanon": {
    font: "Arial", groesse: 21, farbe_text: "dunkel",
    rand: { oben: 900, unten: 700, links: 1000, rechts: 1000 },
    kaesten: "rahmen", kopfzeile_variante: "tabelle",
    kopfzeile_groesse: 20, titel_groesse: 32, untertitel_groesse: 19,
    abschnitt_groesse: 21, aufgabe_groesse: 24, aufgabe_text_groesse: 20,
    anweisung_groesse: 21, ritual_groesse: 21, tabelle_groesse: 21,
    abschnitt_vor: 260, abschnitt_nach: 60, absatz_nach: 100,
    ueberschrift1_groesse: 26, ueberschrift2_groesse: 23,
    zelle: { oben: 70, unten: 70, links: 110, rechts: 110 },
    rahmen_staerke: 4, rahmen_farbe: "hellgrau", marker: "\u25b8",
    zellen_ausrichtung: "mitte",
  },
};

function stilAufloesen(spec) {
  const profilName = (spec.stil && spec.stil.profil)
    || (spec.dokumenttyp === "loesung" ? "loesung-kompakt" : "kompakt");
  const profil = PROFILE[profilName];
  if (!profil) fehler(`Unbekanntes Profil '${profilName}'. Bekannt: ${Object.keys(PROFILE).join(", ")}`);
  const st = { ...profil, ...(spec.stil || {}) };
  st.profil = profilName;
  st.rand = { ...profil.rand, ...((spec.stil && spec.stil.rand) || {}) };
  st.zelle = { ...profil.zelle, ...((spec.stil && spec.stil.zelle) || {}) };
  st.farben = { ...FARBEN_BASIS, ...((spec.stil && spec.stil.farben) || {}) };
  st.satzbreite = st.satzbreite || (A4_BREITE - st.rand.links - st.rand.rechts);
  st.absatz_nach = st.absatz_nach ?? 80;
  return st;
}

/* ============================================================ Hilfen ==== */

function fehler(msg) {
  console.error("ABBRUCH: " + msg);
  process.exit(1);
}
const warnungen = [];
function warnung(msg) { warnungen.push(msg); }
const hinweise = [];                 // Kit 1.8: unterhalb von Warnung
function hinweis(msg) { hinweise.push(msg); }

let ST;                 // aktiver Stil
let CTX;                // { outDir, spec }
let AB_QUELLE = null;   // per ab_spec geladene AB-/Uebungs-Spec (Kit 1.8)

function farbe(v) {
  if (v == null) return undefined;
  return ST.farben[v] || String(v).replace(/^#/, "");
}

function rahmen(staerke, farbName) {
  const r = { style: BorderStyle.SINGLE, size: staerke, color: farbe(farbName) };
  return { top: r, bottom: r, left: r, right: r };
}
const KEIN_RAHMEN = (() => {
  const n = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  return { top: n, bottom: n, left: n, right: n };
})();
function zellRahmen() { return rahmen(ST.rahmen_staerke, ST.rahmen_farbe); }

/** Inline-Markup: **fett**, *kursiv*. Oder Runs als Array [[text, {opt}], ...]. */
function runs(text, basis = {}) {
  if (Array.isArray(text)) {
    return text.map(([t, o = {}]) => run(t, { ...basis, ...o }));
  }
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0, m;
  const s = String(text ?? "");
  while ((m = re.exec(s)) !== null) {
    if (m.index > last) out.push(run(s.slice(last, m.index), basis));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(run(tok.slice(2, -2), { ...basis, fett: true }));
    else out.push(run(tok.slice(1, -1), { ...basis, kursiv: true }));
    last = m.index + tok.length;
  }
  if (last < s.length) out.push(run(s.slice(last), basis));
  return out;
}

function run(text, o = {}) {
  return new TextRun({
    text,
    bold: o.fett, italics: o.kursiv,
    size: o.groesse ?? ST.groesse,
    color: farbe(o.farbe ?? ST.farbe_text),
    font: o.font ?? ST.font,
    characterSpacing: o.sperrung,
    break: o.umbruch,
  });
}

const AUSRICHTUNG = {
  links: AlignmentType.LEFT, mitte: AlignmentType.CENTER,
  rechts: AlignmentType.RIGHT, block: AlignmentType.JUSTIFIED,
};

/** Absatz mit Markup-Text. */
function absatz(text, o = {}) {
  return new Paragraph({
    alignment: o.ausrichtung ? AUSRICHTUNG[o.ausrichtung] : undefined,
    spacing: { before: o.vor ?? 0, after: o.nach ?? ST.absatz_nach },
    indent: o.einzug ? { left: o.einzug } : undefined,
    pageBreakBefore: o.umbruch || undefined,
    keepNext: o.zusammen || undefined,
    border: o.linie_unten
      ? { bottom: { style: BorderStyle.SINGLE, size: o.linie_unten, color: farbe(o.linie_farbe ?? "dunkel") } }
      : undefined,
    tabStops: o.tabStops,
    children: runs(text, o),
  });
}

function leer(nach = 0) {
  return new Paragraph({ spacing: { before: 0, after: nach }, children: [] });
}

/**
 * Tabelle + Pflicht-Leerabsatz danach (LibreOffice-Verschmelzungsfalle).
 * stil.tabellenabstand (twips) macht den Leerabsatz exakt so hoch; ohne
 * Angabe hat er die natuerliche Zeilenhoehe (Vorlage CH-09.WAS).
 */
function tabelleMitSpacer(t) {
  if (ST.tabellenabstand == null) return [t, leer(0)];
  return [t, new Paragraph({
    spacing: { before: 0, after: 0, line: ST.tabellenabstand, lineRule: LineRuleType.EXACT },
    children: [run("", { groesse: 2 })],
  })];
}

/** Zellenraender: deutsche (oben/unten/links/rechts) oder docx-Schluessel. */
function rand4(z) {
  return {
    top: z.top ?? z.oben ?? 0, bottom: z.bottom ?? z.unten ?? 0,
    left: z.left ?? z.links ?? 0, right: z.right ?? z.rechts ?? 0,
  };
}

function zelle(children, breite, o = {}) {
  return new TableCell({
    width: { size: breite, type: WidthType.DXA },
    borders: o.rahmen ?? zellRahmen(),
    shading: o.fuellung ? { fill: farbe(o.fuellung) } : undefined,
    verticalAlign: o.valign ?? VerticalAlign.TOP,
    margins: rand4(o.zelle ?? ST.zelle),
    columnSpan: o.span,
    children,
  });
}

/** Ein-Zellen-Kasten ueber volle Breite. */
function kasten(children, o = {}) {
  const b = o.breite ?? ST.satzbreite;
  const rand = o.rahmen === "keine" ? KEIN_RAHMEN
    : rahmen(o.staerke ?? ST.rahmen_staerke, o.rahmen ?? ST.rahmen_farbe);
  return new Table({
    width: { size: b, type: WidthType.DXA },
    columnWidths: [b],
    borders: rand,
    rows: [new TableRow({
      height: o.hoehe ? { value: o.hoehe, rule: HeightRule.ATLEAST } : undefined,
      children: [zelle(children, b, {
        rahmen: rand, fuellung: o.fuellung,
        zelle: o.zelle ?? ST.kasten_zelle ?? { top: 85, bottom: 85, left: 160, right: 160 },
      })],
    })],
  });
}

/* ----------------------------------------------------------- Bilder --- */

function pngGroesse(buf) {
  return { breite: buf.readUInt32BE(16), hoehe: buf.readUInt32BE(20) };
}

/** Asset laden: PNG + Sidecar-JSON (Anzeigegroesse). Rueckgabe {data, w, h}. */
function asset(name, breiteSoll) {
  const png = path.join(CTX.outDir, `${name}.png`);
  if (!fs.existsSync(png)) fehler(`Asset '${name}' fehlt: ${png} — vorher python ab_assets.py ausfuehren.`);
  const data = fs.readFileSync(png);
  const g = pngGroesse(data);
  let w, h;
  const side = path.join(CTX.outDir, `${name}.json`);
  if (fs.existsSync(side)) {
    const d = JSON.parse(fs.readFileSync(side, "utf8"));
    w = d.breite_px; h = d.hoehe_px;
  } else { w = g.breite; h = g.hoehe; }
  if (breiteSoll) { h = Math.round(breiteSoll * h / w); w = breiteSoll; }
  return { data, w, h };
}

function bildAbsatz(a, o = {}) {
  return new Paragraph({
    alignment: AUSRICHTUNG[o.ausrichtung ?? "mitte"],
    spacing: { before: o.vor ?? 0, after: o.nach ?? 120 },
    children: [new ImageRun({
      type: "png", data: a.data, transformation: { width: a.w, height: a.h },
    })],
  });
}

/* ======================================================== Elemente ====== */
/* Jede Funktion: (e, seite) -> Array von Paragraph|Table                    */

const ELEMENTE = {};

// --- Kopf & Titel ----------------------------------------------------------

ELEMENTE.kopfzeile = (e) => {
  const variante = e.variante ?? ST.kopfzeile_variante;
  const rechts = e.rechts ?? "Name:                                   Datum:";
  if (variante === "zeile") {
    return [new Paragraph({
      tabStops: [{ type: TabStopType.RIGHT, position: ST.satzbreite }],
      border: { bottom: { style: BorderStyle.SINGLE, size: ST.rahmen_staerke, color: farbe(ST.rahmen_farbe) } },
      spacing: { after: e.nach ?? 160 },
      children: [
        run(e.links ?? "", { groesse: ST.kopfzeile_groesse, farbe: "grau" }),
        run("\t" + rechts, { groesse: ST.kopfzeile_groesse, farbe: "grau" }),
      ],
    })];
  }
  // tabelle: links Titel + Unterzeile, rechts Zweigmarke / Namensfeld
  const bRechts = e.breite_rechts ?? 2600;
  const bLinks = ST.satzbreite - bRechts;
  const linksKinder = [];
  const zeile = e.links ? absatz(e.links, { groesse: ST.kopfzeile_groesse, farbe: "grau", nach: 40, sperrung: e.sperrung }) : null;
  if (zeile && e.zeile_oben) linksKinder.push(zeile);          // Layout_wh: Kleinzeile ueber dem Titel
  if (e.titel) linksKinder.push(absatz(e.titel, { fett: true, groesse: ST.titel_groesse, nach: 20 }));
  if (zeile && !e.zeile_oben) linksKinder.push(zeile);
  if (!linksKinder.length) linksKinder.push(leer());
  const unten = { style: BorderStyle.SINGLE, size: e.linie ?? 10, color: farbe(e.linie_farbe ?? "dunkel") };
  return tabelleMitSpacer(new Table({
    width: { size: ST.satzbreite, type: WidthType.DXA },
    columnWidths: [bLinks, bRechts],
    borders: { ...KEIN_RAHMEN, bottom: unten },
    rows: [new TableRow({ children: [
      zelle(linksKinder, bLinks, { rahmen: KEIN_RAHMEN, zelle: { top: 40, bottom: 60, left: 0, right: 0 }, valign: VerticalAlign.BOTTOM }),
      zelle([absatz(rechts, {
        groesse: e.groesse_rechts ?? 19, farbe: e.farbe_rechts ?? "grau",
        fett: e.fett_rechts ?? true, ausrichtung: "rechts", nach: 0,
      })], bRechts, { rahmen: KEIN_RAHMEN, zelle: { top: 40, bottom: 60, left: 0, right: 0 }, valign: VerticalAlign.TOP }),
    ]})],
  }));
};

/** Name-/Datum-Zeile mit Unterstrich-Leadern (Layout_wh.namenszeile). */
ELEMENTE.namenszeile = (e) => [new Paragraph({
  tabStops: [
    { type: TabStopType.LEFT, position: e.name_bis ?? 3100, leader: LeaderType.UNDERSCORE },
    { type: TabStopType.LEFT, position: e.datum_ab ?? 5400 },
    { type: TabStopType.LEFT, position: ST.satzbreite - 260, leader: LeaderType.UNDERSCORE },
  ],
  spacing: { before: e.vor ?? 70, after: e.nach ?? 120 },
  children: [run("Name:\t\tDatum:\t ", { groesse: 19, farbe: "grau" })],
})];

ELEMENTE.titel = (e) => {
  const out = [absatz(e.text, {
    fett: true, groesse: ST.titel_groesse, nach: e.untertitel ? 0 : (e.nach ?? 160),
    linie_unten: e.linie ? 8 : undefined, vor: e.vor ?? 0,
  })];
  if (e.untertitel) out.push(absatz(e.untertitel, { groesse: ST.untertitel_groesse, farbe: "grau", nach: e.nach ?? 160 }));
  return out;
};

ELEMENTE.abschnitt = (e) => [absatz(e.text, {
  fett: true, groesse: e.groesse ?? ST.abschnitt_groesse,
  vor: e.vor ?? ST.abschnitt_vor, nach: e.nach ?? ST.abschnitt_nach, umbruch: e.umbruch,
})];

ELEMENTE.ueberschrift = (e) => {
  const ebene = e.ebene ?? 1;
  if (ebene === 1) return [absatz(e.text, {
    fett: true, groesse: ST.ueberschrift1_groesse ?? 26, vor: e.vor ?? 280, nach: e.nach ?? 100,
    linie_unten: ST.rahmen_staerke, linie_farbe: ST.rahmen_farbe, umbruch: e.umbruch,
  })];
  return [absatz(e.text, {
    fett: true, groesse: ST.ueberschrift2_groesse ?? 23, vor: e.vor ?? 220, nach: e.nach ?? 60, umbruch: e.umbruch,
  })];
};

// Punkte (Kit 1.8): gueltig = Zahl > 0. Eine aufgabe mit teilaufgaben rendert
// die Summe der Teilpunkte (aufgabenBilanz setzt _punkte_gesamt), sonst ihre
// eigenen. Rechtsbuendig ueber einen Tabstop am Satzende: "(4 P)".
function punkteGueltig(v) {
  if (v == null || v === "") return false;
  const n = Number(v);
  return Number.isFinite(n) && n > 0;
}
function punkteText(p) {
  const n = Number(p);
  return `(${Number.isInteger(n) ? n : String(n).replace(".", ",")} P)`;
}
function punkteAnzeige(e) {
  if (punkteGueltig(e.punkte)) return Number(e.punkte);
  return e._punkte_gesamt > 0 ? e._punkte_gesamt : null;
}
const punkteRun = (p, groesse) => (p == null ? [] : [run(`\t${punkteText(p)}`, { groesse })]);
const punkteTab = (p) => (p == null ? undefined : [{ type: TabStopType.RIGHT, position: ST.satzbreite }]);

ELEMENTE.aufgabe = (e) => {
  const p = punkteAnzeige(e);
  const kinder = [new Paragraph({
    pageBreakBefore: e.umbruch || undefined,
    spacing: { before: e.vor ?? (e.umbruch ? 0 : ST.abschnitt_vor), after: e.nach ?? (e.unterzeile ? 20 : ST.abschnitt_nach) },
    tabStops: punkteTab(p),
    children: [
      run(`${e.nr}${ST.aufgabe_trenner ?? "  "}`, { fett: true, groesse: ST.aufgabe_groesse }),
      ...runs(e.text, e.zitat
        ? { kursiv: true, farbe: "grau", groesse: ST.aufgabe_text_groesse }
        : { fett: true, groesse: ST.aufgabe_text_groesse }),
      ...punkteRun(p, ST.aufgabe_text_groesse),
    ],
  })];
  if (e.unterzeile) kinder.push(absatz(e.unterzeile, { groesse: 18, farbe: "grau", nach: 60 }));
  return kinder;
};

// --- Text -------------------------------------------------------------------

ELEMENTE.anweisung = (e) => [absatz(e.text, {
  groesse: e.groesse ?? ST.anweisung_groesse, kursiv: e.kursiv, fett: e.fett,
  farbe: e.farbe, vor: e.vor, nach: e.nach, ausrichtung: e.ausrichtung,
  einzug: e.einzug, umbruch: e.umbruch,
})];
ELEMENTE.text = (e) => ELEMENTE.anweisung({ groesse: ST.groesse, ...e });

ELEMENTE.stichpunkte = (e) => (e.punkte || []).map((t) => new Paragraph({
  bullet: { level: 0 },
  spacing: { after: e.nach ?? 60 },
  children: runs(t, { groesse: e.groesse ?? ST.groesse }),
}));

ELEMENTE.loesung = (e) => [new Paragraph({
  spacing: { before: e.vor ?? 60, after: e.nach ?? ST.absatz_nach },
  indent: (e.einzug ?? ST.loesung_einzug) ? { left: e.einzug ?? ST.loesung_einzug } : undefined,
  children: [
    run(`${ST.marker ?? "\u25b8"}  `, { fett: true, farbe: "akzent", groesse: e.groesse ?? ST.groesse }),
    ...runs(e.text, { groesse: e.groesse ?? ST.groesse, kursiv: e.kursiv }),
  ],
})];

// Bewertungsraster einer Loesung zu einem Uebungsblatt (Kit 1.8). Datenquelle
// ist die per ab_spec geladene uebung-Spec; Format wie das Raster im
// lernkontrolle-Skill (Schritt 3): Aufgabentabelle, AFB-Summen, Soll/Ist.
ELEMENTE.punkteraster = (e) => {
  if (!AB_QUELLE || (AB_QUELLE.dokumenttyp ?? "ab") !== "uebung")
    fehler("punkteraster braucht ab_spec auf eine Spec mit dokumenttyp: uebung.");
  const { items } = aufgabenBilanz(AB_QUELLE);
  const bilanz = afbBilanz(items);
  const rw = richtwertFuer(AB_QUELLE);
  const pz = (v) => `${Number.isInteger(v) ? v : v.toFixed(1).replace(".", ",")}`;
  const out = [];
  out.push(...ELEMENTE.abschnitt({ text: e.titel ?? "Bewertungsraster" }));
  out.push(...ELEMENTE.tabelle({
    kopf_fuellung: "EFEFEF", zelle: { top: 40, bottom: 40, left: 90, right: 90 },
    spalten: [{ kopf: "Aufgabe", breite: 1700, ausrichtung: "links" }, { kopf: "AFB", breite: 1200, ausrichtung: "mitte" }, { kopf: "Punkte", breite: 1400, ausrichtung: "mitte" }],
    zeilen: items.map((it) => [`${it.nr}${it.buchstabe ?? ""}`, it.afb ?? "\u2013", punkteGueltig(it.punkte) ? pz(Number(it.punkte)) : "\u2013"]),
  }));
  const anteil = (k) => (bilanz.gesamt > 0 ? `${pz(Math.round(bilanz.anteil[k] * 10) / 10)} %` : "\u2013");
  out.push(...ELEMENTE.tabelle({
    kopf_fuellung: "EFEFEF", zelle: { top: 40, bottom: 40, left: 90, right: 90 },
    spalten: [{ kopf: "AFB", breite: 1700, ausrichtung: "links" }, { kopf: "Punkte", breite: 1200, ausrichtung: "mitte" }, { kopf: "Anteil", breite: 1400, ausrichtung: "mitte" }],
    zeilen: [
      ["AFB I", pz(bilanz.summe.I), anteil("I")],
      ["AFB II", pz(bilanz.summe.II), anteil("II")],
      ["AFB III", pz(bilanz.summe.III), anteil("III")],
      [{ text: "Gesamt", fett: true }, { text: pz(bilanz.gesamt), fett: true }, { text: bilanz.gesamt > 0 ? "100 %" : "\u2013", fett: true }],
    ],
  }));
  const ist = ["I", "II", "III"].map((k) => `AFB ${k} = ${anteil(k)}`).join(" \u00b7 ");
  if (rw.fehler) {
    out.push(absatz(`Soll: kein Richtwert \u2014 ${rw.fehler}`, { groesse: 20, farbe: "grau", nach: 20, zusammen: true }));
    out.push(absatz(`Ist:  ${ist}`, { groesse: 20, farbe: "grau" }));
  } else {
    const soll = ["I", "II", "III"].map((k) => `AFB ${k} = ${rw.werte[k]} %`).join(" \u00b7 ");
    const abw = afbAbweichungen(bilanz, rw.werte, afbToleranz(AB_QUELLE));
    out.push(absatz(`Soll: ${soll}`, { groesse: 20, farbe: "grau", nach: 20, zusammen: true }));
    out.push(absatz(`Ist:  ${ist}`, { groesse: 20, farbe: "grau", nach: 20, zusammen: true }));
    out.push(absatz(abw.length
      ? `\u26a0 Verteilung abweichend (Toleranz \u00b1${afbToleranz(AB_QUELLE)} Pp): ${abw.join(", ")}`
      : `\u2713 Verteilung eingehalten (Toleranz \u00b1${afbToleranz(AB_QUELLE)} Pp)`,
      { groesse: 20, fett: true }));
  }
  return out;
};

ELEMENTE.leer = (e) => [leer(e.hoehe ?? 100)];
ELEMENTE.seitenumbruch = () => [new Paragraph({ children: [new PageBreak()] })];

// --- Stundenfrage & Ritual ------------------------------------------------

ELEMENTE.stundenfrage = (e) => {
  const modus = e.modus ?? "fest";
  if (ST.kaesten === "schlicht") {
    const out = ELEMENTE.abschnitt({ text: e.label ?? "Stundenfrage" });
    if (modus === "platzhalter") {
      out.push(absatz(e.text, { kursiv: true, groesse: ST.anweisung_groesse }));
      out.push(...ELEMENTE.schreibkasten({ hoehe: e.hoehe ?? 700 }));
    } else {
      out.push(absatz(e.text, { fett: true }));
    }
    return out;
  }
  const kinder = [absatz(e.label ?? ST.stundenfrage_label ?? "Stundenfrage", {
    groesse: 16, farbe: "grau", nach: 50, fett: e.fett_label ?? ST.stundenfrage_fett, sperrung: e.sperrung ?? ST.stundenfrage_sperrung,
  })];
  if (modus === "platzhalter") {
    kinder.push(absatz(e.text, { kursiv: true, groesse: ST.anweisung_groesse, nach: 40 }));
    kinder.push(...schreiblinien(e.zeilen ?? 2, { einzug: 0, abstand: 220 }));
  } else {
    kinder.push(absatz(e.text, { fett: true, groesse: e.groesse ?? 23, nach: 0 }));
  }
  return tabelleMitSpacer(kasten(kinder, {
    staerke: e.staerke ?? ST.stundenfrage_staerke ?? 6, rahmen: e.rahmen ?? ST.stundenfrage_rahmen ?? "rahmen",
  }));
};

const RITUAL_EMOJI = { vermuten: "\uD83D\uDD2E", punkt: "\uD83C\uDFAF" };

ELEMENTE.ritual = (e) => {
  const kanon = e.kanon ?? "vermuten";
  if (!RITUAL_EMOJI[kanon]) fehler(`ritual: kanon '${kanon}' unbekannt (vermuten | punkt).`);
  const text = e.text ?? ST[`ritual_${kanon}`];
  if (ST.kaesten === "schlicht") {
    return [new Paragraph({
      spacing: { before: e.vor ?? 0, after: e.nach ?? 60 },
      children: [run(`${RITUAL_EMOJI[kanon]} ${text}`, { kursiv: true, groesse: ST.ritual_groesse })],
    })];
  }
  const label = e.label ?? ST[`ritual_label_${kanon}`] ?? "";
  const inline = e.zusatz && e.zusatz_inline;
  const kinder = [new Paragraph({
    spacing: { after: e.zusatz && !inline ? 40 : 0 },
    children: [
      run(`${RITUAL_EMOJI[kanon]}${ST.ritual_emoji_trenner ?? " "}`, { groesse: 22 }),
      run(label ? `${label}   ` : "", { fett: true, groesse: ST.ritual_groesse }),
      run(label ? `\u201e${text}\u201c` : text, { kursiv: true, fett: !label, groesse: ST.ritual_groesse }),
      ...(inline ? [run(`      ${e.zusatz}`, { groesse: 17, farbe: "grau" })] : []),
    ],
  })];
  if (e.zusatz && !inline) kinder.push(absatz(e.zusatz, { groesse: 18, nach: 0 }));
  return tabelleMitSpacer(kasten(kinder, {
    rahmen: "rahmen", staerke: 4, fuellung: "hell",
    zelle: { top: 60, bottom: 60, left: 160, right: 160 },
  }));
};

// --- Schreibflaechen ----------------------------------------------------------

ELEMENTE.schreibkasten = (e) => tabelleMitSpacer(new Table({
  width: { size: e.breite ?? ST.satzbreite, type: WidthType.DXA },
  columnWidths: [e.breite ?? ST.satzbreite],
  rows: [new TableRow({
    height: { value: e.hoehe ?? 1000, rule: HeightRule.ATLEAST },
    children: [zelle([leer()], e.breite ?? ST.satzbreite)],
  })],
}));

function schreiblinien(anzahl, o = {}) {
  const { einzug = 220, abstand = 180, breite = ST.satzbreite } = o;
  const out = [];
  for (let i = 0; i < anzahl; i++) {
    out.push(new Paragraph({
      indent: { left: einzug },
      spacing: { before: abstand, after: 0 },
      tabStops: [{ type: TabStopType.LEFT, position: breite - 200, leader: LeaderType.UNDERSCORE }],
      children: [run("\t\u00a0", { groesse: 20 })],
    }));
  }
  return out;
}
ELEMENTE.schreiblinien = (e) => schreiblinien(e.anzahl ?? 2, e);

/**
 * lueckenzeile: Text mit \t je Luecke; positionen = twips, Eintrag als Zahl
 * (Unterstrich-Leader) oder {pos, leader: false} (reiner Tabstop).
 * zusatzlinien: weitere leere Schreiblinien darunter (Satzmuster).
 */
ELEMENTE.lueckenzeile = (e) => {
  let text = Array.isArray(e.text) ? e.text : String(e.text ?? "");
  const pos = (e.positionen ?? [ST.satzbreite - 200]).map((p) => (typeof p === "number" ? { pos: p, leader: true } : p));
  const roh = Array.isArray(text) ? text.map(([t]) => t).join("") : text;
  const nTabs = (roh.match(/\t/g) || []).length;
  if (nTabs !== pos.length) warnung(`lueckenzeile: ${nTabs} Tabs im Text, aber ${pos.length} positionen — "${roh.slice(0, 40)}"`);
  if (roh.endsWith("\t")) {                        // Leader-Falle
    if (Array.isArray(text)) text = [...text, [" ", {}]]; else text += " ";
  }
  const out = [absatz(text, {
    groesse: e.groesse ?? ST.groesse, vor: e.vor ?? 60, nach: e.nach ?? 160, einzug: e.einzug,
    tabStops: pos.map((p) => ({ type: TabStopType.LEFT, position: p.pos, leader: p.leader === false ? undefined : LeaderType.UNDERSCORE })),
  })];
  if (e.zusatzlinien) out.push(...schreiblinien(e.zusatzlinien, { einzug: e.einzug ?? 220, abstand: e.abstand ?? 180 }));
  return out;
};

/** teilaufgabe: a) / b) mit Einzug. */
ELEMENTE.teilaufgabe = (e) => [new Paragraph({
  spacing: { before: e.vor ?? 40, after: e.nach ?? 30 },
  indent: { left: e.einzug ?? 220 },
  tabStops: punkteTab(punkteAnzeige(e)),
  children: [
    ...[],
    run(`${e.buchstabe})  `, { fett: true, groesse: e.groesse ?? ST.anweisung_groesse,
      ...(e.zitat ? { farbe: "grau" } : {}) }),
    ...runs(e.text, e.zitat
      ? { kursiv: true, farbe: "grau", groesse: e.groesse ?? ST.anweisung_groesse }
      : { groesse: e.groesse ?? ST.anweisung_groesse, kursiv: e.kursiv }),
    ...punkteRun(punkteAnzeige(e), e.groesse ?? ST.anweisung_groesse),
  ],
})];

/** ankreuzen: Optionen mit Kaestchen. */
ELEMENTE.ankreuzen = (e) => (e.optionen || []).map((o) => new Paragraph({
  spacing: { before: 45, after: 0 },
  indent: { left: e.einzug ?? 220 },
  children: [run("☐   ", { groesse: 22 }), ...runs(o, { groesse: e.groesse ?? ST.anweisung_groesse })],
}));

/** zitat: woertlicher AB-Text in der Loesung, grau-kursiv. */
ELEMENTE.zitat = (e) => [absatz(e.text, {
  groesse: e.groesse ?? 18, kursiv: true, farbe: "grau", vor: e.vor ?? 20, nach: e.nach ?? 60, einzug: e.einzug ?? 220,
})];

// --- Tabellen ------------------------------------------------------------------

function zellText(v, o = {}) {
  if (v == null) return leer();
  const obj = typeof v === "object" && !Array.isArray(v) ? v : { text: v };
  return new Paragraph({
    alignment: AUSRICHTUNG[obj.ausrichtung ?? o.ausrichtung ?? "links"],
    spacing: { after: 0 },
    children: runs(obj.text ?? "", {
      groesse: obj.groesse ?? o.groesse ?? ST.tabelle_groesse,
      fett: obj.fett ?? o.fett, kursiv: obj.kursiv, farbe: obj.farbe ?? o.farbe,
    }),
  });
}

/**
 * tabelle / raster:
 *   spalten: [{kopf, breite, ausrichtung}]  zeilen: [ "Label" | [zellen...] ]
 *   zeilenhoehe (twips, ATLEAST) macht aus der Tabelle ein Schreibraster
 *   gruppen: [{titel, spalten, zeilen}] -> eine Tabelle mit Lueckenspalte
 */
ELEMENTE.tabelle = (e) => {
  const ausr = e.ausrichtung ?? ST.zellen_ausrichtung ?? "links";
  const gruppen = e.gruppen ?? [{ spalten: e.spalten, zeilen: e.zeilen, titel: e.titel }];
  const luecke = e.gruppen ? (e.luecke ?? 600) : 0;
  const breiten = [];
  gruppen.forEach((g, gi) => {
    if (gi > 0) breiten.push(luecke);
    g.spalten.forEach((s) => breiten.push(s.breite));
  });
  const gesamt = breiten.reduce((a, b) => a + b, 0);
  const rows = [];
  const lueckeZelle = () => zelle([leer()], luecke, { rahmen: KEIN_RAHMEN });

  if (gruppen.some((g) => g.titel)) {
    const cells = [];
    gruppen.forEach((g, gi) => {
      if (gi > 0) cells.push(lueckeZelle());
      cells.push(zelle([zellText(g.titel ?? "", { fett: true, ausrichtung: "mitte" })],
        g.spalten.reduce((a, s) => a + s.breite, 0), { fuellung: "hell", span: g.spalten.length }));
    });
    rows.push(new TableRow({ tableHeader: true, children: cells }));
  }
  if (e.kopf !== false) {
    const cells = [];
    gruppen.forEach((g, gi) => {
      if (gi > 0) cells.push(lueckeZelle());
      g.spalten.forEach((s) => cells.push(zelle(
        [zellText(s.kopf ?? "", { fett: true, ausrichtung: s.ausrichtung ?? (e.kopf_ausrichtung ?? ausr) })],
        s.breite, { fuellung: e.kopf_fuellung ?? "hell", zelle: e.zelle })));
    });
    rows.push(new TableRow({ tableHeader: true, children: cells }));
  }
  const nZeilen = Math.max(...gruppen.map((g) => (g.zeilen || []).length));
  for (let r = 0; r < nZeilen; r++) {
    const cells = [];
    gruppen.forEach((g, gi) => {
      if (gi > 0) cells.push(lueckeZelle());
      const z = (g.zeilen || [])[r];
      const werte = Array.isArray(z) ? z : [z];
      g.spalten.forEach((s, ci) => {
        const v = werte[ci];
        cells.push(zelle([zellText(v, { ausrichtung: s.ausrichtung ?? ausr })], s.breite, { zelle: e.zelle }));
      });
    });
    rows.push(new TableRow({
      height: e.zeilenhoehe ? { value: e.zeilenhoehe, rule: HeightRule.ATLEAST } : undefined,
      children: cells,
    }));
  }
  return tabelleMitSpacer(new Table({
    width: { size: gesamt, type: WidthType.DXA },
    columnWidths: breiten,
    rows,
  }));
};
ELEMENTE.raster = ELEMENTE.tabelle;

// --- Kaesten -----------------------------------------------------------------

/** infokasten: titel, absaetze (Markup-Strings oder {text,...}), punkte, fuellung, rahmen */
ELEMENTE.infokasten = (e) => {
  const kinder = [];
  if (e.titel) kinder.push(absatz(e.titel, { fett: true, groesse: e.titel_groesse ?? 21, nach: 60 }));
  (e.absaetze || []).forEach((a, i, arr) => {
    const o = typeof a === "object" && !Array.isArray(a) ? a : { text: a };
    kinder.push(absatz(o.text, {
      groesse: o.groesse ?? e.groesse ?? ST.anweisung_groesse, fett: o.fett, kursiv: o.kursiv,
      farbe: o.farbe, nach: i === arr.length - 1 && !e.punkte ? 0 : (o.nach ?? 40),
    }));
  });
  (e.punkte || []).forEach((t, i, arr) => kinder.push(absatz(`\u2022  ${t}`, {
    groesse: e.groesse ?? ST.anweisung_groesse, nach: i === arr.length - 1 ? 0 : 40,
  })));
  return tabelleMitSpacer(kasten(kinder, {
    fuellung: e.fuellung === "keine" ? undefined : (e.fuellung ?? "hell"),
    rahmen: e.rahmen, staerke: e.staerke,
    zelle: e.zelle ?? { top: 100, bottom: 100, left: 160, right: 160 },
  }));
};
ELEMENTE.befundkasten = (e) => ELEMENTE.infokasten({
  titel: "Befund \u2014 erg\u00e4nzt durch die Lehrkraft", ...e,
});

/** sprinter: text (String|Liste, ohne Buchstaben) oder aufgaben (Liste, a) b) …), hoehe */
ELEMENTE.sprinter = (e) => {
  const label = e.label ?? "Sprinteraufgabe";
  const texte = e.text == null ? [] : (Array.isArray(e.text) ? e.text : [e.text]);
  const aufgaben = e.aufgaben || [];
  const buchstabe = (i) => String.fromCharCode(97 + i);
  if (ST.kaesten === "schlicht") {
    const out = ELEMENTE.abschnitt({ text: label });
    texte.forEach((t) => out.push(absatz(t, { groesse: ST.anweisung_groesse })));
    aufgaben.forEach((t, i) => out.push(absatz(`**${buchstabe(i)})**  ${t}`, { groesse: ST.anweisung_groesse })));
    if (e.hoehe) out.push(...ELEMENTE.schreibkasten({ hoehe: e.hoehe }));
    return out;
  }
  const kinder = [e.sperrung
    ? new Paragraph({ spacing: { after: 60 }, children: [
        ...(e.emoji ? [run(`${e.emoji}  `, { groesse: 20 })] : []),
        run(label, { fett: true, groesse: 16, farbe: "grau", sperrung: e.sperrung }),
      ] })
    : absatz(label, { fett: true, groesse: ST.anweisung_groesse, nach: 40 })];
  texte.forEach((t) => kinder.push(absatz(t, { groesse: ST.anweisung_groesse, nach: 30 })));
  aufgaben.forEach((t, i) => {
    kinder.push(absatz(`**${buchstabe(i)})**  ${t}`, { groesse: ST.anweisung_groesse, nach: 30, einzug: e.einzug }));
    if (e.linien) kinder.push(...schreiblinien(e.linien, { einzug: e.einzug ?? 220, abstand: e.abstand ?? 280, breite: ST.satzbreite - 320 }));
  });
  const out = tabelleMitSpacer(kasten(kinder, { rahmen: "rahmen", staerke: 4, zelle: { top: 70, bottom: 70, left: 160, right: 160 } }));
  if (e.hoehe) out.push(...ELEMENTE.schreibkasten({ hoehe: e.hoehe }));
  return out;
};

// --- Merksatz & Notanker ----------------------------------------------------------

/**
 * merksatz:
 *   variante inline  -> Schreibflaeche links, gedrehter Notanker rechts (scaffold, hoehe)
 *   variante kasten  -> gerahmter Kasten mit Label und Schreiblinien (zeilen, hinweis)
 */
ELEMENTE.merksatz = (e) => {
  const variante = e.variante ?? (ST.kaesten === "schlicht" ? "inline" : "kasten");
  if (variante === "inline") {
    const a = asset(e.scaffold, e.breite);
    const links = e.breite_links ?? Math.round(ST.satzbreite * 0.58);
    const rechts = ST.satzbreite - links;
    return tabelleMitSpacer(new Table({
      width: { size: ST.satzbreite, type: WidthType.DXA },
      columnWidths: [links, rechts],
      rows: [new TableRow({
        height: { value: e.hoehe ?? 2000, rule: HeightRule.ATLEAST },
        children: [
          zelle([leer()], links),
          zelle([bildAbsatz(a, { nach: 0 })], rechts),
        ],
      })],
    }));
  }
  const kinder = [absatz(e.label ?? "MERKSATZ \u2013 deine Antwort auf die Stundenfrage", {
    groesse: 16, fett: true, farbe: "grau", sperrung: 40, nach: 40,
  })];
  if (e.hinweis) kinder.push(absatz(e.hinweis, { groesse: 17, farbe: "grau", nach: 20 }));
  if (e.hoehe) {
    return tabelleMitSpacer(kasten(kinder, { staerke: e.staerke ?? 8, rahmen: "dunkel", hoehe: e.hoehe }));
  }
  kinder.push(...schreiblinien(e.zeilen ?? 3, { einzug: 0, abstand: 250, breite: ST.satzbreite - 320 }));
  return tabelleMitSpacer(kasten(kinder, { staerke: e.staerke ?? 8, rahmen: "dunkel" }));
};

/**
 * notanker: gedrehter Scaffold.
 *   position hier  -> an dieser Stelle im Fluss
 *   position fuss  -> im Section-Footer (Default; wird in seiteBauen() abgefangen),
 *                     ab_seite: 1 = jede Seite der Section, 2 = ab der zweiten
 *   hinweis: Text unter dem Bild (Default "Du kommst nicht weiter? Drehe das Blatt um 180°.")
 */
function notankerKinder(e) {
  const a = asset(e.scaffold, e.breite);
  const out = [bildAbsatz(a, { vor: e.vor ?? 60, nach: 30 })];
  const hinweis = e.hinweis === false ? null
    : (e.hinweis ?? "Du kommst nicht weiter? Drehe das Blatt um 180\u00b0.");
  if (hinweis) out.push(absatz(hinweis, { groesse: 16, farbe: "grau", kursiv: true, ausrichtung: "mitte", nach: 0 }));
  return { kinder: out, hoehePx: a.h + (hinweis ? 14 : 0) + 6 };
}
ELEMENTE.notanker = (e) => notankerKinder(e).kinder;

// --- Bilder --------------------------------------------------------------------

ELEMENTE.bild = (e) => {
  if (!e.asset) fehler("bild: Feld 'asset' fehlt.");
  return [bildAbsatz(asset(e.asset, e.breite), e)];
};
ELEMENTE.balkenraster = ELEMENTE.bild;

/**
 * nebeneinander: zwei Spalten in einer randlosen Tabelle (nie zwei Tabellen).
 *   links / rechts: Liste von Elementen  ODER  links_bild / rechts_bild: Asset-Name
 *   breite_rechts (twips), breite_bild (px), valign: oben | mitte
 */
ELEMENTE.nebeneinander = (e) => {
  const luecke = e.luecke ?? 0;                       // Lueckenspalte (twips), z. B. Planpaar
  const bRechts = e.breite_rechts ?? Math.round((ST.satzbreite - luecke) / 2);
  const bLinks = e.breite_links ?? (ST.satzbreite - bRechts - luecke);
  const seite = (elemente, bildName, breiteBild) => {
    if (bildName) return [bildAbsatz(asset(bildName, breiteBild), { nach: 0, vor: 0, ausrichtung: e.ausrichtung_bild ?? "mitte" })];
    const k = (elemente || []).flatMap((el) => rendern(el));
    return k.length ? k : [leer()];
  };
  const valign = e.valign === "mitte" ? VerticalAlign.CENTER : VerticalAlign.TOP;
  const rahmenZelle = e.rahmen ? rahmen(e.staerke ?? 4, e.rahmen === true ? "grau" : e.rahmen) : KEIN_RAHMEN;
  const innen = e.rahmen ? (e.zelle ?? { top: 60, bottom: 60, left: 80, right: 80 }) : null;
  const cells = [
    zelle(seite(e.links, e.links_bild, e.breite_bild_links ?? e.breite_bild), bLinks,
      { rahmen: rahmenZelle, zelle: innen ?? { top: 0, bottom: 0, left: 0, right: luecke ? 0 : 160 }, valign }),
  ];
  if (luecke) cells.push(zelle([leer()], luecke, { rahmen: KEIN_RAHMEN, zelle: { top: 0, bottom: 0, left: 0, right: 0 } }));
  cells.push(zelle(seite(e.rechts, e.rechts_bild, e.breite_bild), bRechts,
    { rahmen: rahmenZelle, zelle: innen ?? { top: 0, bottom: 0, left: 0, right: 0 }, valign }));
  return tabelleMitSpacer(new Table({
    width: { size: bLinks + luecke + bRechts, type: WidthType.DXA },
    columnWidths: luecke ? [bLinks, luecke, bRechts] : [bLinks, bRechts],
    borders: KEIN_RAHMEN,
    rows: [new TableRow({ children: cells })],
  }));
};

/* ===================================================== Seiten / Dokument == */

const BEKANNTE_FELDER = new Set(["typ"]);

function rendern(e) {
  if (typeof e !== "object" || e == null) fehler(`Element ist kein Objekt: ${JSON.stringify(e)}`);
  const fn = ELEMENTE[e.typ];
  if (!fn) fehler(`Unbekannter Elementtyp '${e.typ}'. Bekannt: ${Object.keys(ELEMENTE).sort().join(", ")}`);
  return fn(e);
}

function seiteBauen(seite, spec) {
  const elemente = [...(seite.elemente || [])];
  const istUebung = (spec.dokumenttyp ?? "ab") === "uebung";
  // Uebungsblatt (Kit 1.8): Untertitel-Default, wenn die Seite keinen setzt.
  const untertitel = seite.untertitel ?? (istUebung ? "\u00dcbungsblatt" : undefined);
  // Kopfzeile / Titel aus Seiten- oder Spec-Ebene voranstellen
  const kopf = seite.kopfzeile === false ? null : { ...(spec.kopf || {}), ...(seite.kopfzeile || {}) };
  const vorne = [];
  if (kopf && Object.keys(kopf).length) {
    const variante = kopf.variante ?? ST.kopfzeile_variante;
    if (variante === "tabelle") vorne.push({ typ: "kopfzeile", titel: seite.titel, links: untertitel ?? kopf.links, ...kopf, ...(seite.titel ? { titel: seite.titel } : {}) });
    else {
      vorne.push({ typ: "kopfzeile", ...kopf });
      if (seite.titel) vorne.push({ typ: "titel", text: seite.titel, untertitel });
    }
  } else if (seite.titel) {
    vorne.push({ typ: "titel", text: seite.titel, untertitel, linie: seite.titel_linie });
  }
  // Notanker im Fuss abfangen
  const fussAnker = elemente.filter((e) => e.typ === "notanker" && (e.position ?? "fuss") === "fuss");
  let fluss = elemente.filter((e) => !(e.typ === "notanker" && (e.position ?? "fuss") === "fuss"));
  // Uebungsblatt: Kasten afb3_hinweis vor der ERSTEN AFB-III-Aufgabe des
  // Blattes (einmal je Spec, Stil infokasten, nicht der Ritual-Kasten).
  if (istUebung && !CTX.afb3Gesetzt) {
    const idx = fluss.findIndex((e) => e.typ === "aufgabe" && afbNorm(e.afb) === "III");
    if (idx >= 0) {
      CTX.afb3Gesetzt = true;
      fluss = [...fluss.slice(0, idx),
        { typ: "infokasten", absaetze: [{ text: spec.afb3_hinweis ?? AFB3_HINWEIS_DEFAULT, kursiv: true }] },
        ...fluss.slice(idx)];
    }
  }
  // Loesung zu einem Uebungsblatt: Bewertungsraster am Ende der letzten Seite,
  // sofern die Spec es nicht selbst als Element `punkteraster` platziert.
  if ((spec.dokumenttyp ?? "ab") === "loesung" && AB_QUELLE && (AB_QUELLE.dokumenttyp ?? "ab") === "uebung"
      && seite === spec.seiten[spec.seiten.length - 1]
      && !spec.seiten.some((sx) => elementeFlach(sx.elemente).some((e) => e.typ === "punkteraster"))) {
    fluss = [...fluss, { typ: "punkteraster" }];
  }

  const children = [...vorne, ...fluss].flatMap((e) => rendern(e));
  const rand = { ...ST.rand, ...(seite.rand || {}) };
  const props = { page: { margin: { top: rand.oben, bottom: rand.unten, left: rand.links, right: rand.rechts } } };
  const footers = {};
  if (fussAnker.length) {
    if (fussAnker.length > 1) fehler("Mehr als ein notanker mit position fuss auf einer Seite.");
    const na = notankerKinder(fussAnker[0]);
    const fussHoehe = Math.round(na.hoehePx * 15) + 200;          // px -> twips
    props.page.margin.footer = 280;
    props.page.margin.bottom = Math.max(rand.unten, 280 + fussHoehe);
    footers.default = new Footer({ children: na.kinder });
    if ((fussAnker[0].ab_seite ?? 1) === 2) {
      props.titlePage = true;
      footers.first = new Footer({ children: [leer()] });
    }
  }
  return { properties: props, children, footers: Object.keys(footers).length ? footers : undefined };
}

function specPruefen(spec) {
  const pflicht = ["kit_version", "block", "titel", "zweig", "ausgabe", "stand", "seiten"];
  const fehlt = pflicht.filter((k) => spec[k] == null);
  if (fehlt.length) fehler(`Pflichtfelder fehlen: ${fehlt.join(", ")}`);
  const sv = String(spec.kit_version);
  if (sv.split(".")[0] !== KIT_VERSION.split(".")[0]) {
    if (!process.argv.includes("--force"))
      fehler(`Spec kit_version ${sv} passt nicht zu KIT_VERSION ${KIT_VERSION} (Major). --force erzwingt.`);
    warnung(`kit_version ${sv} vs. Kit ${KIT_VERSION} — mit --force gebaut.`);
  } else if (sv !== KIT_VERSION) {
    warnung(`Spec kit_version ${sv}, Kit ist ${KIT_VERSION}. Neubau kann sich vom Original unterscheiden.`);
  }
  if (!Array.isArray(spec.seiten) || !spec.seiten.length) fehler("seiten: muss eine nicht-leere Liste sein.");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(spec.stand))) warnung(`stand '${spec.stand}' ist nicht ISO (JJJJ-MM-TT).`);
  const dt = spec.dokumenttyp ?? "ab";
  if (!["ab", "loesung", "uebung"].includes(dt)) warnung(`dokumenttyp '${dt}' unbekannt (ab | loesung | uebung) — wird wie ab behandelt.`);
}

/* ====================================== Uebungsblatt-Check (Kit 1.8) ===== */
// Gilt nur fuer dokumenttyp: uebung. A-1..A-5 entfallen dort vollstaendig
// (AB_Qualitaet.md: Uebungs- und reine Plenumsbloecke fallen nicht unter den
// Bauplan). Nur Warnungen bzw. Hinweise, nie Abbruch.
//   Ue-1 AFB-Anteile: Punktsumme je AFB gegen Richtwert (zweig oder
//        afb_richtwert), Toleranz afb_toleranz (Default 5 Prozentpunkte)
//   Ue-2 AFB III freiwillig: keine AFB-III-Aufgabe = Hinweis, keine Warnung
//   Ue-3 Reihenfolge I -> II -> III auf Aufgabenebene
//   Ue-4 Punkte: jede aufgabe ohne Teilaufgaben und jede teilaufgabe > 0;
//        eigene Punkte einer aufgabe mit Teilaufgaben muessen deren Summe sein
//   Ue-5 Fremdelemente: stundenfrage, notanker, sprinter, ritual

function afbNorm(v) { return v == null ? null : String(v).trim().toUpperCase(); }

// Ordnet Teilaufgaben ihrer aufgabe zu, prueft Punkte und setzt
// e._punkte_gesamt fuer das Rendering. Laeuft fuer jeden Dokumenttyp; ohne
// punkte-Angaben bleibt alles unberuehrt.
function aufgabenBilanz(spec) {
  const items = [];
  const probleme = [];
  (spec.seiten || []).forEach((seite) => {
    let akt = null;
    let teile = [];
    const abschluss = () => {
      if (!akt) return;
      if (teile.length) {
        const summe = teile.reduce((a, t) => a + (punkteGueltig(t.punkte) ? Number(t.punkte) : 0), 0);
        if (punkteGueltig(akt.punkte) && Number(akt.punkte) !== summe)
          probleme.push(`Aufgabe ${akt.nr} tr\u00e4gt punkte ${akt.punkte}, die Teilaufgaben summieren ${summe}.`);
        akt._punkte_gesamt = summe > 0 ? summe : null;
        teile.forEach((t) => items.push({ art: "teil", nr: akt.nr, buchstabe: t.buchstabe, afb: afbNorm(t.afb ?? akt.afb), punkte: t.punkte, e: t }));
      } else {
        if (!punkteGueltig(akt.punkte)) probleme.push(`Aufgabe ${akt.nr} ohne punkte (> 0).`);
        akt._punkte_gesamt = null;
        items.push({ art: "aufgabe", nr: akt.nr, buchstabe: null, afb: afbNorm(akt.afb), punkte: akt.punkte, e: akt });
      }
    };
    elementeFlach(seite.elemente).forEach((e) => {
      if (e.typ === "aufgabe") { abschluss(); akt = e; teile = []; }
      else if (e.typ === "teilaufgabe" && akt) {
        if (!punkteGueltig(e.punkte)) probleme.push(`Teilaufgabe ${akt.nr}${e.buchstabe ?? "?"} ohne punkte (> 0).`);
        teile.push(e);
      }
    });
    abschluss();
  });
  return { items, probleme };
}

function afbBilanz(items) {
  const summe = { I: 0, II: 0, III: 0 };
  items.forEach((it) => { if (punkteGueltig(it.punkte) && summe[it.afb] != null) summe[it.afb] += Number(it.punkte); });
  const gesamt = summe.I + summe.II + summe.III;
  const anteil = { I: 0, II: 0, III: 0 };
  if (gesamt > 0) ["I", "II", "III"].forEach((k) => { anteil[k] = (100 * summe[k]) / gesamt; });
  return { summe, gesamt, anteil };
}

function afbToleranz(spec) {
  const t = Number(spec.afb_toleranz);
  return Number.isFinite(t) && t >= 0 ? t : AFB_TOLERANZ_DEFAULT;
}

// { werte: {I,II,III}, quelle } oder { fehler }
function richtwertFuer(spec) {
  if (spec.afb_richtwert != null) {
    const r = spec.afb_richtwert;
    const w = { I: Number(r.I), II: Number(r.II), III: Number(r.III) };
    if (![w.I, w.II, w.III].every(Number.isFinite))
      return { fehler: "afb_richtwert braucht I, II und III als Zahlen." };
    if (Math.abs(w.I + w.II + w.III - 100) > 0.01)
      return { fehler: `afb_richtwert summiert auf ${w.I + w.II + w.III} statt 100.` };
    return { werte: w, quelle: "afb_richtwert" };
  }
  const z = String(spec.zweig ?? "").trim();
  if (AFB_RICHTWERT[z]) return { werte: AFB_RICHTWERT[z], quelle: `zweig ${z}` };
  return { fehler: `\u00dcbungsblatt braucht Einzelzweig oder afb_richtwert (zweig: ${z || "fehlt"}).` };
}

function afbAbweichungen(bilanz, werte, toleranz) {
  const pz = (v) => (Number.isInteger(v) ? String(v) : v.toFixed(1).replace(".", ","));
  return ["I", "II", "III"]
    .filter((k) => Math.abs(bilanz.anteil[k] - werte[k]) > toleranz + 1e-9)
    .map((k) => `AFB ${k} ${pz(Math.round(bilanz.anteil[k] * 10) / 10)} % statt ${werte[k]} %`);
}

function uebungPruefen(spec) {
  const befunde = [];
  const m = (regel, text) => befunde.push(`\u00dcbung ${regel}: ${text}`);
  const alle = (spec.seiten || []).flatMap((sx) => elementeFlach(sx.elemente));

  // ---- Ue-5 Fremdelemente
  ["stundenfrage", "notanker", "sprinter", "ritual"].forEach((t) => {
    const n = alle.filter((e) => e.typ === t).length;
    if (n) m("\u00dc-5", `${n} Element(e) ${t} \u2014 nicht erlaubt bei uebung.`);
  });

  // ---- Ue-4 Punkte
  const { items, probleme } = aufgabenBilanz(spec);
  probleme.forEach((p) => m("\u00dc-4", p));

  // ---- Ue-3 Reihenfolge (Aufgabenebene)
  const aufgaben = alle.filter((e) => e.typ === "aufgabe");
  let maxRang = 0, maxNr = null;
  aufgaben.forEach((e) => {
    const k = afbNorm(e.afb);
    if (k == null) { m("\u00dc-3", `Aufgabe ${e.nr} ohne afb (I | II | III).`); return; }
    if (!AFB_RANG[k]) { m("\u00dc-3", `Aufgabe ${e.nr}: afb '${e.afb}' unbekannt (I, II, III).`); return; }
    if (AFB_RANG[k] < maxRang)
      m("\u00dc-3", `Aufgabe ${e.nr} (AFB ${k}) nach Aufgabe ${maxNr} (AFB ${Object.keys(AFB_RANG).find((x) => AFB_RANG[x] === maxRang)}) \u2014 Reihenfolge I \u2192 II \u2192 III.`);
    if (AFB_RANG[k] > maxRang) { maxRang = AFB_RANG[k]; maxNr = e.nr; }
  });

  // ---- Ue-2 AFB III freiwillig
  if (!items.some((it) => it.afb === "III"))
    hinweis("\u00dcbung \u00dc-2: keine AFB-III-Aufgabe \u2014 zul\u00e4ssig; \u00dc-1 rechnet mit AFB III = 0 %.");

  // ---- Ue-1 AFB-Anteile
  const bilanz = afbBilanz(items);
  if (bilanz.gesamt <= 0) { m("\u00dc-1", "keine Punkte \u2014 AFB-Anteile nicht pr\u00fcfbar."); return befunde; }
  const rw = richtwertFuer(spec);
  if (rw.fehler) { m("\u00dc-1", `${rw.fehler} Anteilspr\u00fcfung entf\u00e4llt.`); return befunde; }
  const tol = afbToleranz(spec);
  const abw = afbAbweichungen(bilanz, rw.werte, tol);
  if (abw.length) {
    const pz = (v) => (Number.isInteger(v) ? String(v) : v.toFixed(1).replace(".", ","));
    const ist = ["I", "II", "III"].map((k) => pz(Math.round(bilanz.anteil[k] * 10) / 10)).join("/");
    const soll = ["I", "II", "III"].map((k) => rw.werte[k]).join("/");
    m("\u00dc-1", `AFB-Anteile weichen ab (Toleranz \u00b1${tol} Pp, Richtwert ${rw.quelle}): ${abw.join(", ")}. Ist I/II/III = ${ist} %, Soll = ${soll} % bei ${pz(bilanz.gesamt)} P.`);
  }
  return befunde;
}

/* ============================================ Bauplan-Check (Kit 1.2) ===== */
// Prueft ein Arbeitsblatt gegen den Bauplan aus _Grundsaetze\AB_Qualitaet.md
// Teil A. Einheit ist eine Seite der Spec (= eine Stunde). Nur Warnungen, nie
// Abbruch; Loesungen (dokumenttyp: loesung) werden nicht geprueft.
//   A-1 Anknuepfung: erste Aufgabe traegt `bezug:`
//   A-2 Materialbezug: jede AFB-I/II-Aufgabe traegt `bezug:`
//   A-3 AFB-Progression: `afb: I | II | III` je aufgabe, Start mit I,
//       mindestens eine II, kein Rueckfall; III nur als Sprinter
//   A-4 Stundenfrage-Element, Merksatz-Anschluss (ritual kanon: punkt oder
//       merksatz) nach der letzten Aufgabe, verdeckter Scaffold (notanker/
//       merksatz mit scaffold) — Default Pflicht, Opt-out nur ausdruecklich
//       ueber `bauplan: {scaffold: false}` auf Spec-Ebene
//   A-5 genau eine Sprinteraufgabe (sprinter), nach dem Merksatz-Anschluss
//   A-4 (Blatt, Kit 1.7): ueber alle Seiten genau eine stundenfrage,
//       hoechstens ein sprinter und ein ritual kanon: punkt — sonst tragen
//       zwei Bloecke ein Blatt; auf getrennte Specs aufteilen
// Seiten ohne stundenfrage und ohne aufgabe (Fortsetzungs-/Infoseiten) werden
// uebersprungen. Specs ohne afb-Angaben bekommen nur die Strukturpruefung
// (A-4/A-5) und einen Hinweis, dass die AFB-Kette nicht pruefbar ist.

const AFB_RANG = { I: 1, II: 2, III: 3 };

function elementeFlach(liste) {
  const out = [];
  (liste || []).forEach((e) => {
    if (!e || typeof e !== "object") return;
    out.push(e);
    if (e.typ === "nebeneinander") {
      out.push(...elementeFlach(e.links));
      out.push(...elementeFlach(e.rechts));
    }
  });
  return out;
}

/* ======================== Aufgabenzitate aus der AB-Spec (Kit 1.5) ======== */
// Eine Loesungs-Spec kann mit `ab_spec:` auf die Spec des Arbeitsblatts zeigen
// (Pfad relativ zum Ordner der Loesungs-Spec). Ein `aufgabe`-Element mit
// `zitat: true` und ohne `text`, aber mit `nr`, holt seinen Wortlaut dann aus
// der Aufgabe gleicher `nr` des Arbeitsblatts. Aenderungen am AB schlagen so
// beim naechsten Bau in die Loesung durch; Wortlaut-Drift zwischen Blatt und
// Erwartungshorizont ist ausgeschlossen. Ein vorhandener `text` gewinnt -
// Bestandsspecs bleiben unveraendert.
//
// `nr` ist eine Zeichenkette, keine Zahl (AB_Messen_GR fuehrt `nr: "1 + 2"`),
// und wird zeichengenau verglichen. Aufgaben in `nebeneinander` zaehlen mit
// (elementeFlach). Doppelte `nr` im Arbeitsblatt sind ein Abbruch: die erste
// stillschweigend zu nehmen waere genau die Drift, die das Feld verhindert.

// Teilaufgaben (Kit 1.6) haengen an der zuletzt gesehenen aufgabe derselben
// Seite: Schluessel `<nr>|<buchstabe>`. Eine teilaufgabe vor der ersten aufgabe
// einer Seite hat keinen Anker und wird nicht indiziert.
function aufgabenIndex(spec) {
  const index = new Map();
  const teile = new Map();
  const doppelt = new Set();
  (spec.seiten || []).forEach((seite, si) => {
    let nrAktuell = null;
    elementeFlach(seite.elemente).forEach((e) => {
      if (e.typ === "aufgabe" && e.nr != null) {
        const nr = String(e.nr).trim();
        nrAktuell = nr;
        if (index.has(nr)) doppelt.add(`nr "${nr}"`);
        else index.set(nr, { text: e.text, seite: si + 1, e });
      } else if (e.typ === "teilaufgabe" && e.buchstabe != null && nrAktuell != null) {
        const b = String(e.buchstabe).trim();
        const k = `${nrAktuell}|${b}`;
        if (teile.has(k)) doppelt.add(`nr "${nrAktuell}" ${b})`);
        else teile.set(k, { text: e.text, seite: si + 1, e });
      }
    });
  });
  return { index, teile, doppelt };
}

function zitateAufloesen(spec, specPfad) {
  const offen = [];
  (spec.seiten || []).forEach((seite, si) => {
    let nrAktuell = null;
    elementeFlach(seite.elemente).forEach((e) => {
      if (e.typ === "aufgabe" && e.nr != null) nrAktuell = String(e.nr).trim();
      if (e.typ === "aufgabe" && e.zitat && e.text == null) offen.push({ e, seite: si + 1 });
      if (e.typ === "teilaufgabe" && e.zitat && e.text == null)
        offen.push({ e, seite: si + 1, nr: nrAktuell });
    });
  });
  if (!offen.length) return 0;

  const wo = (o) => {
    if (o.e.typ === "teilaufgabe")
      return `Seite ${o.seite}, teilaufgabe ${o.e.buchstabe == null ? "(ohne buchstabe)" : `${String(o.e.buchstabe).trim()})`}`
        + ` unter nr ${o.nr == null ? "(keine aufgabe davor)" : `"${o.nr}"`}`;
    return `Seite ${o.seite}, nr ${o.e.nr == null ? "(fehlt)" : `"${String(o.e.nr).trim()}"`}`;
  };
  const ohneNr = offen.find((o) => o.e.typ === "aufgabe" && o.e.nr == null);
  if (ohneNr)
    fehler(`aufgabe mit zitat: true ohne text braucht nr, um zitiert zu werden (${wo(ohneNr)}).`);
  const teilOhne = offen.find((o) => o.e.typ === "teilaufgabe" && (o.e.buchstabe == null || o.nr == null));
  if (teilOhne)
    fehler(`teilaufgabe mit zitat: true ohne text braucht buchstabe und eine aufgabe mit nr davor (${wo(teilOhne)}).`);
  if (spec.ab_spec == null)
    fehler(`${offen[0].e.typ} mit zitat: true ohne text (${wo(offen[0])}) — dafuer muss die Spec `
      + `ab_spec: <AB-Spec> tragen (Pfad relativ zum Spec-Ordner).`);

  const abPfad = path.resolve(path.dirname(specPfad), String(spec.ab_spec));
  let ab;
  try { ab = YAML.parse(fs.readFileSync(abPfad, "utf8")); }
  catch (err) { fehler(`ab_spec nicht lesbar: ${abPfad} (${err.message})`); }
  if (!ab || !Array.isArray(ab.seiten))
    fehler(`ab_spec ohne seiten-Liste: ${abPfad}`);

  AB_QUELLE = ab;
  // Uebungsblatt als Quelle (Kit 1.8): punkte und afb wandern mit dem Zitat,
  // sofern die Loesung sie nicht selbst setzt.
  const uebernehmen = (ziel, treffer) => {
    ziel.text = treffer.text;
    if ((ab.dokumenttyp ?? "ab") === "uebung" && treffer.e) {
      if (ziel.punkte == null && treffer.e.punkte != null) ziel.punkte = treffer.e.punkte;
      if (ziel.afb == null && treffer.e.afb != null) ziel.afb = treffer.e.afb;
    }
  };
  const { index, teile, doppelt } = aufgabenIndex(ab);
  if (doppelt.size)
    fehler(`ab_spec ${path.basename(abPfad)} fuehrt mehrfach: `
      + `${[...doppelt].join(", ")} — Zitat waere nicht eindeutig.`);
  const vorhanden = () => (index.size
    ? [...index.keys()].map((n) => `"${n}"`).join(", ")
    : "keine");
  const vorhandeneTeile = (nr) => {
    const bs = [...teile.keys()].filter((k) => k.startsWith(`${nr}|`)).map((k) => `${k.split("|")[1]})`);
    return bs.length ? bs.join(", ") : "keine";
  };

  const abName = path.basename(abPfad);
  offen.forEach((o) => {
    if (o.e.typ === "teilaufgabe") {
      const b = String(o.e.buchstabe).trim();
      if (!index.has(o.nr))
        fehler(`ab_spec ${abName} hat keine Aufgabe mit nr "${o.nr}" `
          + `(zitiert in ${wo(o)}). Vorhandene Nummern: ${vorhanden()}.`);
      const treffer = teile.get(`${o.nr}|${b}`);
      if (!treffer)
        fehler(`ab_spec ${abName} hat unter nr "${o.nr}" keine teilaufgabe ${b}) `
          + `(zitiert in ${wo(o)}). Vorhandene Teilaufgaben dort: ${vorhandeneTeile(o.nr)}.`);
      if (treffer.text == null)
        fehler(`ab_spec ${abName}: teilaufgabe ${b}) unter nr "${o.nr}" hat keinen text (zitiert in ${wo(o)}).`);
      uebernehmen(o.e, treffer);
      return;
    }
    const nr = String(o.e.nr).trim();
    const treffer = index.get(nr);
    if (!treffer)
      fehler(`ab_spec ${abName} hat keine Aufgabe mit nr "${nr}" `
        + `(zitiert in ${wo(o)}). Vorhandene Nummern: ${vorhanden()}.`);
    if (treffer.text == null)
      fehler(`ab_spec ${abName}: Aufgabe nr "${nr}" hat keinen text `
        + `(zitiert in ${wo(o)}).`);
    uebernehmen(o.e, treffer);
  });
  return offen.length;
}

function bauplanPruefen(spec) {
  const befunde = [];
  if ((spec.dokumenttyp ?? "ab") !== "ab") return befunde;
  const optOut = !!(spec.bauplan && spec.bauplan.scaffold === false);
  const afbVon = (e) => (e.afb == null ? null : String(e.afb).trim().toUpperCase());
  const istSprinterAfb = (e) => afbVon(e) === "III";

  (spec.seiten || []).forEach((seite, si) => {
    const el = elementeFlach(seite.elemente);
    const aufgaben = el.filter((e) => e.typ === "aufgabe");
    const hatSF = el.some((e) => e.typ === "stundenfrage");
    if (!aufgaben.length && !hatSF) return;
    const wo = `Seite ${si + 1}${seite.titel ? ` „${seite.titel}“` : ""}`;
    const m = (regel, text) => befunde.push(`Bauplan ${regel} · ${wo}: ${text}`);
    const letzterIdx = (pred) => { let k = -1; el.forEach((e, i) => { if (pred(e)) k = i; }); return k; };
    const ersterIdx = (pred) => el.findIndex(pred);

    // ---- A-4: Stundenfrage, Merksatz-Anschluss, Scaffold
    if (!hatSF) m("A-4", "kein Element stundenfrage.");
    const merkIdx = letzterIdx((e) => e.typ === "merksatz" || (e.typ === "ritual" && e.kanon === "punkt"));
    const letzteAufgabeIdx = letzterIdx((e) => e.typ === "aufgabe" && !istSprinterAfb(e));
    if (merkIdx < 0) m("A-4", "kein Merksatz-Anschluss (ritual kanon: punkt oder merksatz) — die letzte AFB-II-Aufgabe beantwortet die Stundenfrage als Merksatz.");
    else if (letzteAufgabeIdx > merkIdx) m("A-4", "Merksatz-Anschluss steht vor der letzten Aufgabe — er gehoert hinter die Aufgabe, die die Stundenfrage beantwortet.");
    const scaffold = el.some((e) => (e.typ === "notanker" || e.typ === "merksatz") && e.scaffold);
    if (!scaffold && !optOut) m("A-4", "kein verdeckter Merksatz-Scaffold (notanker oder merksatz mit scaffold). Default ist Pflicht; Opt-out nur ausdruecklich mit bauplan: {scaffold: false}.");

    // ---- A-5: Sprinteraufgabe
    const sprinter = el.filter((e) => e.typ === "sprinter");
    const sprIdx = ersterIdx((e) => e.typ === "sprinter");
    if (!sprinter.length) m("A-5", "keine Sprinteraufgabe (sprinter) — AFB III fuer die Schnellen fehlt.");
    else {
      if (sprinter.length > 1) m("A-5", `${sprinter.length} sprinter-Elemente — eine Sprinteraufgabe je Stunde.`);
      if (merkIdx >= 0 && sprIdx < merkIdx) m("A-5", "Sprinteraufgabe steht vor dem Merksatz-Anschluss — sie folgt auf die Antwort der Stundenfrage.");
      if (letzteAufgabeIdx > sprIdx) m("A-5", "nummerierte Aufgaben nach der Sprinteraufgabe — AFB I/II gehoeren vor den Sprinter.");
    }

    // ---- A-3: AFB-Progression (nur mit afb-Angaben pruefbar)
    const mitAfb = aufgaben.filter((e) => e.afb != null);
    if (!mitAfb.length) {
      m("A-3", "keine afb-Angaben an den Aufgaben — AFB-Progression und Materialbezug nicht pruefbar (afb: I | II | III und bezug: je aufgabe).");
      return;
    }
    const ohneAfb = aufgaben.filter((e) => e.afb == null).map((e) => e.nr);
    if (ohneAfb.length) m("A-3", `Aufgabe(n) ohne afb: ${ohneAfb.join(", ")}.`);
    const kette = [];
    aufgaben.forEach((e) => {
      const k = afbVon(e);
      if (k == null) return;
      if (AFB_RANG[k]) kette.push({ nr: e.nr, afb: k });
      else m("A-3", `Aufgabe ${e.nr}: afb '${e.afb}' unbekannt (I, II, III).`);
    });
    if (kette.length && kette[0].afb !== "I") m("A-3", `erste Aufgabe (${kette[0].nr}) ist AFB ${kette[0].afb} — die Stunde beginnt mit AFB I.`);
    if (!kette.some((k) => k.afb === "II")) m("A-3", "keine AFB-II-Aufgabe — die Stundenfrage wird auf AFB II beantwortet.");
    for (let i = 1; i < kette.length; i++) {
      if (AFB_RANG[kette[i].afb] < AFB_RANG[kette[i - 1].afb])
        m("A-3", `Aufgabe ${kette[i].nr} (AFB ${kette[i].afb}) nach Aufgabe ${kette[i - 1].nr} (AFB ${kette[i - 1].afb}) — Progression I → II, kein Rueckfall.`);
    }
    kette.filter((k) => k.afb === "III").forEach((k) =>
      m("A-5", `Aufgabe ${k.nr} ist als nummerierte Aufgabe AFB III — AFB III gehoert in die Sprinteraufgabe.`));

    // ---- A-1 / A-2: Bezug
    const erste = aufgaben[0];
    if (erste && !erste.bezug) m("A-1", `Aufgabe ${erste.nr} ohne bezug — Anknuepfung an den Einstieg ausweisen (bezug: Einstieg | Simulation | Versuch | Abbildung | …).`);
    const ohneBezug = aufgaben
      .filter((e) => e !== erste && e.afb != null && !istSprinterAfb(e) && !e.bezug)
      .map((e) => e.nr);
    if (ohneBezug.length) m("A-2", `Aufgabe(n) ohne bezug: ${ohneBezug.join(", ")} — nennen, worauf die SuS in diesem Moment schauen.`);
  });

  // ---- A-4 (Blatt, Kit 1.7): ein Blatt, eine Stundenfrage. Ueber ALLE Seiten
  // zaehlen — Vorder-/Rueckseite eines Blocks sind legitim, zwei Bloecke auf
  // einem Blatt nicht (Anlass: AB_Wasserbestandteile_GR v2.2 mit B3 und B4).
  // Laeuft nur, wenn die Spec ueberhaupt eine Stundenseite hat; reine
  // Ablaufplaene ohne aufgabe und stundenfrage bleiben wie bisher stumm.
  // Fehlende Stundenfrage meldet weiterhin die Seitenpruefung oben.
  const alle = (spec.seiten || []).flatMap((s) => elementeFlach(s.elemente));
  if (alle.some((e) => e.typ === "aufgabe" || e.typ === "stundenfrage")) {
    const zaehl = (pred) => alle.filter(pred).length;
    const nSF = zaehl((e) => e.typ === "stundenfrage");
    const nSprinter = zaehl((e) => e.typ === "sprinter");
    const nPunkt = zaehl((e) => e.typ === "ritual" && e.kanon === "punkt");
    const grund = "— ein Blatt, eine Stundenfrage (AB_Qualitaet.md, A-4). Blöcke auf getrennte Specs aufteilen.";
    const blatt = (text) => befunde.push(`Bauplan A-4 · Blatt: ${text} ${grund}`);
    if (nSF > 1) blatt(`Blatt trägt ${nSF} Stundenfragen`);
    if (nSprinter > 1) blatt(`Blatt trägt ${nSprinter} Sprinteraufgaben`);
    if (nPunkt > 1) blatt(`Blatt trägt ${nPunkt} Merksatz-Rituale (ritual kanon: punkt)`);
  }
  return befunde;
}

/* ============================================================== CLI ===== */

function soffice() {
  const kandidaten = ["soffice", "C:\\Program Files\\LibreOffice\\program\\soffice.exe",
    "C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe"];
  // Nur Existenzpruefung — `soffice --version` startet eine ganze Instanz
  // und kostet auf manchen Rechnern eine Minute.
  for (const k of kandidaten.slice(1)) if (fs.existsSync(k)) return k;
  for (const dir of (process.env.PATH || "").split(path.delimiter)) {
    for (const name of ["soffice", "soffice.exe"]) {
      if (dir && fs.existsSync(path.join(dir, name))) return path.join(dir, name);
    }
  }
  return null;
}

async function main() {
  const argv = process.argv.slice(2);
  if (!argv.length || argv[0].startsWith("--")) {
    console.log("Aufruf: node ab_kit.js <spec.yaml> [--out DIR] [--pdf] [--force] [--check]");
    process.exit(1);
  }
  const specPfad = path.resolve(argv[0]);
  let spec;
  try { spec = YAML.parse(fs.readFileSync(specPfad, "utf8")); }
  catch (err) { fehler(`Spec nicht lesbar: ${err.message}`); }
  specPruefen(spec);
  // Vor dem Bauplan-Check: zitierte Aufgaben tragen danach ihren Text.
  const zitate = zitateAufloesen(spec, specPfad);
  aufgabenBilanz(spec);              // _punkte_gesamt fuer das Rendering (Kit 1.8)
  const bauplan = (spec.dokumenttyp ?? "ab") === "uebung" ? uebungPruefen(spec) : bauplanPruefen(spec);
  bauplan.forEach((b) => warnung(b));
  if (argv.includes("--check")) {
    console.log(`Check ${path.basename(specPfad)}: Spec ok (Kit ${KIT_VERSION}), `
      + `Bauplan ${bauplan.length ? bauplan.length + " Befund(e)" : "ohne Befund"}`
      + ((spec.dokumenttyp ?? "ab") === "uebung" ? " (Uebung — \u00dc-1 bis \u00dc-5 statt Bauplan)"
        : (spec.dokumenttyp ?? "ab") !== "ab" ? " (Loesung — Bauplan nicht geprueft)" : "")
      + (zitate ? `, ${zitate} Zitat(e) aus ${spec.ab_spec}` : ""));
    warnungen.forEach((w) => console.log("  Warnung: " + w));
    hinweise.forEach((h) => console.log("  Hinweis: " + h));
    return;
  }
  ST = stilAufloesen(spec);
  const stamm = path.basename(spec.ausgabe, path.extname(spec.ausgabe));
  const outDir = argv.includes("--out")
    ? path.resolve(argv[argv.indexOf("--out") + 1])
    : path.join(KIT_DIR, "_build", stamm);
  fs.mkdirSync(outDir, { recursive: true });
  CTX = { outDir, spec };

  const sections = spec.seiten.map((s) => seiteBauen(s, spec));
  const doc = new Document({
    creator: "ab_kit " + KIT_VERSION,
    title: spec.titel,
    styles: {
      // Bewusst KEIN spacing.line: schneidet in LibreOffice Bilder ab.
      default: { document: { run: { font: ST.font, size: ST.groesse, color: farbe(ST.farbe_text) } } },
    },
    sections,
  });
  const buf = await Packer.toBuffer(doc);
  const docxPfad = path.join(outDir, spec.ausgabe);
  fs.writeFileSync(docxPfad, buf);
  console.log(`${spec.ausgabe} geschrieben -> ${outDir}  (Profil ${ST.profil}, Kit ${KIT_VERSION})`
    + (zitate ? `
   ${zitate} Aufgabenzitat(e) aus ${spec.ab_spec} uebernommen` : ""));

  if (argv.includes("--pdf")) {
    const so = soffice();
    if (!so) { warnung("soffice nicht gefunden — kein PDF erzeugt."); }
    else {
      // Eigenes LibreOffice-Profil auf C: — kein Lock-Konflikt mit einer offenen
      // LibreOffice-Instanz und kein Profil auf Google Drive (langsam).
      const profil = path.join(process.env.LOCALAPPDATA || process.env.HOME || KIT_DIR, "ab_kit_lo_profil");
      fs.mkdirSync(profil, { recursive: true });
      const t0 = Date.now();
      execFileSync(so, [
        `-env:UserInstallation=file:///${profil.replace(/\\/g, "/")}`,
        "--headless", "--norestore", "--convert-to", "pdf", "--outdir", outDir, docxPfad,
      ], { stdio: "ignore", timeout: 300000, windowsHide: true });
      console.log(`${stamm}.pdf geschrieben (${Math.round((Date.now() - t0) / 1000)} s)`);
    }
  }
  warnungen.forEach((w) => console.log("  Warnung: " + w));
  hinweise.forEach((h) => console.log("  Hinweis: " + h));
}

main().catch((err) => { console.error(err); process.exit(1); });
