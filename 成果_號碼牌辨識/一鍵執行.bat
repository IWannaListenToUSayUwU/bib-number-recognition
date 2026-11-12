@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"
set "OUT=%ROOT%輸出"
if not exist "%OUT%" mkdir "%OUT%"
set "LOG=%OUT%\setup_log.txt"
echo ==== 號碼牌辨識：一鍵執行 ==== 
echo 進度紀錄會寫在 %OUT%  （這個視窗可以縮小，但不要關掉）

rem ---- 找 Anaconda / Miniconda ----
set "CONDA_BAT="
for %%P in ("%USERPROFILE%\anaconda3" "%USERPROFILE%\miniconda3" "C:\ProgramData\anaconda3" "C:\ProgramData\miniconda3") do (
  if exist "%%~P\Scripts\activate.bat" if not defined CONDA_BAT set "CONDA_BAT=%%~P\Scripts\activate.bat"
)
if not defined CONDA_BAT (
  echo [錯誤] 找不到 Anaconda/Miniconda >> "%LOG%"
  echo [錯誤] 找不到 Anaconda/Miniconda，請告訴 Claude。
  pause & exit /b 1
)
call "%CONDA_BAT%"
echo %date% %time% 使用 conda: %CONDA_BAT% >> "%LOG%"

rem ---- 建立獨立環境 bibread（只在第一次執行時安裝）----
call conda env list | findstr /b /c:"bibread " >nul
if errorlevel 1 (
  echo 第一次執行：建立 Python 環境 bibread（約 5-15 分鐘）...
  echo %time% 建立環境 >> "%LOG%"
  call conda create -y -n bibread python=3.11 >> "%LOG%" 2>&1
)
call conda activate bibread
python -c "import torch,sys;sys.exit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
if errorlevel 1 (
  echo 安裝支援 CUDA 的 PyTorch ...
  echo %time% 安裝 torch cu124 >> "%LOG%"
  python -m pip install --upgrade pip >> "%LOG%" 2>&1
  python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124 >> "%LOG%" 2>&1
)
python -m pip install -r "%ROOT%requirements_win.txt" >> "%LOG%" 2>&1
python -c "import torch;print('CUDA 可用:',torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '');import os;print('CPU 核心:',os.cpu_count())" >> "%LOG%" 2>&1
type "%LOG%" | findstr /c:"CUDA"

rem ---- 先測速 20 秒，再跑三支完整影片 ----
echo %time% 開始測速 >> "%LOG%"
for %%V in ("%ROOT%..\2013*.mp4") do python "%ROOT%src\run_parallel.py" "%%~fV" --outdir "%OUT%\speedtest" --start 855 --end 875 >> "%LOG%" 2>&1
echo 測速完成，開始處理完整影片...
for %%V in ("%ROOT%..\*.mp4") do (
  echo 處理：%%~nxV
  python "%ROOT%src\run_parallel.py" "%%~fV" --outdir "%OUT%" >> "%LOG%" 2>&1
)
echo %date% %time% 全部完成 >> "%LOG%"
echo ==== 全部完成，結果在 %OUT% ====
pause
