@echo off
chcp 65001 >nul
rem R14 三層設定的端對端驗證（GPU，約 50 分鐘）：
rem  (1) GLOBAL_v2_2 跑 C 段：raw.jsonl 要和 v2.2 逐位元相同（確認 extract8 和新版正式流程沒有改到結果）
rem  (2) GLOBAL_v3_0 跑 C、D、tpe2t_2700：OCR 次數、過線事件要和 R13 的精確模擬相同，並量實際省下的時間
rem 跑完後執行：python 30_實驗\R14_三層設定14_check_run.py
echo 開始時間：%date% %time%
call "%~dp0..\跑實驗.bat" R14_三層設定 GLOBAL_v2_2 tpe_C_600 --novideo
call "%~dp0..\跑實驗.bat" R14_三層設定 GLOBAL_v3_0 tpe_C_600 tpe_D_1800 tpe2t_2700 --novideo
echo 結束時間：%date% %time%
pause
