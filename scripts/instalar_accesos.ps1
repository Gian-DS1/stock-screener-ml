# Crea los accesos directos del Stock Screener en el escritorio.
# Ejecutar una vez:  powershell -ExecutionPolicy Bypass -File scripts\instalar_accesos.ps1
$scripts = $PSScriptRoot
$desktop = [Environment]::GetFolderPath('Desktop')
$icon = Join-Path $scripts 'stock.ico'
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

New-Shortcut 'Stock Screener' (Join-Path $scripts 'iniciar.vbs') 'Abrir el dashboard del Stock Screener (local)'
New-Shortcut 'Detener Stock Screener' (Join-Path $scripts 'detener.vbs') 'Detener el backend del Stock Screener'

Write-Host "Accesos directos creados en el escritorio: 'Stock Screener' y 'Detener Stock Screener'."
