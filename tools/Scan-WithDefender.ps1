$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
try {
    $status = Get-MpComputerStatus
    if (-not $status.AntivirusEnabled) {
        Write-Host 'Microsoft Defender nie jest aktywnym antywirusem. Uzyj skanera swojej ochrony antywirusowej.'
        exit 2
    }
    Write-Host "Zlecam skan folderu: $projectRoot"
    Start-MpScan -ScanType CustomScan -ScanPath $projectRoot
    Write-Host 'Zlecono skan. Sprawdz wynik w Zabezpieczenia Windows > Ochrona przed wirusami > Historia ochrony.'
    Write-Host 'Ten skrypt nie wylacza ochrony, nie dodaje wyjatkow i nie zmienia zasad systemu.'
} catch {
    Write-Host 'Nie udalo sie potwierdzic skanowania. Kliknij folder prawym przyciskiem i wybierz skanowanie swoim antywirusem.'
    exit 2
}
