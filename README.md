# AB-Kit — Arbeitsblätter und Lösungen aus einer Spec

Kit-Version: siehe `KIT_VERSION` · Stand 08.09.2026 · Repo: `https://github.com/mrhey111/ab-kit` (öffentlich, kanonisch) · Arbeitskopie Windows: `C:\dev\ab_kit\` (Klon)
<!-- schema-bindung: v1.16 (2026-09-08) -->

Ein Renderer, alle Unterschiede zwischen Blättern stehen in der Spec. Pro
Arbeitsblatt oder Erwartungshorizont gibt es genau eine Textdatei
`<Stamm>.spec.yaml` im Blockordner des Archivs (Konvention: `_Sessions\2026-09_Archivpaket\Spec_Konvention.md`).
Das Kit ersetzt `Python_Skripte\CH-09.WAS\build_*.js`, `scaffold_gen.py`,
`diagramm_gen.py` und `Python_Skripte\_gemeinsam\Layout_wh.js`.

## Dateien

| Datei | Zweck |
|---|---|
| `KIT_VERSION` | Versionsmarke (eine Zeile). Jede Spec trägt `kit_version`; Major-Abweichung = Abbruch. |
| `ab_assets.py` | Erzeugt aus dem Block `assets:` der Spec alle PNGs (RGB) plus Sidecar `<name>.json` mit Anzeigegröße. |
| `ab_kit.js` | Rendert die Spec zu docx, optional zu PDF (`--pdf`, braucht `soffice`). |
| `package.json` | Abhängigkeiten `docx`, `yaml` — siehe Installation. |
| `bau.ps1` | Windows: Check, Assets, Bau mit PDF für eine oder mehrere Specs und Ablage von docx + pdf **neben der Spec** (Blockordner). `-NurCheck` für den reinen Check. |
| `_build\<Stamm>\` | Zwischenprodukte (PNG, JSON, docx, pdf). Nie ins Archiv kopieren, außer docx + pdf. |
| `_build\specs\` | Arbeitskopien der Specs während einer Session; die gültige Spec liegt im Blockordner. |

## Installation

**Windows — die Arbeitskopie ist ein Klon des Repos unter `C:\dev\ab_kit\`,
nie auf Google Drive (Falle 8).** Ein Befehl prüft und installiert alles
Fehlende inkl. LibreOffice und macht einen Funktionstest:

```
git clone https://github.com/mrhey111/ab-kit C:\dev\ab_kit
powershell -ExecutionPolicy Bypass -File "C:\dev\ab_kit\setup_windows.ps1"
```

Von Hand entspricht das:

```
pip install pillow pyyaml
npm install -g docx yaml
```

Statt global geht auf `C:` auch `npm install` im Kit-Ordner; `ab_kit.js` sucht
die Module zuerst lokal, dann im globalen npm-Root (`%APPDATA%\npm\node_modules`).
Auf Google Drive `npm install` nie ausführen — dort entstehen 0-Byte-Dateien
(Falle 8). Für PDF: LibreOffice (`winget install TheDocumentFoundation.LibreOffice`);
`ab_kit.js` findet `soffice` über PATH oder `C:\Program Files\LibreOffice\program\`.
Git-Ablauf (commit, push, pull): `G:\Meine Ablage\_Sessions\2026-09_Archivpaket\AB-Kit_Git-Kurzanleitung.md`.

**Linux-Container:** siehe „Nutzung im Container".

## Nutzung im Container

Der Kit liegt öffentlich unter `https://github.com/mrhey111/ab-kit`. Ein
Claude-Container (erlaubte Domains: github.com, raw.githubusercontent.com,
registry.npmjs.org, pypi.org) holt und baut ihn selbst:

```
git clone https://github.com/mrhey111/ab-kit
cd ab-kit
pip install pillow pyyaml
npm install
```

`soffice` ist im Container vorhanden, `--pdf` funktioniert also ohne
Installation; ebenso `pdftoppm` für die Sichtprüfung. Fonts: Liberation Sans
ist die erste Stufe der Fallbackkette (Falle 11), die PNGs werden damit
genauso breit wie unter Windows mit Arial.

Der Container hat keinen Zugriff auf `G:`. Deshalb:

- Die Spec wird als **Arbeitskopie** in den Container gebracht (Upload oder
  Wortlaut aus dem Chat) und dort gebaut, z. B. unter `_build/specs/`. Die
  gültige Spec bleibt die im Blockordner des Archivs.
- Assets vom Typ `bilddatei` mit absolutem `G:`-Pfad (`pfad: 'G:\…'`)
  müssen in der Arbeitskopie auf einen Container-Pfad umgebogen werden; das
  Bild selbst wird mit hochgeladen. Relative Pfade lösen gegen den Ordner
  der Spec auf und funktionieren unverändert, wenn das Bild daneben liegt.
  In der Spec, die ins Archiv geht, steht wieder der `G:`-Pfad.
- `kit_version` der Spec muss zur `KIT_VERSION` des Klons passen (Major),
  sonst bricht der Lauf ab — bei einem alten Klon `git pull`.

Ablauf im Container:

```
python ab_assets.py _build/specs/AB_X_GR.spec.yaml
node   ab_kit.js   _build/specs/AB_X_GR.spec.yaml --pdf
pdftoppm -r 60 -png _build/AB_X_GR/AB_X_GR.pdf _build/AB_X_GR/seite
```

Ergebnis der Container-Session ist die geprüfte Spec; Fabian baut sie lokal
einmal und legt docx und pdf in den Blockordner. Nichts aus `_build/`, keine
Spec und kein Bild darf ins Repo (siehe `.gitignore`).

## Ablauf

**Windows, ein Befehl (empfohlen):**

```
& "C:\dev\ab_kit\bau.ps1" "<Blockordner>\AB_X_GR.spec.yaml" "<Blockordner>\Loesung_X.spec.yaml"
```

`bau.ps1` führt je Spec `--check`, `ab_assets.py` und `ab_kit.js --pdf` aus
und kopiert docx **und** pdf neben die Spec, also in den Blockordner
(Namensparität). Zwischenprodukte bleiben in `_build\<Stamm>\`. Der Stamm
kommt aus dem Spec-Feld `ausgabe`. Schlägt der Check fehl, wird die Spec
übersprungen; Exitcode = Zahl der Probleme. `-NurCheck` prüft nur.

**Von Hand (Windows und Container):**

```
cd C:\dev\ab_kit
python ab_assets.py "<Blockordner>\AB_X_GR.spec.yaml"
node   ab_kit.js   "<Blockordner>\AB_X_GR.spec.yaml" --pdf
```

Ausgabe landet in `_build\AB_X_GR\`. Von dort docx **und** pdf in den
Blockordner kopieren (Namensparität, Lint warnt bei Solo-docx). Optional
`--out DIR` für einen anderen Zielordner, `--force` bei Major-Abweichung der
`kit_version`, `--check` für den reinen Spec- und Bauplan-Check ohne Bau
(braucht keine Assets, dauert unter einer Sekunde — vor jedem Bau sinnvoll).

Sichtprüfung immer über das PDF (`pdftoppm -r 60 -png`), nie über die docx.

## Spec-Format (Kurzreferenz)

```yaml
kit_version: "1.0"          # Pflicht — Kit-Stand, mit dem die Spec gebaut wurde
dokumenttyp: ab             # ab | loesung | uebung (Übungsblatt, Kit 1.8)
block: CH-09.WAS-B3         # Pflicht
titel: Wasserbestandteile   # Pflicht — Kurzname des Materials
zweig: GR                   # Pflicht — GR | G | R | H | LK (Lösung)
ausgabe: AB_Wasserbestandteile_GR.docx   # Pflicht — Dateiname der Ausgabe
stand: 2026-09-03           # Pflicht — ISO, Stand dieser Spec
version: "2.2"              # optional — Materialversion (Blueprint-Bezug)
ab_spec: AB_Wasser_GR.spec.yaml   # optional (Kit 1.5) — nur `dokumenttyp: loesung`:
                            # Quelle für Aufgabenzitate, relativ zum Spec-Ordner
