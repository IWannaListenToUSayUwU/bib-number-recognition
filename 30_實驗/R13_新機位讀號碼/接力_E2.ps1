# R13 接力：等調整集基準（v2.2）跑完，自動接著跑 E2（GPU 一次只跑一個實驗，避免互搶 CPU）
$base = "Z:\雲科專題\30_實驗\R13_新機位讀號碼\out\FROZEN_CONFIG_v2_2"
while (-not ((Test-Path "$base\score.json") -and (Test-Path "$base\tpe2t_5700\DONE.txt"))) { Start-Sleep -Seconds 30 }
"baseline done $(Get-Date -Format HH:mm:ss)"
cmd /c '"Z:\雲科專題\30_實驗\R13_新機位讀號碼\跑E2.bat" < nul'
"E2 finished $(Get-Date -Format HH:mm:ss)"
