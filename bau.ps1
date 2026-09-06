<#
    bau.ps1 - AB-Kit: bauen und direkt im Blockordner ablegen
    Nimmt eine oder mehrere Spec-Dateien, laesst Assets und Renderer laufen und
    kopiert docx + pdf anschliessend neben die Spec - also in den Blockordner.
    Zwischenprodukte (PNG, JSON) bleiben in _build\<Stamm>\ des Kits.

    Aufruf:  & "C:\dev\ab_kit\bau.ps1" $B5 $B6
             -NurCheck   nur der Spec- und Bauplan-Check, kein Bau

    Der Ausgabestamm wird aus dem Spec-Feld `ausgabe` gelesen (dort steht der
    docx-Name); fehlt das Feld, gilt der Dateistamm der Spec. Beides ist im
    Archiv identisch (Spec_Konvention: <Stamm>.spec.yaml -> <Stamm>.docx).
    Schlaegt der Check fehl (Exitcode != 0), wird die Spec uebersprungen.
    Datei bewusst reines ASCII: Windows PowerShell 5.1 liest UTF-8 ohne BOM
    als ANSI und stolpert ueber Umlaute.
#>
param(
    [Parameter(Mandatory = $true, Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$Spec,
    [switch]$NurCheck
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$Kit = Split-Path -Parent $MyInvocation.MyCommand.Path
$fehler = 0

foreach ($s in $Spec) {
    $pfad = (Resolve-Path -LiteralPath $s).Path
    if ($pfad -notlike "*.spec.yaml") {
        Write-Warning "Keine Spec-Datei, uebersprungen: $pfad"
        $fehler++
        continue
    }
    # Stamm: Feld `ausgabe` der Spec (Dateiname der docx), sonst Dateistamm.
    $stamm = $null
    $zeile = Select-String -LiteralPath $pfad -Pattern '^ausgabe:\s*(.+?)\s*$' | Select-Object -First 1
    if ($zeile) {
        $wert = $zeile.Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'")
        $stamm = [IO.Path]::GetFileNameWithoutExtension($wert)
    }
    if (-not $stamm) {
        # zweimal die Endung abschneiden: .yaml, dann .spec
        $stamm = [IO.Path]::GetFileNameWithoutExtension(
                     [IO.Path]::GetFileNameWithoutExtension($pfad))
    }
    $ziel  = Split-Path -Parent $pfad
    $build = Join-Path $Kit "_build\$stamm"

    Write-Host ""
    Write-Host "== $stamm" -ForegroundColor Cyan

    & node (Join-Path $Kit "ab_kit.js") $pfad --check
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "   Check fehlgeschlagen (Exit $LASTEXITCODE), kein Bau: $pfad"
        $fehler++
        continue
    }
    if ($NurCheck) { continue }

    & python (Join-Path $Kit "ab_assets.py") $pfad
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "   Assets fehlgeschlagen (Exit $LASTEXITCODE), kein Bau: $pfad"
        $fehler++
        continue
    }
    & node (Join-Path $Kit "ab_kit.js") $pfad --pdf
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "   Renderer fehlgeschlagen (Exit $LASTEXITCODE): $pfad"
        $fehler++
        continue
    }

    foreach ($ext in @("docx", "pdf")) {
        $quelle = Join-Path $build "$stamm.$ext"
        if (Test-Path -LiteralPath $quelle) {
            Copy-Item -LiteralPath $quelle -Destination $ziel -Force
            Write-Host "   abgelegt: $ziel\$stamm.$ext" -ForegroundColor Green
        }
        else {
            Write-Warning "   $stamm.$ext nicht gefunden in $build"
            $fehler++
        }
    }
}
Write-Host ""
if ($fehler -gt 0) { Write-Host "$fehler Problem(e), siehe Warnungen oben." -ForegroundColor Yellow }
exit $fehler
