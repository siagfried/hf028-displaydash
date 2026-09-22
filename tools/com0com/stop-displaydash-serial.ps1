param([string]$Router='100.105.214.93')
$ErrorActionPreference='Stop'
$exe=Join-Path $PSScriptRoot 'hub4com.exe'
Get-CimInstance Win32_Process -Filter "Name='hub4com.exe'" | Where-Object { $_.ExecutablePath -eq $exe } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
& ssh "root@$Router" '/usr/bin/displaydash-serial-bridge stop'
if ($LASTEXITCODE -ne 0) { throw 'Local bridge stopped; remote restore failed. Run displaydash-serial-bridge stop on the router.' }