afb_richtwert: {I: 20, II: 60, III: 20}   # optional (uebung, Kit 1.8) — sonst Default je zweig
afb_toleranz: 5             # optional (uebung) — Prozentpunkte, Default 5 (wie die LK)
afb3_hinweis: "Zusatz — freiwillig. …"   # optional (uebung) — Kasten vor der ersten AFB-III-Aufgabe
stil:                       # optional — Profil + Überschreibungen
  profil: kompakt           # kompakt | kanon | loesung-kompakt | loesung-kanon
  rand: {oben: 850, unten: 850, links: 850, rechts: 850}
kopf:                       # optional — Kopfzeile auf jeder Seite
  links: "Chemie · Jahrgang 9 · Wasser und Wasserstoff"
bauplan:                    # optional — nur für den ausdrücklichen Opt-out
  scaffold: false           # Merksatz-Scaffold weglassen (Default: Pflicht)
seiten:                     # Pflicht — jede Seite = eigene docx-Section = eine Stunde
  - titel: Wasser enthält Sauerstoff
    untertitel: "Arbeitsblatt · Teil 1"
    elemente:
      - {typ: aufgabe, nr: "1", afb: I, bezug: Einstieg, text: Vermuten und beobachten}
      - ...                 # afb: I | II | III und bezug: je aufgabe (Bauplan-Check)
assets:                     # optional — PNG-Generatoren (ab_assets.py)
  scaffold_teil1: {typ: scaffold, zeilen: [[b, "Notanker …"], [r, "…"]]}
