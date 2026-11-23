@echo off
chcp 65001 >nul
rem R13 GPU 第三批（04:45 起，依序）：E5b 偵測短邊 480（C、D）→ E5c 短邊 320＋外擴 2.0（C、D）→ E2 貼底裁切（4 段調整集）
echo 開始時間：%date% %time%
call "%~dp0..\跑實驗.bat" R13_新機位讀號碼\E5b R13_E5b_det480 tpe_C_600 tpe_D_1800 --novideo
call "%~dp0..\跑實驗.bat" R13_新機位讀號碼\E5c R13_E5c_det320u2 tpe_C_600 tpe_D_1800 --novideo
call "%~dp0..\跑實驗.bat" R13_新機位讀號碼\E2 R13_E2_bottomext tpe2t_2700 tpe2t_3600 tpe2t_4800 tpe2t_5700 --novideo
echo 結束時間：%date% %time%
