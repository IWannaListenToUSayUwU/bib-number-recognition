@echo off
chcp 65001 >nul
rem R12 第二機位：v2.2（每秒 16 格）用正式流程跑 3 段終點線新片段，再跑 C、D（確認正式流程和 R06 的結果一致）。
rem 會檢查 GPU 與片段指紋；不產生標註影片（--novideo）。預估 1.5～2 小時，可以放著跑。
echo 開始時間：%date% %time%
call "%~dp0..\跑實驗.bat" R12_第二機位 FROZEN_CONFIG_v2_2 tpe2_A_3000 tpe2_B_4200 tpe2_C_5400 tpe_C_600 tpe_D_1800 --novideo
echo 結束時間：%date% %time%
pause