```

**Inline-Markup** in allen Textfeldern: `**fett**`, `*kursiv*`. Alternativ
Runs als Liste `[["Text", {fett: true, groesse: 26, farbe: akzent}], …]`.
Farbnamen: `text`, `dunkel`, `grau`, `hellgrau`, `rahmen`, `hell`, `akzent`,
sonst Hex.

### Profile (Defaults für `stil:`)

| Profil | Vorbild | Schrift | Ränder (twips) | Kästen |
|---|---|---|---|---|
| `kompakt` | CH-09.WAS AB | Calibri 11 | 850 rundum | schlicht (Kopf + Kasten darunter) |
| `kanon` | PH-10.SGE AB (Layout_wh) | Calibri 10 | 720/900/500/900 | gerahmt mit Label |
| `loesung-kompakt` | CH-09.WAS Lösung | Calibri 10,5 | 850 rundum | — |
| `loesung-kanon` | PH-10.SGE Lösung | Arial 10,5 | 900/1000/700/1000 | gerahmt, Marker ▸ |

Alle Profilwerte lassen sich unter `stil:` einzeln überschreiben
(`font`, `groesse`, `rand`, `satzbreite`, `farben`, `kaesten`, `zelle`, …).

### Elementtypen

| typ | Felder | Bemerkung |
|---|---|---|
| `kopfzeile` | `links`, `rechts`, `variante: zeile\|tabelle`, `titel`, `zeile_oben`, `sperrung`, `breite_rechts` | meist über `kopf:` + Seiten-`titel` automatisch; `zeile_oben` = Kleinzeile über dem Titel (Layout_wh) |
| `namenszeile` | `name_bis`, `datum_ab` | Name/Datum mit Unterstrich-Leadern (Layout_wh) |
| `titel` | `text`, `untertitel`, `linie` | |
| `abschnitt` | `text`, `umbruch` | unnummerierter Kopf (Stundenfrage, Sprinteraufgabe, …) |
| `ueberschrift` | `text`, `ebene: 1\|2` | Lösungen |
| `aufgabe` | `nr`, `text`, `zitat`, `unterzeile`, `umbruch`, `afb`, `bezug`, `punkte` | `punkte` (Kit 1.8) rechtsbündig als „(4 P)“, bei Teilaufgaben deren Summe; `zitat: true` = AB-Wortlaut grau-kursiv (Lösung), ohne `text` wird er aus `ab_spec` gezogen (siehe Aufgabenzitate); `afb: I\|II\|III` und `bezug` (Einstieg, Simulation, Versuch, …) werden nicht gerendert, nur vom Bauplan-Check gelesen |
| `anweisung` / `text` | `text`, `groesse`, `fett`, `kursiv`, `farbe`, `vor`, `nach`, `einzug`, `ausrichtung` | |
| `stichpunkte` | `punkte: []` | Aufzählung |
| `loesung` | `text` | Lösungsabsatz mit Marker |
| `punkteraster` | `titel` | Bewertungsraster einer Lösung zu einem Übungsblatt (Kit 1.8): Aufgabentabelle, AFB-Summen mit Anteil, Soll/Ist — wird am Ende automatisch angehängt, wenn `ab_spec` auf eine `uebung`-Spec zeigt und das Element nicht selbst platziert ist |
| `stundenfrage` | `modus: fest\|platzhalter`, `text`, `hoehe`, `zeilen`, `label`, `sperrung`, `staerke`, `rahmen` | K-008: Platzhalter zum Selbsteintragen; Profil-Defaults `stundenfrage_label/_sperrung/_fett/_staerke/_rahmen` |
| `ritual` | `kanon: vermuten\|punkt`, `label`, `zusatz`, `zusatz_inline` | 🔮 / 🎯, Wortlaut aus dem Profil; `label: ""` = ohne Label (Layout_wh) |
| `teilaufgabe` | `buchstabe`, `text`, `zitat`, `einzug`, `punkte`, `afb` | `punkte`/`afb` (Kit 1.8) für Übungsblätter, `afb` erbt von der Aufgabe; a) / b) unter einer Aufgabe; `zitat: true` = AB-Wortlaut grau-kursiv (Lösung), ohne `text` aus `ab_spec` gezogen — gematcht über `buchstabe` unter der vorangehenden `aufgabe` (Kit 1.6) |
| `ankreuzen` | `optionen: []`, `einzug` | ☐-Zeilen |
| `zitat` | `text`, `einzug` | wörtlicher AB-Text in der Lösung, grau-kursiv |
| `raster` / `tabelle` | `spalten: [{kopf, breite, ausrichtung}]`, `zeilen`, `zeilenhoehe`, `gruppen`, `luecke`, `kopf_fuellung` | `zeilen`-Eintrag: String (Label 1. Spalte) oder Liste von Zellen; Zelle: String oder `{text, fett, farbe}`; `gruppen` = Tabellen nebeneinander |
| `schreibkasten` | `hoehe`, `breite` | |
| `schreiblinien` | `anzahl`, `einzug`, `abstand` | Tab-Leader, nie Absatzrahmen |
| `lueckenzeile` | `text` mit `\t`, `positionen: []`, `groesse`, `einzug`, `zusatzlinien` | Unterstrich-Leader je Tab; Position als Zahl oder `{pos, leader: false}`; mit `zusatzlinien` = Satzmuster |
| `infokasten` | `titel`, `absaetze`, `punkte`, `fuellung`, `rahmen`, `staerke`, `zelle` | grau (`hell`) als Default |
| `befundkasten` | wie infokasten | Titel „Befund — ergänzt durch die Lehrkraft" |
| `merksatz` | `variante: inline\|kasten`, `scaffold`, `hoehe`, `zeilen`, `hinweis` | inline = Notanker rechts neben der Schreibfläche (alt) |
| `notanker` | `scaffold`, `position: fuss\|hier`, `ab_seite: 1\|2`, `hinweis`, `breite` | Default: gedreht im Seitenfuß (Section-Footer) mit Dreh-Hinweis |
| `bild` / `balkenraster` | `asset`, `breite`, `ausrichtung`, `vor`, `nach` | |
| `nebeneinander` | `links`/`rechts` (Elementlisten) oder `links_bild`/`rechts_bild`, `breite_links`, `breite_rechts`, `breite_bild`, `valign`, `luecke`, `rahmen` | eine Tabelle; `luecke` = Lückenspalte, `rahmen: grau` = beide Zellen gerahmt (Planpaar) |
| `sprinter` | `text` (String/Liste) oder `aufgaben` (a), b), …), `hoehe`, `label`, `emoji`, `sperrung`, `linien`, `abstand` | `linien` = Schreiblinien je Teilaufgabe im Kasten |
| `leer` | `hoehe` | |
| `seitenumbruch` | — | |

Aufnahmeregel: Ein Elementtyp kommt ins Kit, wenn er zweimal gebraucht
wurde. Ein wirklich neuer Typ braucht eine Renderer-Erweiterung in
`ab_kit.js` (`ELEMENTE.<name>`), einen Eintrag hier und einen Bump von
`KIT_VERSION`.

### Asset-Typen (`ab_assets.py`)

| typ | Felder |
|---|---|
| `scaffold` | `zeilen: [[b\|r\|i, text]]`, `pt`, `zeilenabstand`, `innenabstand`, `farbe`, `rahmen` |
| `stromkreis` | `breite`, `messgeraet: A\|V` (sonst leer) | WH-Stil: Lampe oben, Quelle mit Polen unten — Bestand, für neue Specs `schaltbild` |
| `balkenraster` | `breite`, `hoehe`, `y_titel`, `y_max`, `y_schritt`, `kategorien` |
| `achsenkreuz` | `breite`, `hoehe`, `x_label`, `y_label`, `gitter: [nx, ny]`, `felder: {x, y}`, `pfeile` |
| `schaltplan` | `breite`, `quelle`, `bauteil`, `messgeraete: true\|false` | Bestand, für neue Specs `schaltbild` |
| `kennlinien` | `breite`, `hoehe`, `x_max`, `x_schritt`, `y_max`, `y_schritt`, `reihen: [{name, u, i, farbe, marker, kurve: gerade\|potenz\|keine}]` |
| `bilddatei` | `pfad`, `breite`, `beschnitt: {links, oben, rechts, unten}` (Anteile 0..1), `graustufen`, `autokontrast`, `cutoff`, `rahmen`, `rahmenfarbe` |
| `schaltbild` | `breite`, `hoehe`, `reihe: [{bauteil, label, zustand, zellen, pole, umgekehrt, farbe, seite} \| {zweige: [[…], […]], seite}]`, `zweigabstand`, `farbe` | Kit 1.4: Schaltplan aus Bauteilen + Topologie, siehe unten |
| `kreislauf` | `breite`, `hoehe`, `stationen: [2..4]`, `pfeile: [{label}]` — oder Kurzform `oben`, `unten`, `rechts: {label}`, `links: {label}`; `feld: [b, h]`, `aussenrand`, `pt`, `farbe` | Kit 1.9: Stoffkreislauf mit 2 bis 4 Stationen im Umlauf, Beschriftungskästchen je Übergang, siehe unten |

`bilddatei` bindet ein vorhandenes Bild ein (Foto, Scan, extern erzeugtes PNG)
statt es zu zeichnen — der Zuschnitt steht damit in der Spec, nicht in einer
zweiten Bilddatei. Relative `pfad`-Angaben werden gegen den **Ordner der Spec**
aufgelöst, nicht gegen den Kit-Ordner. Transparenz wird auf Weiß gelegt
(Falle 4). Für Fremdbilder gehört die Quellenangabe als Textelement unter das
Bild (§ 63 UrhG) und die Quelle in die Quellentabelle des Blueprints.

Alle Assets werden 4-fach aufgelöst gerendert; die Anzeigegröße steht im
Sidecar-JSON und wird beim Einbetten verwendet. `breite` am Element
überschreibt sie proportional.

### Asset-Typ `schaltbild` (Kit 1.4)

Schaltplan aus einer deklarativen Beschreibung: Bauteile plus Topologie.
Ersetzt für neue Specs die starren Typen `schaltplan` und `stromkreis`, die
unverändert bestehen bleiben (bestehende Specs müssen bitgleich bauen).

```yaml
plan_b6:
  typ: schaltbild
  breite: 260                 # Anzeigebreite px; hoehe optional (sonst aus Inhalt)
  reihe:                      # Umlauf im Uhrzeigersinn, Start auf der linken Seite
    - {bauteil: quelle, label: "4,5 V", pole: true}
    - {bauteil: schalter, zustand: offen, label: S1}
    - {bauteil: lampe}
    - {bauteil: schalter, zustand: offen, label: S2}
plan_b7:
  typ: schaltbild
  breite: 300
  reihe:
    - {bauteil: quelle, pole: true}
    - zweige:                 # parallele Zweige, jeder Zweig wieder eine Reihe
        - [{bauteil: lampe, label: L1}]
        - [{bauteil: lampe, label: L2}]
