@echo off
chcp 65001 >nul
rem R13 GPU 第二批（依序）：(1) 完整 OCR（C、D＋tpe2t_2700）→ (2) E5 OCR 偵測短邊 320（C、D＋4 段調整集，提速）→ (3) E2 貼底裁切（4 段調整集）
rem 01:58 起順序調整過：OCR 探針顯示前處理都無效（E2 預期幫助小）；02:07 OCR 速度探針顯示偵測短邊 320 快 2.5 倍、讀對率不變
echo 開始時間：%date% %time%
call "%~dp0..\跑實驗.bat" R13_新機位讀號碼\FULL R13_FULL_ocr tpe_C_600 tpe_D_1800 tpe2t_2700 --novideo
echo 完整 OCR 結束：%date% %time%
call "%~dp0..\跑實驗.bat" R13_新機位讀號碼\E5 R13_E5_det320 tpe_C_600 tpe_D_1800 tpe2t_2700 tpe2t_3600 tpe2t_4800 tpe2t_5700 --novideo
echo E5 結束：%date% %time%
call "%~dp0..\跑實驗.bat" R13_新機位讀號碼\E2 R13_E2_bottomext tpe2t_2700 tpe2t_3600 tpe2t_4800 tpe2t_5700 --novideo
echo 結束時間：%date% %time%
