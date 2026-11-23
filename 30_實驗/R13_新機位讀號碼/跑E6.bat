@echo off
chcp 65001 >nul
rem R13 GPU 第四批（05:08 起，依序）：E6 偵測短邊 320＋提早停止只算 5 碼（C、D → 4 段調整集）→ E2 貼底裁切（4 段調整集）
echo 開始時間：%date% %time%
call "%~dp0..\跑實驗.bat" R13_新機位讀號碼\E6 R13_E6_det320_es5 tpe_C_600 tpe_D_1800 tpe2t_2700 tpe2t_3600 tpe2t_4800 tpe2t_5700 --novideo
call "%~dp0..\跑實驗.bat" R13_新機位讀號碼\E2 R13_E2_bottomext tpe2t_2700 tpe2t_3600 tpe2t_4800 tpe2t_5700 --novideo
echo 結束時間：%date% %time%
