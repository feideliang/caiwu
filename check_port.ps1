$targets = @(12172, 21608, 27620, 26968)
foreach ($id in $targets) {
    $proc = Get-Process -Id $id -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Output ("PID " + $id + ": " + $proc.ProcessName)
        Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
        Write-Output ("  -> killed")
    } else {
        Write-Output ("PID " + $id + ": not found")
    }
}
Start-Sleep 1
Write-Output "---"
$list = netstat -ano | Select-String ':8007 '
if (-not $list) { Write-Output "port 8007 is free" } else { $list }