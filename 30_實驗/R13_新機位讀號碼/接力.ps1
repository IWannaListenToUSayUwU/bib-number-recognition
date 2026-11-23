# R13 通用接力：等前一個實驗跑完（score.json＋最後一段的 DONE.txt），再跑下一個 bat。
param([string]$WaitDir, [string]$LastClip, [string]$Bat)
while (-not ((Test-Path "$WaitDir\score.json") -and (Test-Path "$WaitDir\$LastClip\DONE.txt"))) { Start-Sleep -Seconds 30 }
"previous done $(Get-Date -Format HH:mm:ss)"
cmd /c "`"$Bat`" < nul"
"finished $(Get-Date -Format HH:mm:ss)"
