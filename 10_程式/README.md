# 馬拉松號碼牌辨識系統

先讀 `REPORT.md`，裡面有方法、準確率和限制。

## 安裝（建議使用獨立環境）
```bash
conda create -n bibread python=3.11 -y
conda activate bibread
pip install -r requirements.txt
```
另外需要系統安裝 ffmpeg / ffprobe（Windows 可用 `winget install ffmpeg`）。
模型檔：`models/yolo11s.pt`（已附）；RapidOCR 的模型會隨 pip 套件一起安裝。

## 使用
```bash
python src/bibread.py "影片.mp4" --out 結果.csv
# 只處理一段（秒）並輸出標註影片：
python src/bibread.py "影片.mp4" --start 600 --end 660 --out 結果.csv --annotated 標註.mp4
```
輸出 CSV 欄位：bib（號碼）、time_s（最清楚那格的秒數）、time_hms、score（投票分數，越高越可信）。

## 速度
2 核 CPU、無 GPU 時，處理時間約為影片長度的 6–46 倍，人越多越慢。
一小時的影片建議分段跑（用 --start/--end），或改在有 GPU 的電腦上執行（ultralytics 會自動使用 CUDA）。

## 資料夾
- `src/`：系統（bibread.py）與全部實驗程式。
- `work/`：抽樣結果、標註規範、標準答案、原始標註、鎖定設定、評估結果。
- `demo/`：示範輸出（v1 第 855–875 秒）。

## 第二版：Windows 一鍵執行（建議）
雙擊 `一鍵執行.bat`：
- 第一次執行會建立 conda 環境 `bibread`，並安裝 CUDA 版 PyTorch。
- 先跑 20 秒測速，再依序處理上一層資料夾裡的所有 .mp4。
- 結果寫在 `輸出\`：每支影片一份 CSV 與一支 `_標註.mp4`（只標出定案號碼），進度記錄在 `log.txt`。

單獨處理一支影片：
```
conda activate bibread
python src\run_parallel.py "影片.mp4" --outdir 輸出 [--start 秒 --end 秒] [--workers N] [--no-video]
```
`demo\` 裡有同一段影片（v1 第 855–875 秒）的舊版與新版標註，可以直接對照。
