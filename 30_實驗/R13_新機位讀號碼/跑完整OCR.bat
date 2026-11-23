@echo off
chcp 65001 >nul
rem R13 完整 OCR（early_stop=999，每格都 OCR）：C、D＋調整集第 1 段。給離線精確模擬提速策略用。輸出在 FULL\out
rem （原本排在這裡的 E3「不動的人不做 OCR」改成用這份完整紀錄離線精確重現，設定檔 R13_E3_static.json 保留）
echo 開始時間：%date% %time%
call "%~dp0..\跑實驗.bat" R13_新機位讀號碼\FULL R13_FULL_ocr tpe_C_600 tpe_D_1800 tpe2t_2700 --novideo
echo 結束時間：%date% %time%