```

**Bauteile** (`bauteil:`, DIN EN 60617): `quelle` (`zellen: n`, `pole: true`
für + und −, `umgekehrt: true` dreht die Polung), `lampe`, `schalter`
(`zustand: offen` — Default, Ruhestellung nach DIN EN 60617-7 — oder
`geschlossen`), `taster`, `widerstand`, `widerstand_veraenderbar` (Alias
`potentiometer`), `amperemeter`, `voltmeter`, `motor`, `klingel`, `summer`,
`led`, `diode` (beide mit `umgekehrt`), `sicherung`, `kreuzung` (Leiterkreuzung
ohne Verbindung), `verbindung` (Verbindungspunkt), `klemme` (offene Stelle /
Klemmstelle für Prüfstromkreise; Aliasse `offen`, `klemmstelle`), `leer`
(Leitungsstück als Abstandhalter). Je Bauteil optional `label`,
`label_stil: kursiv`, `farbe` (Hex) und `seite`. Unbekanntes Bauteil = Abbruch
mit Liste.

**Topologie und Seitenzuordnung.** Ohne `seite:` verteilt der Generator
automatisch: erster Eintrag auf die linke Seite (dort steht üblicherweise die
Quelle); die erste Zweiggruppe auf die rechte Seite als Leiter, Einträge davor
oben, danach unten; ohne Gruppe werden die übrigen Einträge gleichmäßig auf
oben, rechts, unten verteilt (Reihenfolge = Umlauf). Wer die Verteilung selbst
festlegt, gibt `seite: links|oben|rechts|unten` an **jedem** Eintrag (alle
oder keiner — Mischung bricht ab). Gruppen auf einer senkrechten Seite werden
als Leiter gezeichnet (Zweige parallel zur Seite, nach innen, Knotenpunkte auf
der oberen und unteren Leitung); Gruppen auf einer waagerechten Seite als
Schleife nach außen — das ist das Voltmeter-Bild (Zweig 1 auf der Leitung,
Zweig 2 darüber). Verschachtelte Gruppen sind bewusst nicht vorgesehen
(Sek I braucht sie nicht).

**Zeichenregeln, fest verdrahtet:** nur waagerechte und senkrechte Leitungen;
Eckabstand 24 px, also nie ein Bauteil in der Ecke; Bauteile gleichmäßig auf
der Seite verteilt; Labels immer aufrecht, nach außen; Polung so, dass der
Strom im Uhrzeigersinn fließt (links: + oben). Reicht der Platz auf einer
Seite nicht (40 px je Bauteil), bricht der Generator mit Angabe der Seite ab
— `breite`/`hoehe` erhöhen oder anders verteilen. Weitere Felder:
`zweigabstand` (Default 44), `farbe` (Default `1A1A1A`).

Testfälle mit den vier Akzeptanzplänen (PH-08.STK-B6 Reihenschaltung, B7
Parallelschaltung, B5 Prüfstromkreis, PH-10.SGE-B3 nachgebaut) und einem
Bauteilkatalog: `_build\specs\schaltbild_test.spec.yaml`.

### Asset-Typ `kreislauf` (Kit 1.9)

Stoffkreislauf (Kreisprozess) mit 2 bis 4 Stationen im Umlauf, Uhrzeigersinn,
erste Station oben. Auf jedem Übergang sitzt ein Beschriftungskästchen — leer
zum Eintragen oder mit `label`. Links und rechts bleibt ein freier Rand
(`aussenrand`), in dem die SuS eigene Pfeile ergänzen (im Erstfall die
Energiezufuhr und -abgabe).

```yaml
kreislauf_b6:                 # Kurzform, zwei Stationen (CH-09.WAS-B6)
  typ: kreislauf
  breite: 430                 # Anzeigebreite px (Default 430), hoehe Default 205
  oben: "Wasser"
  unten: "Wasserstoff  +  Sauerstoff"
  rechts: {label: ""}         # Pfeil oben -> unten; leer = Kästchen zum Eintragen
  links: {label: ""}          # Pfeil unten -> oben
  feld: [112, 30]             # Beschriftungskästchen Breite x Höhe (Default)
  aussenrand: 46              # freier Rand links und rechts (Default)
wasserkreislauf:              # Langform, 2 bis 4 Stationen
  typ: kreislauf
  breite: 480
  hoehe: 240
  stationen: ["Meer", "Wolken", "Regen", "Fluss"]
  pfeile:                     # je Übergang ein Eintrag, Station 1 -> 2 zuerst
    - {label: "Verdunstung"}
    - {label: "Kondensation"}
    - {label: "Niederschlag"}
    - {label: "Abfluss"}      # letzte Station -> erste, der Umlauf schließt sich
```

| Feld | Bedeutung | Default |
|---|---|---|
| `stationen` | Langform: Liste der Stationstexte (fett, einzeilig), 2 bis 4 | Pflicht (Langform) |
| `pfeile` | Langform: je Übergang `{label: "…"}`, genau so viele Einträge wie `stationen`; fehlt der Block, entstehen leere Kästchen | leer |
| `oben`, `unten`, `rechts`, `links` | Kurzform für zwei Stationen: Kastentexte und `{label: "…"}` für den rechten (abwärts) bzw. linken (aufwärts) Pfeil; rendert bitgleich zu `stationen: [oben, unten]`, `pfeile: [rechts, links]`. Mischung mit der Langform = Abbruch | — |
| `breite`, `hoehe` | Anzeigegröße px | 430 × 205 |
| `feld` | `[breite, hoehe]` des Beschriftungskästchens | `[112, 30]` |
| `aussenrand` | freier Rand links und rechts, außerhalb der senkrechten Leitungen | 46 |
| `pt` | Schriftgröße in Punkt (Stationen fett, Labels regular) | 10 |
| `farbe` | Linien- und Schriftfarbe (Hex) | `1A1A1A` |

**Anordnung.** 2 Stationen: oben/unten, Pfeile rechts abwärts und links
aufwärts, Kästchen auf halber Höhe (das B6-Bild). 3 Stationen: Dreieck —
oben Mitte, unten rechts, unten links; die Übergänge 1 → 2 und 3 → 1 laufen
mit einer Ecke über die senkrechten Leitungen, 2 → 3 waagerecht unten.
4 Stationen: Rechteck — Stationen in den Ecken, alle Übergänge gerade. Die
senkrechten Leitungen liegen bei `aussenrand + feld[0]/2`; Eckstationen (3
und 4) sind auf diese Leitungen zentriert und ragen in den Außenrand hinein.

**Zeichenregeln, fest verdrahtet** (wie `schaltbild`): nur waagerechte und
senkrechte Leitungen, rechte Winkel, Labels aufrecht, Kästchen auf der Mitte
eines geraden Stücks und nie in einer Ecke, mindestens 14 px Leitung vor
jedem Kasten und Kästchen. Reicht der Platz nicht, bricht der Generator mit
Angabe der Seite ab statt still zu überlappen: Kasten breiter als der Abstand
zwischen den Leitungen (Seite `oben`/`unten`, bei den Defaults 198 px), zwei
Kästen plus Kästchen breiter als die Seite, Kasten über dem Bildrand
(`links`/`rechts`), Label breiter als `feld`, senkrechte Leitung kürzer als
`feld[1]` + 28 px (`hoehe`). Die Abhilfe steht in der Meldung (`breite`/
`hoehe` erhöhen, `aussenrand`/`feld` verkleinern, Text kürzen).

Testfälle: `_build\specs\kreislauf_test.spec.yaml` (B6 in Kurz- und Langform,
bitgleich; Labels; abweichende `pt`/`feld`/`aussenrand`; drei und vier
Stationen) und `_build\specs\kreislauf_fehler_*.spec.yaml` (neun
Abbruchfälle).

## Aufgabenzitate aus der AB-Spec (Kit 1.5)

Im Erwartungshorizont steht der Aufgabentext noch einmal, grau-kursiv
(`zitat: true`). Bisher war das eine Kopie von Hand — änderte sich der
Wortlaut auf dem Blatt, lief die Lösung stillschweigend hinterher.

Eine Lösungs-Spec kann die AB-Spec deshalb benennen:

```yaml
dokumenttyp: loesung
ab_spec: AB_Kennlinie_GR.spec.yaml     # relativ zum Ordner der Lösungs-Spec
seiten:
  - elemente:
      - {typ: aufgabe, nr: "2", zitat: true}     # Text kommt aus dem AB
      - {typ: loesung, text: "…"}
