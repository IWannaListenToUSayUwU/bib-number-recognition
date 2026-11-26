# 馬拉松號碼布辨識＋過線計時系統（YOLO + OCR）

輸入一段馬拉松影片，系統會找出畫面中每一位跑者、讀出**號碼布號碼**，並算出他**通過計時線的時間**（計時線是在畫面上自行指定的一條虛擬線）。比賽時鐘有入鏡時，過線時間還可以換成**槍聲時間**，直接和官方成績比對。

雲科大專題成果。目前版本是 **GLOBAL_v3_1**（2026-11-24 定版）。

- 期末報告：[`40_成果/期末報告.md`](40_成果/期末報告.md)，內容包括方法、評估設計、成績與限制。
- 成果總覽與 demo 影片：[`40_成果/README.md`](40_成果/README.md)
- 各版本的變化：[`版本紀錄.md`](版本紀錄.md)
- 第一、二輪報告（2026-11-12，用國外影片）：[`10_程式/REPORT.md`](10_程式/REPORT.md)

## 運作方式（v3.1）

```
影片 ─► 每秒取 16 格 ─► YOLO11s 偵測人物 ＋ ByteTrack 追蹤（衣服顏色或位置突變時切成新軌跡）
     ─► 讀字閘門：站著不動的人不讀、只讀計時線附近的人
     ─► 裁切軀幹 ─► RapidOCR（PP-OCRv4）讀數字
     ─► 過線模組：人框底部（腳的位置）跨過計時線 → 在前後兩格之間內插出過線時間
     ─► 號碼定案：多次讀數投票 ＋ 號碼位數／號碼名單 ＋ 共識解碼 ＋ 號碼布顏色
     ─► events.csv：每個過線事件一行（過線時間、號碼；讀不出號碼的人也會輸出，號碼空白）
```

設定分成三層，每支影片不必重新調參數：

| 層 | 內容 | 什麼時候設定 |
|---|---|---|
| 全域（`10_程式/config/global/`） | 演算法參數，只有一套（目前是 GLOBAL_v3_1） | 開發時定版，定版後不再修改 |
| 比賽（`config/race/`） | 號碼位數、號碼名單、號碼布顏色規則 | 賽前向主辦單位取得 |
| 機位（`config/camera/`） | 計時線位置、只讀線附近的範圍、時鐘位置 | 架好攝影機後在畫面上點選，不需要正確答案 |

## 效果

主要指標是**號碼和過線時間都對的跑者比例**：時間以 ±0.5 秒比人工答案，或以 ±2 秒比官方成績。完整成績單在 [`20_測試基準/成績單.md`](20_測試基準/成績單.md)，由 `python 20_測試基準/scorecard.py` 產生。

| 測試集 | 答案來源 | v3.1 | 輸出號碼錯誤率 | 時間誤差中位數 |
|---|---|---|---|---|
| 2022 臺北馬・轉角機位 C+D（122 人） | 人工標註的過線正確答案 | **0.762** [0.68, 0.83] | 0.097 | 0.06 秒 |
| 2022 臺北馬・終點線機位 tpe2（160 人） | 官方完賽名單 | **0.225** [0.17, 0.30] | 0.077 | 0.36 秒（官方成績只到整秒） |
| 2026 新屋魚米之鄉・終點（92 人，960×720、逆光） | 官方完賽名單 | **0.391** [0.30, 0.49] | 0（輸出 36 個全對） | 0.07 秒 |

方括號內是 95% 信賴區間。

- 終點機位的兩個測試集用**全部完賽者**當分母，包含號碼布本來就被遮住、看不清的人，所以比人工答案嚴格。人眼實際看得出的上限還沒量。
- 這三個測試集在開發過程中都用過，**不是保留卷**（從沒看過的影片）。數字可能偏樂觀。
- 速度：文字辨識（OCR）跑在 CPU 上，處理時間約為影片長度的 9～20 倍，**還不是即時**。OCR 改用 GPU 時每張圖快約 3 倍，這是初步量測。

過線計時 demo 影片在 [`40_成果/過線計時demo/`](40_成果/過線計時demo/)。

## 資料夾結構

```
.
├─ README.md                  ← 本檔（GitHub 用）
├─ 規格.md / 研究流程.md       ← 實驗規則（怎麼跑才算數、下一步怎麼決定）
├─ 專案導覽.md / 版本紀錄.md   ← 專案地圖、各版本的變化
├─ 00_原始素材/               ← 原始影片（不上傳）
├─ 10_程式/
│  ├─ src/                     ← 主程式與實驗程式（extract9、bibrules、crossing、settings…）
│  ├─ config/                  ← 三層設定：global／race／camera（說明見 config/README.md）
│  ├─ models/yolo11s.pt        ← 人物偵測模型（已附）
│  ├─ work/                    ← 舊版凍結設定檔、計時線原始檔、標註規範
│  ├─ 一鍵執行*.bat            ← 舊版（v2.1）一鍵安裝＋執行
│  └─ REPORT.md                ← 第一、二輪報告（2026-11-12）
├─ 20_測試基準/               ← 固定測試片段的清單與指紋（MANIFEST）、正確答案、評分程式、成績單
├─ 30_實驗/                   ← 各輪實驗（R03～R19），每輪有計畫.md／總結；跑實驗.bat、run_experiment.py
└─ 40_成果/                   ← 期末報告、成果總覽、過線計時 demo、早期 demo
```

## 系統需求

