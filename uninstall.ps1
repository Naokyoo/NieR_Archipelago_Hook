$destDll = "C:\Program Files (x86)\Steam\steamapps\common\NieRAutomata\dinput8.dll"

if (Test-Path $destDll) {
    Remove-Item $destDll -Force
    Write-Host "dinput8.dll removed from NieR: Automata folder." -ForegroundColor Green
} else {
    Write-Host "No dinput8.dll found in NieR: Automata folder." -ForegroundColor Yellow
}
