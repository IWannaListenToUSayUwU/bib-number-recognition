@echo off
chcp 65001 >nul
rem R13：舊機位 A、B 段用 v2.2（每秒 16 格）重跑（原本只有 R04 的 v2、8 格），給官方名單獨立評估用。輸出在 AB16\out
echo 開始時間：%date% %time%
call "%~dp0..\跑實驗.bat" R13_新機位讀號碼\AB16 FROZEN_CONFIG_v2_2 tpe_A_300 tpe_B_1200 --novideo
echo 結束時間：%date% %time%
