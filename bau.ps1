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

    Gesperrte Zieldatei: Google Drive Desktop und der Explorer-Vorschaubereich
    halten die abgelegte PDF zeitweise offen. Die Ablage wiederholt den Kopier-
    versuch deshalb (KopieVersuche / KopiePauseMs) und laeuft bei dauerhafter
    Sperre mit einer Warnung weiter zur naechsten Spec - ein Abbruch der
    Schleife wuerde die restlichen Specs stillschweigend ungebaut lassen.
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
$unvollstaendig = @()

# Sperren durch Drive-Sync loesen sich meist in wenigen Sekunden.
$KopieVersuche = 10
$KopiePauseMs  = 700

# Kopiert mit Wiederholung. Rueckgabe: $null bei Erfolg, sonst die Meldung des
# letzten Fehlversuchs. Schreibt selbst nichts auf die Konsole.
function Copy-MitWiederholung {
    param(
        [Parameter(Mandatory = $true)][string]$Quelle,
        [Parameter(Mandatory = $true)][string]$Ziel,
        [int]$Versuche = 10,
        [int]$PauseMs = 700
    )
    $meldung = $null
    for ($i = 1; $i -le $Versuche; $i++) {
        try {
            Copy-Item -LiteralPath $Quelle -Destination $Ziel -Force -ErrorAction Stop
            return $null
        }
        catch {
            $meldung = $_.Exception.Message
            if ($i -lt $Versuche) { Start-Sleep -Milliseconds $PauseMs }
        }
    }
    return $meldung
}

foreach ($s in $Spec) {
    # Resolve-Path bricht bei nicht existierendem Pfad terminierend ab und
    # wuerde die ganze Schleife beenden - deshalb abgefangen.
    $pfad = $null
    try { $pfad = (Resolve-Path -LiteralPath $s -ErrorAction Stop).Path }
    catch { $pfad = $null }
    if (-not $pfad) {
        Write-Warning "Spec nicht gefunden, uebersprungen: $s"
        $fehler++
        $unvollstaendig += "$s (Spec nicht gefunden)"
        continue
    }
    if ($pfad -notlike "*.spec.yaml") {
        Write-Warning "Keine Spec-Datei, uebersprungen: $pfad"
        $fehler++
        $unvollstaendig += "$pfad (keine Spec-Datei)"
        continue
    }
    # Stamm: Feld `ausgabe` der Spec (Dateiname der docx), sonst Dateistamm.
    $stamm = $null
    $zeile = $null
    try {
        $zeile = Select-String -LiteralPath $pfad -Pattern '^ausgabe:\s*(.+?)\s*$' -ErrorAction Stop |
                 Select-Object -First 1
    }
    catch { $zeile = $null }   # nicht lesbar: unten faellt der Dateistamm ein
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
        $unvollstaendig += "$stamm (Check fehlgeschlagen)"
        continue
    }
    if ($NurCheck) { continue }

    & python (Join-Path $Kit "ab_assets.py") $pfad
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "   Assets fehlgeschlagen (Exit $LASTEXITCODE), kein Bau: $pfad"
        $fehler++
        $unvollstaendig += "$stamm (Assets fehlgeschlagen)"
        continue
    }
    & node (Join-Path $Kit "ab_kit.js") $pfad --pdf
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "   Renderer fehlgeschlagen (Exit $LASTEXITCODE): $pfad"
        $fehler++
        $unvollstaendig += "$stamm (Renderer fehlgeschlagen)"
        continue
    }

    # Ablage. Jede Datei einzeln: eine gesperrte PDF darf weder die docx noch
    # die naechste Spec verhindern.
    $ablageLuecke = @()
    foreach ($ext in @("docx", "pdf")) {
        $quelle = Join-Path $build "$stamm.$ext"
        if (-not (Test-Path -LiteralPath $quelle)) {
            Write-Warning "   $stamm.$ext nicht gefunden in $build"
            $fehler++
            $ablageLuecke += $ext
            continue
        }
        $meldung = Copy-MitWiederholung -Quelle $quelle -Ziel $ziel `
                       -Versuche $KopieVersuche -PauseMs $KopiePauseMs
        if (-not $meldung) {
            Write-Host "   abgelegt: $ziel\$stamm.$ext" -ForegroundColor Green
        }
        else {
            Write-Warning "   $stamm.$ext nicht abgelegt - Ziel nach $KopieVersuche Versuchen gesperrt:"
            Write-Warning "     $ziel\$stamm.$ext"
            Write-Warning "     $meldung"
            Write-Warning "     ACHTUNG: docx und PDF im Blockordner koennen jetzt auseinanderlaufen"
            Write-Warning "     (neue docx neben alter PDF). Von Hand kopieren aus:"
            Write-Warning "     $quelle"
            $fehler++
            $ablageLuecke += $ext
        }
    }
    if ($ablageLuecke.Count -gt 0) {
        $unvollstaendig += "$stamm (nicht abgelegt: " + ($ablageLuecke -join ", ") + ")"
    }
}
Write-Host ""
if ($unvollstaendig.Count -gt 0) {
    Write-Host "Nicht vollstaendig abgelegt:" -ForegroundColor Yellow
    foreach ($u in $unvollstaendig) { Write-Host "  - $u" -ForegroundColor Yellow }
}
if ($fehler -gt 0) { Write-Host "$fehler Problem(e), siehe Warnungen oben." -ForegroundColor Yellow }
exit $fehler
