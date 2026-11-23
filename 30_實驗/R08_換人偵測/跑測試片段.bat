@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"
set "BIB_OCR_THREADS=8"
if not exist "%ROOT%out" mkdir "%ROOT%out"
echo ==== 第八輪：調嚴換人偵測，門檻 0.42 與 0.50 各跑 C、D（約 30-50 分鐘）====
call "%USERPROFILE%\anaconda3\Scripts\activate.bat"
call conda activate bibread
if errorlevel 1 ( echo [錯誤] 找不到 bibread 環境 & pause & exit /b 1 )
echo [1/4] 0.42 tpe_C_600
python "%ROOT%run_clip.py" "%ROOT%..\第五輪_5碼修正\clips\tpe_C_600.mp4" FROZEN_CONFIG_v2_4 >> "%ROOT%out\console.txt" 2>&1
echo [2/4] 0.42 tpe_D_1800
python "%ROOT%run_clip.py" "%ROOT%..\第五輪_5碼修正\clips\tpe_D_1800.mp4" FROZEN_CONFIG_v2_4 >> "%ROOT%out\console.txt" 2>&1
echo [3/4] 0.50 tpe_C_600
python "%ROOT%run_clip.py" "%ROOT%..\第五輪_5碼修正\clips\tpe_C_600.mp4" FROZEN_CONFIG_v2_4b novideo >> "%ROOT%out\console.txt" 2>&1
echo [4/4] 0.50 tpe_D_1800
python "%ROOT%run_clip.py" "%ROOT%..\第五輪_5碼修正\clips\tpe_D_1800.mp4" FROZEN_CONFIG_v2_4b novideo >> "%ROOT%out\console.txt" 2>&1
echo %date% %time% 全部完成 >> "%ROOT%out\log.txt"
echo ==== 完成 ====
pause
