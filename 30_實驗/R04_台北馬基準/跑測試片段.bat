@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"
set "BIB_OCR_THREADS=8"
if not exist "%ROOT%out" mkdir "%ROOT%out"
echo ==== 第四輪 台北馬測試：用第二版系統跑 2 個 60 秒片段 ====
if not exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" ( echo [錯誤] 找不到 %USERPROFILE%\anaconda3\Scripts\activate.bat & pause & exit /b 1 )
call "%USERPROFILE%\anaconda3\Scripts\activate.bat"
call conda activate bibread
if errorlevel 1 ( echo [錯誤] 找不到 bibread 環境 & pause & exit /b 1 )
echo [1/2] tpe_A_300（進度請看 out\log.txt）
python "%ROOT%run_clip.py" "%ROOT%clips\tpe_A_300.mp4" >> "%ROOT%out\console.txt" 2>&1
echo [2/2] tpe_B_1200（進度請看 out\log.txt）
python "%ROOT%run_clip.py" "%ROOT%clips\tpe_B_1200.mp4" >> "%ROOT%out\console.txt" 2>&1
echo %date% %time% 全部完成 >> "%ROOT%out\log.txt"
echo ==== 完成，結果在 %ROOT%out ====
pause
