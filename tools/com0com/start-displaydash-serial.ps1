param([string]$Router='100.105.214.93', [string]$BridgePort='CNCB1', [int]$TcpPort=2000)
$ErrorActionPreference = "Stop"
$hub = Join-Path $PSScriptRoot "hub4com.exe"
if (-not (Test-Path $hub)) { throw "hub4com.exe not found" }
$existing=Get-CimInstance Win32_Process -Filter "Name='hub4com.exe'" | Where-Object { $_.ExecutablePath -eq $hub }
if ($existing) { throw 'Bridge already running. Stop it before starting another.' }
$bridgeArgs=@('--baud=115200','--octs=off',('\\.\'+$BridgePort),'--use-driver=tcp','--reconnect=1000','--write-limit=65536',('*{0}:{1}' -f $Router,$TcpPort))
Start-Process -FilePath $hub -ArgumentList $bridgeArgs -WindowStyle Hidden
Write-Host "Bridge started: $BridgePort -> ${Router}:$TcpPort. Start the router bridge first."
