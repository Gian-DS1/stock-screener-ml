# Registra la tarea diaria del pipeline en el Programador de tareas de Windows.
# Ejecutar como administrador:  powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
param(
    [string]$At = "18:30",   # hora local, tras el cierre de NYSE (16:00 ET)
    [string]$TaskName = "SniperScreener Daily"
)

$backend = Join-Path (Split-Path $PSScriptRoot -Parent) "backend"
$uv = (Get-Command uv).Source

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -Command `"Set-Location '$backend'; & '$uv' run python -m screener.cli run-daily`""

$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force
Write-Host "Tarea '$TaskName' registrada: corre a diario a las $At (se recupera si el PC estaba apagado)."
