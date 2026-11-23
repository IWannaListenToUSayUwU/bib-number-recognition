@echo off
chcp 65001 >nul
rem R11 過線標註工具：點兩下開啟，瀏覽器會自動打開 http://localhost:8765
rem 標註會自動存在 標註\annot_<片段>.json。用完直接關掉這個黑色視窗即可。
rem 注意：如果 Claude 那邊已經開著同一個工具（同一個 8765 埠），這裡會開不起來，用那邊的就好。
cd /d "%~dp0..\.."
start "" http://localhost:8765
python "30_實驗\R11_過線正確答案\r11_tool.py"
pause
