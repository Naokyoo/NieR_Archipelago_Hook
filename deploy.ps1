$gameDir = "C:\Program Files (x86)\Steam\steamapps\common\NieRAutomata"
$sourceDll = Join-Path $PSScriptRoot "dinput8.dll"
$destDll = Join-Path $gameDir "dinput8.dll"

Write-Host "=== Deploying Archipelago Hook DLL to NieR: Automata ===" -ForegroundColor Cyan

# Run build.bat directly
Set-Location $PSScriptRoot
# Full path: cmd.exe can't resolve a relative path when the folder name has accents (Archipêlago)
& cmd.exe /c "`"$(Join-Path $PSScriptRoot 'build.bat')`""

if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed with exit code $LASTEXITCODE"
    exit 1
}

$proc = Get-Process -Name 'NieRAutomata' -ErrorAction SilentlyContinue
if ($proc) {
    Write-Host "NieRAutomata is currently running. Waiting for game to close..." -ForegroundColor Yellow
    $proc.WaitForExit()
}

Write-Host "Copying dinput8.dll & nier_archipelago_bridge.py into game folder..." -ForegroundColor Yellow
Copy-Item -Path $sourceDll -Destination $destDll -Force
Copy-Item -Path (Join-Path $PSScriptRoot "nier_archipelago_bridge.py") -Destination (Join-Path $gameDir "nier_archipelago_bridge.py") -Force
Copy-Item -Path (Join-Path $PSScriptRoot "ap_definitions.json") -Destination (Join-Path $gameDir "ap_definitions.json") -Force
Copy-Item -Path (Join-Path $PSScriptRoot "known_chests.json") -Destination (Join-Path $gameDir "known_chests.json") -Force

Write-Host "Deployment successful!" -ForegroundColor Green
Write-Host "Hook installed at: $destDll" -ForegroundColor Green

