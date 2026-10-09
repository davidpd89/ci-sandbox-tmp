# Control de las rondas (08/10/2026). Lo usan INICIAR_RONDAS.bat y PARAR_RONDAS.bat.
#   -Accion iniciar : reactiva las tareas RRSS_* que pauso PARAR_RONDAS y quita la senal de parada.
#                     Si ya hay una cola en marcha deja la senal «recargar»: cada cadena termina la ronda que esta haciendo,
#                     no lanza otra, y la cola (y el trabajador de ChatGPT) se relanzan solos con el codigo nuevo siguiendo donde iban.
#                     Sale con 10 si ha pedido recarga (el .bat no lanza otra cola) y con 0 si no habia cola (el .bat la arranca).
#   -Accion parar   : para TODO al momento: senal de parada, tareas RRSS_* en curso detenidas, tareas activas pausadas
#                     (se apuntan para que INICIAR las reactive) y procesos de Python del repo cerrados.
#                     NO toca el Edge dedicado (CDP 9223) ni los servidores MCP; los bloqueos de Edge y movil se liberan solos.
param([Parameter(Mandatory = $true)][ValidateSet('iniciar', 'parar')][string]$Accion)

$Root = 'C:\GIT\RRSS_AutoraDemo'
$Op = Join-Path $Root '00_OPERATIVO'
$Paused = Join-Path $Op 'tareas_pausadas.txt'
$StopFlag = Join-Path $Op 'cola_parar.flag'
$ReloadFlag = Join-Path $Op 'cola_recargar.flag'
# Scripts del repo: «tools\x.py» relativo (las tareas hacen cd al repo) o con la ruta completa del repo. Asi no se tocan otros Python (MCP, http.server).
$RepoScript = '(RRSS_AutoraDemo[\\/]tools|(^|[\s"])tools)[\\/][\w]+\.py'

function Get-RepoPython {
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
        Where-Object { $_.CommandLine -match $RepoScript }
}

if ($Accion -eq 'parar') {
    Set-Content -Path $StopFlag -Value (Get-Date -Format 's') -Encoding UTF8
    $tasks = Get-ScheduledTask -TaskName 'RRSS_*' -ErrorAction SilentlyContinue
    $running = $tasks | Where-Object State -eq 'Running'
    foreach ($t in $running) { Stop-ScheduledTask -TaskName $t.TaskName -ErrorAction SilentlyContinue }
    $enabled = $tasks | Where-Object { $_.State -ne 'Disabled' }
    if ($enabled) {
        $names = @($enabled | ForEach-Object TaskName)
        $previous = @()
        if (Test-Path $Paused) { $previous = @(Get-Content $Paused | Where-Object { $_ }) }
        ($previous + $names | Sort-Object -Unique) | Set-Content -Path $Paused -Encoding UTF8
        foreach ($n in $names) { Disable-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue | Out-Null }
    }
    $procs = @(Get-RepoPython)
    foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    # No quitar lock de una cadena cuyo proceso aún no ha terminado.
    foreach ($p in $procs) { Wait-Process -Id $p.ProcessId -Timeout 10 -ErrorAction SilentlyContinue }
    $survivors = @(Get-RepoPython)
    if ($survivors.Count -gt 0) {
        Write-Error ("Siguen vivos {0} procesos del repositorio; NO limpiar locks" -f $survivors.Count)
        exit 2
    }
    Remove-Item (Join-Path $Op '_cola_respuestas\worker.lock') -ErrorAction SilentlyContinue
    Get-ChildItem $Op -Filter 'cola_rondas_*.lock' -ErrorAction SilentlyContinue | Remove-Item -ErrorAction SilentlyContinue
    # PARAR: después de detener procesos del repo, borrar también marcadores de
    # recuperación de locks; no eliminar ficheros de otros proyectos.
    Get-ChildItem $Op -Filter 'cola_rondas_*.lock.reclaim' -ErrorAction SilentlyContinue | Remove-Item -ErrorAction SilentlyContinue
    Write-Host ("Paradas {0} tareas en curso, pausadas {1} tareas programadas y cerrados {2} procesos de Python del repo." -f @($running).Count, @($enabled).Count, $procs.Count)
    Write-Host 'Las tareas pausadas se reactivan con INICIAR_RONDAS.bat. El Edge dedicado no se ha tocado.'
    exit 0
}

# iniciar
Remove-Item $StopFlag -ErrorAction SilentlyContinue
if (Test-Path $Paused) {
    $names = @(Get-Content $Paused | Where-Object { $_ })
    foreach ($n in $names) { Enable-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue | Out-Null }
    Remove-Item $Paused -ErrorAction SilentlyContinue
    Write-Host ("Reactivadas {0} tareas programadas que se pausaron con PARAR_RONDAS." -f $names.Count)
}
$queue = @(Get-RepoPython | Where-Object { $_.CommandLine -match 'round_queue\.py' })
if ($queue.Count -gt 0) {
    Set-Content -Path $ReloadFlag -Value (Get-Date -Format 's') -Encoding UTF8
    Write-Host 'Ya hay una cola de rondas en marcha. Se ha pedido RECARGAR:'
    Write-Host '  las rondas que estan en curso terminan normalmente y las siguientes arrancan con el codigo nuevo,'
    Write-Host '  siguiendo donde iba la cola (lo hecho hoy se lee de 00_OPERATIVO\tiempos_rondas.csv).'
    exit 10
}
exit 0
