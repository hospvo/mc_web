Get-Process | ForEach-Object {
    try {
        $_.ProcessorAffinity = 49152
    } catch {
        Write-Host "Nelze nastavit afinitu pro proces $($_.Name)"
    }
}