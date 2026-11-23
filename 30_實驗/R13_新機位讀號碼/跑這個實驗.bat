@echo off
chcp 65001 >nul
rem R13 調整集基準：v2.2（每秒 16 格）跑 4 段調整集片段（Claude 在夜間自動執行）
echo 開始時間：%date% %time%
call "%~dp0..\跑實驗.bat" R13_新機位讀號碼 FROZEN_CONFIG_v2_2 tpe2t_2700 tpe2t_3600 tpe2t_4800 tpe2t_5700 --novideo
echo 結束時間：%date% %time%