```

Ein `aufgabe`-Element mit `zitat: true` und **ohne** `text` holt seinen
Wortlaut aus der Aufgabe gleicher `nr` der referenzierten Spec. Ein
vorhandener `text` gewinnt — Bestandsspecs bleiben unverändert.

Seit Kit 1.6 gilt dasselbe für `teilaufgabe`: `{typ: teilaufgabe, buchstabe: a,
zitat: true}` holt den Text der Teilaufgabe `a` **unter der vorangehenden
`aufgabe`** gleicher `nr` — in der Lösung wie im Arbeitsblatt zählt jeweils
die zuletzt gesehene `aufgabe` derselben Seite als Anker. Damit ist auch
a)/b) driftfrei, nicht nur der Aufgabenstamm.

Regeln:

- `nr` wird als Zeichenkette zeichengenau verglichen, nicht als Zahl
  (`AB_Messen_GR` führt `nr: "1 + 2"`).
- Aufgaben innerhalb von `nebeneinander` zählen mit.
- Eine `teilaufgabe` ohne `aufgabe` davor auf derselben Seite hat keinen
  Anker: Abbruch. Fehlt der Buchstabe unter der Aufgabe im Blatt: Abbruch
  mit der Liste der dort vorhandenen Teilaufgaben.
- Fehlt die Nummer im Arbeitsblatt: Abbruch mit der Liste der vorhandenen
  Nummern.
- Führt das Arbeitsblatt eine `nr` doppelt: Abbruch. Stillschweigend die
  erste zu nehmen wäre genau die Drift, die das Feld verhindern soll.
- Die Auflösung läuft auch bei `--check`. `bau.ps1` prüft vor dem Bau,
  Drift fällt also auf, bevor irgendetwas geschrieben wird.

## Übungsblätter (`dokumenttyp: uebung`, Kit 1.8)

Ein Übungsblatt ist wie eine Arbeit gebaut: Aufgaben in AFB-Reihenfolge
I → II → III, Punktanteile wie in der Lernkontrolle je Schulzweig, AFB III
freiwillig. Der Stunden-Bauplan A-1…A-5 gilt hier ausdrücklich **nicht**
(`AB_Qualitaet.md`: Übungs- und reine Plenumsblöcke fallen nicht darunter).
Im Archiv-Schema (`_Konfiguration\Archiv_Schema.yaml`, Abschnitt
`material.spec`, v1.16) sind `uebung` als Dokumenttyp, die drei Top-Level-
Felder als Optionalfelder und `Uebung_<Name>_<Zweig>.spec.yaml` als
Dateistamm hinterlegt; die Elementfelder `punkte`/`afb` sind kein
Schema-Gegenstand.

**Spec:** alle bestehenden Elemente; `stundenfrage`, `notanker`, `sprinter`,
`ritual` sind nicht erlaubt (Ü-5). Neu: `aufgabe.punkte` und
`teilaufgabe.punkte` (Zahl > 0, Pflicht), optional `teilaufgabe.afb` (sonst von
der Aufgabe geerbt). Top-Level `afb_richtwert: {I, II, III}` in Prozent (Summe
100); fehlt es, gilt der Default je `zweig` aus `config\afb_richtwert.json`
(G 20/60/20 · R 30/60/10 · H 40/50/10 — **Kopie** des lernkontrolle-Skills,
Abschnitt „AFB-Verteilung“; Master ist der Skill). Kombinierter Zweig (`GR`)
ohne `afb_richtwert` → Warnung, Anteilsprüfung entfällt. `afb_toleranz` in
Prozentpunkten (Default 5, wie die LK im lernkontrolle-Skill; „über“ der
Toleranz warnt, genau auf der Toleranz nicht). `afb3_hinweis`
(Default „Zusatz — freiwillig. Diese Aufgaben zeigen, was für eine sehr gute
Leistung gebraucht wird.“).

**Rendering:** Kopf wie `ab`, Untertitel-Default „Übungsblatt“. Das Kit
sortiert nicht um, es warnt bei falscher Reihenfolge. Vor der ersten
AFB-III-Aufgabe steht `afb3_hinweis` als `infokasten`. Punkte je
(Teil-)Aufgabe rechtsbündig: `(4 P)`; eine Aufgabe mit Teilaufgaben zeigt
deren Summe. Keine AFB-Labels, kein Notanker, keine Ritual-Icons.

**`--check`** (nur `uebung`, Warnungen bzw. Hinweise, nie Abbruch):

| Prüfung | Befund |
|---|---|
| Ü-1 AFB-Anteile | Punktsumme je AFB gegen Richtwert; Abweichung über `afb_toleranz` → Warnung mit Ist/Soll |
| Ü-2 AFB III freiwillig | keine AFB-III-Aufgabe → **Hinweis** (zulässig; Ü-1 rechnet mit 0 %) |
| Ü-3 Reihenfolge | erste II nach der letzten I, erste III nach der letzten II — auf Aufgabenebene |
| Ü-4 Punkte | jede Aufgabe ohne Teilaufgaben und jede Teilaufgabe trägt `punkte` > 0; eigene Punkte einer Aufgabe mit Teilaufgaben müssen deren Summe sein |
| Ü-5 Fremdelemente | `stundenfrage`, `notanker`, `sprinter`, `ritual` → „nicht erlaubt bei uebung“ |

**Lösung:** `dokumenttyp: loesung` mit `ab_spec` auf die `uebung`-Spec. Die
Zitate bringen `punkte` und `afb` mit; am Ende der letzten Seite hängt das Kit
das Bewertungsraster an (`punkteraster`: Aufgabentabelle, AFB-Summen mit
Prozentanteil, Gesamtsumme, Soll/Ist — Format wie im lernkontrolle-Skill,
Schritt 3). Wer es woanders will, setzt `{typ: punkteraster}` selbst.

Testfall: `_build\specs\uebung_test.spec.yaml` (mit `Loesung_Uebungstest.spec.yaml`).

## Bauplan-Check (Kit 1.2)

Jedes Arbeitsblatt (`dokumenttyp: ab`) wird beim Bau und bei `--check` gegen
den Bauplan aus `G:\Meine Ablage\Zettlr_Unterrichtsarchiv\_Grundsaetze\AB_Qualitaet.md`
Teil A geprüft. Einheit ist eine Seite der Spec (= eine Stunde); Seiten ohne
`stundenfrage` und ohne `aufgabe` werden übersprungen, Lösungen ganz.
Nur Warnungen, nie Abbruch — der Check fängt Strukturfehler, die
Prüffragen in Teil A ersetzt er nicht.

Seit Kit 1.7 zählt der Check zusätzlich **über alle Seiten** (A-4, Blatt):
genau eine `stundenfrage`, höchstens ein `sprinter`, höchstens ein
`ritual` mit `kanon: punkt`. Vorder- und Rückseite eines Blocks sind damit
weiter legitim (`seiten` mit mehreren Einträgen), zwei Blöcke auf einem
Blatt nicht — Warnung „Blatt trägt N Stundenfragen — ein Blatt, eine
Stundenfrage (AB_Qualitaet.md, A-4). Blöcke auf getrennte Specs
aufteilen." Die Blattzählung läuft nur, wenn die Spec überhaupt eine
Stundenseite hat; reine Ablaufpläne bleiben stumm, eine fehlende
Stundenfrage meldet weiterhin die Seitenprüfung.

| Element | Prüfung | Woran der Check es erkennt |
|---|---|---|
| A-1 Anknüpfung | erste Aufgabe weist ihren Bezug aus | `bezug:` an der ersten `aufgabe` |
| A-2 Materialbezug | jede AFB-I/II-Aufgabe nennt ihre Quelle | `bezug:` an jeder `aufgabe` mit `afb: I` oder `II` |
| A-3 AFB-Progression | Start mit I, mindestens eine II, kein Rückfall, III nicht als nummerierte Aufgabe | `afb:` je `aufgabe` in Dokumentreihenfolge (auch innerhalb von `nebeneinander`) |
| A-4 Stundenfrage und Merksatz | `stundenfrage` vorhanden; Merksatz-Anschluss (`ritual kanon: punkt` oder `merksatz`) hinter der letzten Aufgabe; verdeckter Scaffold vorhanden; **Blatt (1.7):** über alle Seiten genau eine `stundenfrage`, höchstens ein `sprinter` und ein `ritual kanon: punkt` | `notanker` oder `merksatz` mit `scaffold`; Opt-out **nur** ausdrücklich über `bauplan: {scaffold: false}`; Blattzählung über `seiten` hinweg |
| A-5 Sprinteraufgabe | genau ein `sprinter`, nach dem Merksatz-Anschluss, keine Aufgaben danach | Elementreihenfolge |

Specs ohne `afb:`-Angaben (Bestand vor 1.2) bekommen nur die Strukturprüfung
A-4/A-5 und den Hinweis, dass die AFB-Kette nicht prüfbar ist. Nachrüsten
beim nächsten Anfassen (Retrofit träge), kein Bestandsdurchlauf.
Die frühere `_build\specs\bauplan_test.spec.yaml` gibt es seit dem Aufräumen von
`_build\specs` (07.09.2026) nicht mehr; ein Bauplan-Testfall ist beim nächsten
Bedarf neu anzulegen (`_build\specs` ist gitignored).

## Fallenliste — im Kit gekapselt, hier dokumentiert

1. **Kein `spacing.line` im Default-Style.** Schneidet in LibreOffice
   eingebettete Bilder ab. `ab_kit.js` setzt es nirgends.
2. **Leerer Absatz nach jeder Tabelle.** LibreOffice verschmilzt zwei direkt
   aufeinanderfolgende Tabellen. `tabelleMitSpacer()` hängt ihn automatisch an.
3. **`WidthType.DXA` + `columnWidths`** bei ungleich breiten Spalten;
   `PERCENTAGE` macht sie platt. Alle Tabellen im Kit sind DXA.
4. **PNGs als RGB, nie RGBA.** RGBA lässt den Render abstürzen.
   `ab_assets.py` konvertiert vor dem Speichern.
5. **Gedrehte Texte als PIL-PNG**, nicht als OOXML-Rotation — LibreOffice
   rendert gedrehte Textrahmen unzuverlässig.
6. **Nach dem letzten Tabstop mit Leader muss ein Zeichen folgen**, sonst
   bleibt der letzte Unterstrich weg. `lueckenzeile` und `schreiblinien` hängen
   ein geschütztes Leerzeichen an.
7. **Nutzbare Breite = 11906 − Rand links − Rand rechts** (A4 in twips);
   bei 850 twips Rand also 10206. `ab_kit.js` rechnet das aus `stil.rand`.
8. **`npm install` auf Google Drive erzeugt 0-Byte-Dateien** (608 von 622 im
   Test). Module global installieren; `ab_kit.js` sucht dort nach.
9. **YAML-Flow-Mapping und Kommas:** `{typ: text, text: Satz, mit Komma}`
   zerlegt den Text am Komma ohne Fehlermeldung. Texte mit Komma quoten oder
   als Blockskalar `>-` schreiben.
10. **YAML und „U : I":** Ein Doppelpunkt mit Leerzeichen in einem
    ungequoteten Skalar ist ein Parserfehler („mapping values are not
    allowed"). Quoten.
11. **Fontpfade nie fest verdrahten.** `ab_assets.py` läuft über eine
    Fallbackkette (Liberation → Arial → DejaVu → Calibri); Liberation Sans und
    Arial sind metrisch kompatibel, die PNGs bleiben also gleich breit.
12. **Notanker im Seitenfuß = Section-Footer.** Damit rutscht er nie auf eine
    Folgeseite (Befund PH-10.SGE: dritte PDF-Seite nur mit Scaffold). Der
    untere Seitenrand wird automatisch um die Bildhöhe erhöht; `ab_seite: 2`
    setzt `titlePage` und lässt die erste Seite der Section frei.
13. **Tabellen reißen zwischen Seiten auf.** Landet ein Tabellenkopf am
    Seitenfuß, `umbruch: true` am zugehörigen `aufgabe`-Element setzen und
    nach Inhaltsänderungen prüfen, ob der Umbruch noch sitzt.
14. **Nebeneinander = eine Tabelle mit Lückenspalte**, nie zwei Tabellen
    (siehe 2). `tabelle.gruppen` und `nebeneinander` machen genau das.
15. **Word-Nachbearbeitung erzeugt Drift.** CH-09.WAS v2.1 wurde direkt im
    Dokument geändert; Archiv-docx und Skript liefen auseinander („Das
    Simulation", „Im Unterrichtsmedium"). Änderungen gehören in die Spec,
    dann Neubau — nie umgekehrt.
16. **Python-Konsole unter Windows ist cp1252.** Skripte, die Unicode
    ausgeben, mit `PYTHONIOENCODING=utf-8` starten.
17. **Word per COM hängt auf `G:`.** `Documents.Open` auf einem
    Google-Drive-Pfad blockiert ohne Fehlermeldung; für einen Word-Export
    die docx erst auf `C:` kopieren. Der Kit-Weg ist ohnehin `--pdf`
    (LibreOffice); Word-PDFs nur zur Gegenprobe.
18. **Leerabsatz nach Tabellen kostet eine Zeile.** Im Profil `kanon` ist er
    über `stil.tabellenabstand` (twips, exakte Zeilenhöhe) auf 60 gestellt,
    sonst passt kein einseitiges Blatt; `kompakt` behält die natürliche Höhe,
    weil die CH-09.WAS-Vorlage genau diesen Abstand hat.
19. **`soffice --version` hängt bis zu 100 s**, die eigentliche Konvertierung
    braucht 2 s. `ab_kit.js` prüft deshalb nur die Existenz der Datei und
    konvertiert mit eigenem Profil (`%LOCALAPPDATA%\ab_kit_lo_profil`) und
    `--norestore` — kein Lock-Konflikt mit einem offenen LibreOffice, kein
    Profil auf Google Drive. Erster Lauf auf einem neuen Rechner legt das
    Profil an und dauert einmalig länger.

## Bekannte Einschränkungen

- Das Kit ist bewusst statisch: neuer Elementtyp = Renderer-Erweiterung.
- Eine Kit-Änderung verändert beim Neubau auch alte ABs. Deshalb steht
  `kit_version` in jeder Spec; bei Major-Abweichung bricht der Lauf ab.
- Seitenumbrüche folgen dem Inhalt. Wer ein Blatt auf genau zwei Seiten
  halten will, prüft das PDF und justiert `hoehe`/`zeilen` in der Spec.
- Die docx wird für LibreOffice-Render gebaut und geprüft. Word rendert
  Tabellenhöhen und Tab-Leader minimal anders — SuS-seitig ausschließlich PDF.

## Änderungsprotokoll

- **1.9 (09.09.2026)** — Neuer Asset-Typ `kreislauf` in `ab_assets.py`,
  zwei Commits. **Teil 1:** Stoffkreislauf aus zwei Kästen (`oben`/`unten`)
  und zwei Pfeilen (rechts abwärts, links aufwärts) mit je einem
  Beschriftungskästchen, außen freier Rand (`aussenrand`); Übernahme 1:1 aus
  der Vorstufe `Python_Skripte\CH-09.WAS\kreislauf_gen.py`, das Kit-PNG
  `kreislauf_b6` ist bitgleich zum Skript-PNG (SHA-256 `cea530be…`). Die
  Aufnahmeregel „beim zweiten Bedarf" wurde bewusst übersprungen
  (Entscheidung 09.09.2026). **Teil 2:** Erweiterung auf 2 bis 4 Stationen
  (`stationen`, `pfeile`), Uhrzeigersinn, erste Station oben; 3 Stationen
  als Dreieck, 4 als Rechteck; Kurzform `oben`/`unten`/`rechts`/`links`
  bleibt gültig und rendert bitgleich (Hash geprüft), Mischung beider Formen
  bricht ab. Platzprüfung vor dem Zeichnen mit Abbruch und Seitenangabe
  (Kasten zu breit, Kasten über dem Bildrand, Label breiter als `feld`,
  Leitung zu kurz) — sie gilt auch für die Kurzform: Specs, die unter Teil 1
  sichtbar überlappten (Kastentext breiter als der Leitungsabstand, Label
  breiter als `feld`), brechen jetzt ab statt ein unbrauchbares PNG zu
  liefern; fehlerfreie Specs rendern unverändert. Anlass: CH-09.WAS-B6
  `AB_Wasserauto_GR` (Wasser ⇄ Wasserstoff + Sauerstoff), bis dahin über
  `typ: bilddatei` eingebunden; Ziel des Plurals „Kreisprozesse": Wasser-,
  Kohlenstoff-, Stickstoffkreislauf. Übrige Asset-Typen und `ab_kit.js`
  unverändert; Neubau aller 19 Archiv-Specs liefert bitgleiche PNGs,
  Sidecars und `word/document.xml`, `--check`-Ausgabe bis auf die
  Kit-Versionsnummer unverändert (geprüft 09.09.2026, nach beiden Teilen).
  Testfälle `_build\specs\kreislauf_test.spec.yaml` und
  `kreislauf_fehler_*.spec.yaml`. Specs mit `kit_version: "1.8"` und älter
  (1.x) bauen unverändert (Minor).
- **1.8 (08.09.2026)** — Neuer Dokumenttyp `uebung` (Übungsblatt wie eine
  Arbeit): `punkte` an `aufgabe`/`teilaufgabe`, rechtsbündig gerendert;
  Kasten `afb3_hinweis` vor der ersten AFB-III-Aufgabe; Untertitel-Default
  „Übungsblatt“. `--check` prüft Ü-1 (AFB-Anteile gegen
  `config\afb_richtwert.json` je `zweig` oder `afb_richtwert`, Toleranz
  `afb_toleranz`, Default 5 Pp — am 08.09. nach der Abnahme von 10 auf 5
  korrigiert, `zweig: R` mit 20/60/20 warnt damit), Ü-2 (AFB III freiwillig, Hinweis), Ü-3 (Reihenfolge), Ü-4
  (Punkte), Ü-5 (Fremdelemente) statt A-1…A-5. Lösungen mit `ab_spec` auf eine
  `uebung`-Spec übernehmen `punkte`/`afb` mit dem Zitat und hängen ein
  Bewertungsraster an (`punkteraster`). Unbekannter `dokumenttyp` ist jetzt
  eine Warnung. `ab` und `loesung` zu `ab`-Quellen rendern unverändert (alle
  15 Archiv-Specs geprüft). **Teil B der Übergabe (Default „eine Kopie je
  Seite“) ist nicht gebaut:** die beobachtete Doppelung stammt nicht aus dem
  Kit — `AB_Ablauf_Brennerfuehrerschein_GR` baut seit jeher genau eine Kopie;
  doppelt sind die nicht kit-gebauten Karten `Bedienkarte_Gasbrenner_*` und
  `Fuehrerschein_Gasbrenner` (A5 quer, zwei Stück je A4, Blueprint). Rückfrage
  gestellt, kein Umbau auf Verdacht — Entscheidung 08.09.: Teil B entfällt,
  Kartenlayout ist ein eigenes Thema.
- **1.7 (08.09.2026)** — `--check` erkennt Specs, die mehr als einen Block
  tragen (A-4, Blatt): über alle `seiten` hinweg genau eine `stundenfrage`,
  höchstens ein `sprinter`, höchstens ein `ritual kanon: punkt`; Abweichung =
  Warnung „Blatt trägt N … — ein Blatt, eine Stundenfrage (AB_Qualitaet.md,
  A-4). Blöcke auf getrennte Specs aufteilen.“ Nur `dokumenttyp: ab`; die
  Seitenprüfung A-4/A-5 bleibt unverändert. Läuft nur für Specs mit
  mindestens einer Stundenseite, reine Ablaufpläne bleiben stumm. Anlass:
  `AB_Wasserbestandteile_GR` v2.2 trägt B3 und B4 auf einem Blatt — zwei
  Stundenfragen, zwei Sprinter, zwei Merksatz-Rituale, von 1.6 nicht gemeldet.
  Kein Rendering, kein Spec-Schema betroffen; Specs mit `kit_version: "1.6"`
  bauen unverändert (Minor). R-006 (Blatttitel ≠ Merksatz) bleibt bewusst
  manuelle Prüffrage.
- **1.6 (07.09.2026)** — `teilaufgabe` zitiert wie `aufgabe`: `zitat: true` ohne
  `text`, aber mit `buchstabe`, holt den Wortlaut aus `ab_spec`, gematcht unter
  der vorangehenden `aufgabe` gleicher `nr` (Anker = zuletzt gesehene Aufgabe
  derselben Seite, in Lösung und Blatt gleichermaßen). Gleicher Buchstabe unter
  verschiedenen Nummern bleibt eindeutig; doppelter Buchstabe unter derselben
  Nummer im Blatt = Abbruch, fehlender Anker = Abbruch. Zitierte Teilaufgaben
  rendern grau-kursiv wie das Aufgabenzitat. Anlass: `Loesung_Reihenschaltung`
  nr 3 — nach der Verdrahtung mit 1.5 standen a) und b) wieder als Kopie von
  Hand da, dieselbe Drift eine Ebene tiefer. Bestehende Specs laufen
  unverändert (Minor); ohne `zitat` rendert `teilaufgabe` wie bisher.
- **1.5 (07.09.2026)** — Neues Spec-Feld `ab_spec` für Lösungs-Specs: ein
  `aufgabe`-Element mit `zitat: true` und ohne `text`, aber mit `nr`, holt
  seinen Wortlaut aus der Aufgabe gleicher `nr` der referenzierten AB-Spec
  (Pfad relativ zum Spec-Ordner). AB-Änderungen schlagen damit beim nächsten
  Bau in die Lösung durch, Wortlaut-Drift zwischen Blatt und Erwartungs-
  horizont ist ausgeschlossen. Vorhandener `text` gewinnt. `nr` wird
  zeichengenau als Zeichenkette verglichen (`AB_Messen_GR` führt `nr: "1 + 2"`),
  Aufgaben in `nebeneinander` zählen mit; fehlende Nummer = Abbruch mit der
  Liste der vorhandenen Nummern, doppelte `nr` im AB ebenfalls Abbruch. Läuft
  auch bei `--check`, `bau.ps1` fängt Drift also vor dem Bau ab. Anlass:
  PH-10.SGE-B3/B4 — die Teilung des Blattes am 07.09.2026 kostete drei Runden
  Handnachzug an Zitaten. Geprüft: alle vierzehn Archiv-Specs bauen mit 1.5
  ein zu 1.4 identisches `word/document.xml` (einzige Abweichung ist der
  Ritual-Wortlaut desselben Tages, siehe Eintrag unten). Bestehende Specs mit
  `kit_version: "1.2"` bis `"1.4"` laufen unverändert (Minor).
- **`bau.ps1` (07.09.2026), Kit-Version unverändert 1.4** — Die Ablage in den
  Blockordner hält gesperrte Zieldateien aus. Bisher warf `Copy-Item` unter
  `$ErrorActionPreference = "Stop"` bei einer gesperrten Ziel-PDF (Google Drive
  Desktop, Explorer-Vorschaubereich) einen terminierenden Fehler und beendete
  damit die gesamte `foreach`-Schleife über die Specs — bei einem Aufruf mit
  zwei Specs wurde die zweite nie gebaut, ohne erkennbare Meldung. Jetzt:
  Kopieren mit Wiederholung (`Copy-MitWiederholung`, 10 Versuche im Abstand
  von 700 ms — Sync-Sperren lösen sich meist in wenigen Sekunden), bei
  dauerhafter Sperre Warnung mit Quellpfad in `_build\<Stamm>\` zum
  Kopieren von Hand und ausdrücklichem Hinweis, dass docx und PDF im
  Blockordner auseinanderlaufen können (neue docx neben alter PDF), danach
  weiter mit der nächsten Spec. Ebenfalls entschärft: `Resolve-Path` auf einen
  nicht existierenden Pfad und `Select-String` auf die Spec brachen die
  Schleife bisher genauso hart ab. Am Ende listet der Lauf die Specs auf, die
  nicht vollständig abgelegt wurden; der Exitcode zählt weiter die Probleme.
- **Ritual-Wortlaut (07.09.2026), Kit-Version unverändert 1.4** —
  `ritual_punkt` lautet in den Profilen `kanon` und `kompakt` jetzt
  „… in meinen eigenen Worten zusammen." statt
  „… in meinen eigenen Worten.".
  Reiner Wortlaut, keine Schnittstelle: Specs, Elementtypen und Stilfelder
  bleiben unberührt, bestehende Specs laufen ohne Änderung. Aber: der Neubau
  eines AB mit `ritual kanon: punkt` ändert dessen Ausgabe — docx und PDF im
  Blockordner weichen danach vom bisherigen Stand ab. Zeilenlage geprüft:
  der längere Satz bleibt in beiden Profilen einzeilig (kanon im Kasten
  ca. 290 pt bei ca. 489 pt Satzbreite, kompakt als schlichte Zeile ca. 293 pt
  bei ca. 510 pt).
- **1.4 (06.09.2026)** — Neuer Asset-Typ `schaltbild` in `ab_assets.py`:
  Schaltplan aus deklarativer Beschreibung (Bauteilliste `reihe`, parallele
  `zweige`), 18 Schaltzeichen nach DIN EN 60617, automatische oder explizite
  Seitenzuordnung, Zeichenregeln der Arbeitsblätter fest verdrahtet (rechte
  Winkel, keine Bauteile in den Ecken, Schalter offen). `schaltplan` und
  `stromkreis` bleiben unverändert; Neubau aller zwölf Archiv-Specs liefert
  bitgleiche PNGs (geprüft 06.09.2026). `ab_kit.js` unverändert. Anlass:
  Musterschaltplan PH-08.STK-B6 (Reihenschaltung, zwei Schalter) war mit den
  alten Typen nicht darstellbar. Testfälle `_build\specs\schaltbild_test.spec.yaml`.
  Bestehende Specs mit `kit_version: "1.2"`/`"1.3"` laufen unverändert (Minor).
- **`bau.ps1` (06.09.2026), Kit-Version unverändert 1.3** — Windows-Bauskript:
  Check, Assets, Bau mit PDF für mehrere Specs in einem Aufruf, docx + pdf
  werden neben die Spec in den Blockordner kopiert; Stamm aus `ausgabe`,
  Abbruch je Spec bei fehlgeschlagenem Check, `-NurCheck`. Ersetzt das
  Kopieren von Hand aus `_build\`.
- **Repo-Umzug (06.09.2026), Kit-Version unverändert 1.3** — Der Kit lebt
  jetzt im öffentlichen Repo `https://github.com/mrhey111/ab-kit` (MIT);
  Arbeitskopie auf Windows ist der Klon `C:\dev\ab_kit\`, der alte Ordner auf
  `G:` ist ausgemustert. Neu: `.gitignore` (schließt `_build\`, Specs, Bilder,
  docx, pdf aus — das Repo ist öffentlich, Specs sind Unterrichtsinhalt),
  `.gitattributes` (LF), `LICENSE`, Abschnitt „Nutzung im Container",
  `package.json` auf 1.3.0. Pfade in Installation, Ablauf und
  `setup_windows.ps1` nachgezogen. Claude-Container klonen das Repo selbst
  und bauen dort; die Upload-Schleife über Fabian entfällt.

- **1.3 (06.09.2026)** — Neuer Asset-Typ `bilddatei` in `ab_assets.py`: bindet
  eine vorhandene Bilddatei ein, mit Zuschnitt über Anteile, Graustufen,
  Autokontrast und optionalem Rahmen; relative Pfade lösen gegen den
  Spec-Ordner auf (`SPEC_DIR`). `ab_kit.js` unverändert — Einbindung wie bisher
  über `bild: {asset: …}` bzw. `links_bild`/`rechts_bild`. Anlass: Fotos in
  PH-08.STK-B5/B6. Bestehende Specs mit `kit_version: "1.2"` laufen unverändert
  (Minor, nur Hinweis); Retrofit träge beim nächsten Anfassen.

- **1.2 (03.09.2026)** — Bauplan-Check: `ab_kit.js` prüft jedes AB gegen
  `AB_Qualitaet.md` Teil A (A-1 bis A-5), neue optionale Felder `afb` und
  `bezug` an `aufgabe`, optionaler Spec-Block `bauplan: {scaffold: false}`
  als einziger Opt-out für den Scaffold, neuer Schalter `--check`. Rendering
  unverändert. Alle acht Archiv-Specs auf `kit_version: "1.2"` gesetzt, die
  vier ABs mit `afb`/`bezug` je Aufgabe versehen (Ausgabe unverändert, kein
  Neubau nötig). Testfall `_build\specs\bauplan_test.spec.yaml`.
- **1.1 (03.09.2026)** — WH-Bausteine aus `Layout_wh.js` überführt: neue
  Elemente `namenszeile`, `teilaufgabe`, `ankreuzen`, `zitat`; `lueckenzeile`
  mit reinen Tabstops und `zusatzlinien`; `nebeneinander` mit `luecke`/`rahmen`;
  `sprinter` mit `linien`/`emoji`/`sperrung`; `ritual` mit `zusatz_inline`;
  `kopfzeile` mit `zeile_oben`; Stil-Tokens `stundenfrage_*`, `loesung_einzug`,
  `marker`; Asset `stromkreis`, `scaffold.rahmen`. Specs PH-10.SGE-WH1/WH2
  (AB + Lösung). Alle bestehenden Specs auf `kit_version: "1.1"` gesetzt —
  Ausgabe unverändert.
- **1.0 (03.09.2026)** — Erstfassung. Extrahiert aus CH-09.WAS (build_ab.js,
  build_loesung.js, scaffold_gen.py, diagramm_gen.py), PH-10.SGE
  (build_loesung_widerstand.js, AB_Widerstand_GR_Inhalt.md) und
  `_gemeinsam\Layout_wh.js`. Vier Profile, 24 Elementtypen, 5 Asset-Typen.
  Referenz-Specs: `AB_Wasserbestandteile_GR`, `Loesung_Wasserbestandteile`,
  `AB_Widerstand_GR`, `Loesung_Widerstand`.
