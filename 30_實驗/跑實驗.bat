@echo off
chcp 65001 >nul
setlocal
rem ===== 30_實驗 通用執行檔（規格.md 第 3 節）=====
rem 用法：跑實驗.bat <實驗名> <設定檔名> <片段...>   （通常由各實驗資料夾的「跑這個實驗.bat」呼叫）
rem 例：  跑實驗.bat R08_換人偵測 FROZEN_CONFIG_v2_4 tpe_C_600 tpe_D_1800
set "HERE=%~dp0"
if "%~3"=="" ( echo [錯誤] 參數不足：跑實驗.bat 實驗名 設定檔名 片段... & pause & exit /b 1 )
set "BIB_OCR_THREADS=8"
set "CONDA_BAT="
for %%P in ("%USERPROFILE%\anaconda3" "%USERPROFILE%\miniconda3" "C:\ProgramData\anaconda3" "C:\ProgramData\miniconda3") do (
  if exist "%%~P\Scripts\activate.bat" if not defined CONDA_BAT set "CONDA_BAT=%%~P\Scripts\activate.bat"
)
if not defined CONDA_BAT ( echo [錯誤] 找不到 Anaconda & pause & exit /b 1 )
call "%CONDA_BAT%"
call conda activate bibread
if errorlevel 1 ( echo [錯誤] 找不到 bibread 環境 & pause & exit /b 1 )
python -c "import torch,sys; ok=torch.cuda.is_available(); print('GPU:', torch.cuda.get_device_name(0) if ok else '無'); sys.exit(0 if ok else 2)"
if errorlevel 1 ( echo [停止] 偵測不到 CUDA GPU，不准用 CPU 跑。 & pause & exit /b 2 )
echo ==== 實驗 %1 ／ 設定 %2 ／ 片段 %3 %4 %5 %6 %7 %8 ====
if not exist "%HERE%%~1\out" mkdir "%HERE%%~1\out"
python "%HERE%run_experiment.py" %* >> "%HERE%%~1\out\console.txt" 2>&1
if errorlevel 1 ( echo [失敗] 請看 %HERE%%~1\out\console.txt & pause & exit /b 1 )
echo ==== 完成，分數在 %HERE%%~1\out\%~2\score.json ====
