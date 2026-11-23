@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"
set "BIB_OCR_THREADS=8"
if not exist "%ROOT%out" mkdir "%ROOT%out"
echo ==== 第五輪 5碼修正：用第二版 v2.1（maxlen=5）跑 2 個 60 秒片段 ====
if not exist "%ROOT%..\成果_號碼牌辨識\work\FROZEN_CONFIG_v2_1.json" ( echo [錯誤] 找不到 ..\成果_號碼牌辨識\work\FROZEN_CONFIG_v2_1.json & pause & exit /b 1 )
if not exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" ( echo [錯誤] 找不到 %USERPROFILE%\anaconda3\Scripts\activate.bat & pause & exit /b 1 )
call "%USERPROFILE%\anaconda3\Scripts\activate.bat"
call conda activate bibread
if errorlevel 1 ( echo [錯誤] 找不到 bibread 環境 & pause & exit /b 1 )
echo [1/2] tpe_C_600（進度請看 out\log.txt）
python "%ROOT%run_clip.py" "%ROOT%clips\tpe_C_600.mp4" >> "%ROOT%out\console.txt" 2>&1
echo [2/2] tpe_D_1800（進度請看 out\log.txt）
python "%ROOT%run_clip.py" "%ROOT%clips\tpe_D_1800.mp4" >> "%ROOT%out\console.txt" 2>&1
echo %date% %time% 全部完成 >> "%ROOT%out\log.txt"
echo ==== 完成，結果在 %ROOT%out ====
pause
