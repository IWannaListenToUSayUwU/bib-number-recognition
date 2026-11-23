@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"
set "OUT=%ROOT%..\40_成果\輸出_短片段"
if not exist "%OUT%" mkdir "%OUT%"
set "LOG=%OUT%\setup_log.txt"
echo ==== 號碼牌辨識：短片段版（每支影片 30 秒，共 3 段，約 20-30 分鐘）====
set "CONDA_BAT="
for %%P in ("%USERPROFILE%\anaconda3" "%USERPROFILE%\miniconda3" "C:\ProgramData\anaconda3" "C:\ProgramData\miniconda3") do (
  if exist "%%~P\Scripts\activate.bat" if not defined CONDA_BAT set "CONDA_BAT=%%~P\Scripts\activate.bat"
)
if not defined CONDA_BAT ( echo [錯誤] 找不到 Anaconda & pause & exit /b 1 )
call "%CONDA_BAT%"
call conda activate bibread
if errorlevel 1 ( echo [錯誤] 找不到 bibread 環境，請先執行 一鍵執行.bat 完成安裝 & pause & exit /b 1 )

echo [1/3] v1 林道逆光 855-885 秒
for %%V in ("%ROOT%..\00_原始素材\2013*.mp4") do python "%ROOT%src\run_parallel.py" "%%~fV" --outdir "%OUT%\v1_855-885" --start 855 --end 885 --workers 3 >> "%LOG%" 2>&1
echo [2/3] v2 拱門人潮 720-750 秒
for %%V in ("%ROOT%..\00_原始素材\20th*.mp4") do python "%ROOT%src\run_parallel.py" "%%~fV" --outdir "%OUT%\v2_720-750" --start 720 --end 750 --workers 3 >> "%LOG%" 2>&1
echo [3/3] v3 街道 1680-1710 秒
for %%V in ("%ROOT%..\00_原始素材\BBB10K*.mp4") do python "%ROOT%src\run_parallel.py" "%%~fV" --outdir "%OUT%\v3_1680-1710" --start 1680 --end 1710 --workers 3 >> "%LOG%" 2>&1
echo %date% %time% 全部完成 >> "%LOG%"
echo ==== 完成，結果在 %OUT% ====
pause
