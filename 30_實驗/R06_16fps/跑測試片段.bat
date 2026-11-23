@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"
set "BIB_OCR_THREADS=8"
if not exist "%ROOT%out" mkdir "%ROOT%out"
echo ==== 第六輪：v2.2 + 每秒16格，跑 C、D 兩段（約 30-40 分鐘）====
call "%USERPROFILE%\anaconda3\Scripts\activate.bat"
call conda activate bibread
if errorlevel 1 ( echo [錯誤] 找不到 bibread 環境 & pause & exit /b 1 )
echo [1/2] tpe_C_600
python "%ROOT%run_clip.py" "%ROOT%..\第五輪_5碼修正\clips\tpe_C_600.mp4" >> "%ROOT%out\console.txt" 2>&1
echo [2/2] tpe_D_1800
python "%ROOT%run_clip.py" "%ROOT%..\第五輪_5碼修正\clips\tpe_D_1800.mp4" >> "%ROOT%out\console.txt" 2>&1
echo %date% %time% 全部完成 >> "%ROOT%out\log.txt"
echo ==== 完成 ====
pause