- Python 3.10 或 3.11（建議用 Anaconda／Miniconda 管理）
- [ffmpeg](https://ffmpeg.org/)（需要 `ffmpeg` 與 `ffprobe` 指令）
- NVIDIA 顯示卡：正式實驗流程會檢查 CUDA GPU，沒有就停止。開發時用的是 RTX 3050 Ti Laptop。
  只用 CPU 也能跑舊版一鍵執行，但很慢。

## 安裝

### 方法一：Windows 一鍵安裝

1. 安裝 [Anaconda](https://www.anaconda.com/download) 或 [Miniconda](https://docs.conda.io/en/latest/miniconda.html)，使用預設路徑即可。
2. 安裝 ffmpeg：
   ```bat
   winget install ffmpeg
   ```
3. 下載本專案：
   ```bat
   git clone https://github.com/IWannaListenToUSayUwU/bib-number-recognition.git
   ```
4. 第一次執行 `10_程式/一鍵執行.bat` 時，會自動建立名為 `bibread` 的 conda 環境，並安裝 CUDA 版 PyTorch 和所有套件，約需 5～15 分鐘。

### 方法二：手動安裝（Windows／macOS／Linux）

```bash
git clone https://github.com/IWannaListenToUSayUwU/bib-number-recognition.git
cd bib-number-recognition/10_程式

conda create -n bibread python=3.11 -y
conda activate bibread

# 有 NVIDIA 顯示卡：先裝 CUDA 版 PyTorch
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124

pip install -r requirements_win.txt
```

`requirements.txt` 額外包含實驗腳本用的 `easyocr`。只使用系統本身的話，裝 `requirements_win.txt` 就夠了。

## 使用方法

本 repo **沒有附原始影片**，因為檔案太大，而且是別人上傳的影片。官方成績也不上傳（只上傳號碼名單）。

### A. v3.1 過線計時（目前的系統）

v3.1 目前只能透過實驗流程執行，**還沒有給一般使用者的一鍵版本**。步驟：

1. 從影片剪出片段，放進 `20_測試基準/clips/`，在 `20_測試基準/MANIFEST.json` 登記片段的 sha256、`camera`、`race`。
2. 新機位：在 `10_程式/config/camera/` 建一個機位檔，填畫面大小和計時線（兩個點＋一個上游點），格式照現有的 `tpe_corner_CD.json`。
   新比賽：在 `config/race/` 填號碼位數，有號碼名單的話也一起放。
3. 執行（Windows，conda 環境 `bibread`）：
   ```bat
   30_實驗\跑實驗.bat Rxx_名稱 GLOBAL_v3_1 片段名稱1 片段名稱2
   ```
4. 結果在 `30_實驗/Rxx_名稱/out/GLOBAL_v3_1/<片段>/`：
   - `events.csv`：過線事件。主要欄位有 `t_cross`（過線時間，片段秒數）、`bib`（定案號碼，空白＝讀不出）、`decided_by`（怎麼定案的）、`latency`（過線後多久定案）。
   - `raw.jsonl`：每一格的追蹤與讀數。
   - `run_info.json`：設定檔和程式的 sha256、GPU 名稱、時間。

要輸出 demo 影片，例如畫出計時線、過線的人和號碼，可以用 `10_程式/src/render_crossing_demo.py`，用法見 [`40_成果/README.md`](40_成果/README.md)。

### B. 舊版一鍵執行（v2.1：只輸出號碼和出現時間，沒有過線時間）

影片放在 `00_原始素材\`（與 `10_程式` 同一層），然後雙擊：

| 檔案 | 做什麼 | 結果位置 |
|---|---|---|
| `一鍵執行.bat` | 第一次會先安裝環境，接著跑 20 秒測速，再處理 `00_原始素材\` 下**所有** `.mp4` 的完整內容 | `40_成果\輸出\` |
| `一鍵執行_短片段.bat` | 每支影片只處理 30 秒，適合快速確認系統正常。需要先執行過一次 `一鍵執行.bat` 完成安裝 | `40_成果\輸出_短片段\` |

也可以用命令列處理單一影片：

```bash
conda activate bibread
cd 10_程式
python src/run_parallel.py "影片.mp4" --outdir 輸出 --start 600 --end 660   # 只處理第 600～660 秒
python src/run_parallel.py "影片.mp4" --outdir 輸出 --no-video              # 不輸出標註影片
```

輸出的 CSV 欄位：`bib`（號碼）、`time_s`／`time_hms`（號碼最清楚那一格的時間）、`first_s`／`last_s`（第一次和最後一次讀到）、`score`（投票分數）。
這一版號碼只接受 2～5 位數，也不使用號碼名單。

## 已知限制

- **速度還不是即時**：OCR 跑在 CPU 上，佔處理時間約 95%。
- **終點線機位讀號碼弱**：畫面過曝、壓縮嚴重、號碼布對比低時，即使跑者靠近鏡頭，單張畫面也只有約 14% 讀對。前處理（對比增強、放大等）都試過，沒有效果，瓶頸是 OCR 模型本身。
- **混人**：號碼可能被掛到旁邊的跑者身上，人潮密集時特別明顯。
- **號碼名單用完賽者名單代替報名名單**：名單放大 30% 時只少 1～2 人，影響小；但真實部署要換成報名名單。
- **計時線要手動指定**：攝影機移動後要重新指定。
- **沒有保留卷**：還沒在從沒看過的新影片上驗證。

## 使用的開源專案

- [Ultralytics YOLO11](https://github.com/ultralytics/ultralytics)：人物偵測與 ByteTrack 追蹤
- [RapidOCR](https://github.com/RapidAI/RapidOCR)：文字辨識（PP-OCRv4 模型）
- [OpenCV](https://opencv.org/)、[ffmpeg](https://ffmpeg.org/)：影片讀寫
