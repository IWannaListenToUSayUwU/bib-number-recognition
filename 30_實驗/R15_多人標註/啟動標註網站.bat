@echo off
chcp 65001 >nul
rem R15 多人標註網站：點兩下啟動，其他人用瀏覽器開 http://100.65.210.69:8780 （要在你的 Tailscale 網路裡）
rem 只綁 Tailscale 位址，校網連不到。關掉這個黑色視窗＝網站停止。標註存在 30_實驗\R15_多人標註\標註\<名字>\
rem 用 C:\Python313\python.exe：防火牆已允許它在「私人網路」（Tailscale）接受連線，不用改防火牆。
cd /d "%~dp0..\.."
start "" http://100.65.210.69:8780
"C:\Python313\python.exe" "30_實驗\R15_多人標註\r15_server.py" --host 100.65.210.69 --port 8780
pause
