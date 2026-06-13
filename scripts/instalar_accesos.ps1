# Crea los accesos directos del Sniper Screener en el escritorio.
# Ejecutar una vez:  powershell -ExecutionPolicy Bypass -File scripts\instalar_accesos.ps1
$scripts = $PSScriptRoot
$desktop = [Environment]::GetFolderPath('Desktop')
$icon = Join-Path $scripts 'sniper.ico'
$ws = New-Object -ComObject WScript.Shell

function New-Shortcut($name, $target, $desc) {
    $lnk = $ws.CreateShortcut((Join-Path $desktop "$name.lnk"))
    $lnk.TargetPath = 'wscript.exe'
    $lnk.Arguments = '"' + $target + '"'
    $lnk.WorkingDirectory = $scripts
    $lnk.Description = $desc
    if (Test-Path $icon) { $lnk.IconLocation = $icon }
    $lnk.Save()
}

New-Shortcut 'Sniper Screener' (Join-Path $scripts 'iniciar.vbs') 'Abrir el dashboard del Sniper Screener (local)'
New-Shortcut 'Detener Sniper Screener' (Join-Path $scripts 'detener.vbs') 'Detener el backend del Sniper Screener'

Write-Host "Accesos directos creados en el escritorio: 'Sniper Screener' y 'Detener Sniper Screener'."
