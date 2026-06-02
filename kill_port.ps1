$pids = @(12172,21608,27620,26968)
foreach ($p in $pids) {
    try {
        $proc = Get-Process -Id $p -ErrorAction Stop
        $proc | Stop-Process -Force -ErrorAction Continue
        Write-Output "killed $p"
    } catch {
        Write-Output "failed $p or not found"
    }
}
Start-Sleep 2
netstat -ano | Select-String ':8007 ' | ForEach-Object { Write-Output $_ }