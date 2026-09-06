# setup_windows.ps1 - AB-Kit auf einem weiteren Windows-Rechner einrichten
# ---------------------------------------------------------------------------
# Aufruf (PowerShell, kein Admin noetig - LibreOffice fragt per UAC nach):
#   git clone https://github.com/mrhey111/ab-kit C:\dev\ab_kit
#   powershell -ExecutionPolicy Bypass -File "C:\dev\ab_kit\setup_windows.ps1"
#
# Prueft und installiert: LibreOffice (winget), docx + yaml (npm global),
# pillow + pyyaml (pip). Danach ein Funktionstest mit AB_Messen_GR.
# Voraussetzungen, die das Skript nur meldet: node >= 22, Python >= 3.11,
# winget, optional pdftoppm (TeX Live) fuer die Sichtpruefung.
# pip wird als Modul (`python -m pip`) geprueft und noetigenfalls per
# ensurepip nachgeruestet - eine pip.exe im PATH gibt es nicht ueberall.
# Datei bewusst reines ASCII: Windows PowerShell 5.1 liest UTF-8 ohne BOM
# als ANSI und stolpert ueber Umlaute und Gedankenstriche.

$ErrorActionPreference = "Continue"
$kit = "C:\dev\ab_kit"
$ok = $true

function Zeile($t) { Write-Host ""; Write-Host "== $t" -ForegroundColor Cyan }

Zeile "Voraussetzungen"
$fehlend = @()
foreach ($cmd in @("node", "npm", "python", "winget")) {
  $c = Get-Command $cmd -ErrorAction SilentlyContinue
  if ($c) { Write-Host "  $cmd : $($c.Source)" } else { Write-Host "  $cmd : FEHLT" -ForegroundColor Red; $fehlend += $cmd }
}
if ($fehlend.Count -gt 0) {
  Write-Host ""
  Write-Host "Fehlt: $($fehlend -join ', '). Bitte zuerst installieren (node >= 22, Python >= 3.11), dann erneut ausfuehren." -ForegroundColor Red
  exit 1
}
# pip nur als Modul pruefen: unter AppData installiertes Python legt keine
# pip.exe in den PATH, `python -m pip` funktioniert trotzdem.
python -m pip --version > $null 2>&1
if ($LASTEXITCODE -eq 0) {
  Write-Host "  pip : python -m pip"
} else {
  Write-Host "  pip : fehlt - wird per ensurepip nachgeruestet ..." -ForegroundColor Yellow
  python -m ensurepip --upgrade
  python -m pip --version > $null 2>&1
  if ($LASTEXITCODE -ne 0) { Write-Host "  pip liess sich nicht einrichten." -ForegroundColor Red; exit 1 }
}
Write-Host "  node $(node --version) / $(python --version)"
$pdftoppm = Get-Command pdftoppm -ErrorAction SilentlyContinue
if ($pdftoppm) { Write-Host "  pdftoppm: $($pdftoppm.Source)" } else { Write-Host "  pdftoppm: fehlt (nur fuer Sichtpruefung; TeX Live oder Poppler)" -ForegroundColor Yellow }

Zeile "LibreOffice"
$soffice = "C:\Program Files\LibreOffice\program\soffice.exe"
if (Test-Path $soffice) {
  Write-Host "  vorhanden: $soffice"
} else {
  Write-Host "  wird installiert (winget, UAC-Abfrage bestaetigen) ..."
  winget install --id TheDocumentFoundation.LibreOffice --exact --accept-package-agreements --accept-source-agreements
  if (Test-Path $soffice) { Write-Host "  installiert." } else { Write-Host "  NICHT gefunden - Installation pruefen." -ForegroundColor Red; $ok = $false }
}

Zeile "npm-Module docx + yaml (global; lokales npm install im Klon auf C: geht ebenfalls)"
$root = Join-Path $env:APPDATA "npm\node_modules"
$fehlt = @("docx", "yaml") | Where-Object { -not (Test-Path (Join-Path $root $_)) }
if ($fehlt.Count -eq 0) {
  Write-Host "  vorhanden in $root"
} else {
  npm install -g docx yaml --no-audit --no-fund
  if ($LASTEXITCODE -ne 0) { $ok = $false }
}

Zeile "Python-Pakete pillow + pyyaml"
python -c "import PIL, yaml" 2>$null
if ($LASTEXITCODE -eq 0) {
  Write-Host "  vorhanden"
} else {
  python -m pip install pillow pyyaml
  if ($LASTEXITCODE -ne 0) { $ok = $false }
}

Zeile "Funktionstest"
$spec = "G:\Meine Ablage\Zettlr_Unterrichtsarchiv\PH\PH-10\PH-10.SGE\PH-10.SGE-WH2\AB_Messen_GR.spec.yaml"
Set-Location $kit
python ab_assets.py $spec
node ab_kit.js $spec --pdf
$pdf = Join-Path $kit "_build\AB_Messen_GR\AB_Messen_GR.pdf"
if (Test-Path $pdf) { Write-Host "  OK - $pdf" -ForegroundColor Green } else { Write-Host "  PDF fehlt - Ausgabe oben pruefen." -ForegroundColor Red; $ok = $false }

Write-Host ""
if ($ok) { Write-Host "Einrichtung abgeschlossen." -ForegroundColor Green } else { Write-Host "Einrichtung unvollstaendig, siehe rote Zeilen." -ForegroundColor Red }
