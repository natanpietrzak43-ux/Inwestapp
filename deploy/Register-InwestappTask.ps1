param([string]$RepositoryPath=(Split-Path $PSScriptRoot -Parent))
$ErrorActionPreference='Stop'
$repository=(Resolve-Path $RepositoryPath).Path
$pythonExe=(& py -3 -c "import sys; print(sys.executable)").Trim()
if (-not (Test-Path $pythonExe)) { throw 'Nie znaleziono interpretera Python.' }
$runner=Join-Path $repository 'tools\run_service.py'
$action=New-ScheduledTaskAction -Execute $pythonExe -Argument ('"'+$runner+'" --port 8000') -WorkingDirectory $repository
$trigger=New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$settings=New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -Force -TaskName 'Inwestapp Demo' -Action $action -Trigger $trigger -Settings $settings -Description 'Prywatny bot papierowy/OKX Demo; komputer musi pozostac wlaczony.'
$watchdog=Join-Path $repository 'tools\watchdog.py'
$watchdogAction=New-ScheduledTaskAction -Execute $pythonExe -Argument ('"'+$watchdog+'"') -WorkingDirectory $repository
Register-ScheduledTask -Force -TaskName 'Inwestapp Watchdog' -Action $watchdogAction -Trigger $trigger -Settings $settings -Description 'Niezalezny nadzor aktualnosci cykli Inwestapp.'
