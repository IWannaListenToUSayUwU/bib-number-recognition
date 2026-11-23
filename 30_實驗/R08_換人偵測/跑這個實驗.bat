@echo off
chcp 65001 >nul
rem R08 重跑：門檻 0.42（v2_4）與 0.50（v2_4b）各跑 C、D，走 30_實驗 的通用流程（會檢查 GPU 與片段指紋，跑完自動評分）
call "%~dp0..\跑實驗.bat" R08_換人偵測 FROZEN_CONFIG_v2_4 tpe_C_600 tpe_D_1800
call "%~dp0..\跑實驗.bat" R08_換人偵測 FROZEN_CONFIG_v2_4b tpe_C_600 tpe_D_1800 --novideo
pause
