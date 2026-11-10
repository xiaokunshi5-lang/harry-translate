$taskRoot = $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskServer = Join-Path $taskRoot 'server.py'
$taskHud = Join-Path $taskRoot 'float_app.py'
Get-CimInstance Win32_Process -Filter "name = 'python.exe'" | Where-Object {
    $_.ExecutablePath -eq $taskPython -and
    ($_.CommandLine.Contains($taskServer) -or $_.CommandLine.Contains($taskHud))
} | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
Write-Output 'Harry Translate stopped.'
