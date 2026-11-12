# 馬拉松號碼牌辨識系統（YOLO + OCR）

輸入一段馬拉松終點或路線的影片，系統會自動找出畫面中跑者的**號碼牌號碼**，並記錄每個號碼出現的時間。結果輸出成 CSV，也可以另外輸出一支把號碼標在跑者身上的影片。

雲科大專題成果。方法、準確率和評估設計的完整說明在 [`成果_號碼牌辨識/REPORT.md`](成果_號碼牌辨識/REPORT.md)。

## 運作方式

```
影片 ─► 每秒取 8 格 ─► YOLO11s 偵測人物 + ByteTrack 追蹤
     ─► 裁切軀幹 ─► RapidOCR（PP-OCRv4）讀數字（只保留 2～4 位數）
     ─► 同一位跑者的多次讀數加權投票 ─► 剔除車牌、看板等固定文字
     ─► 輸出 CSV ＋（選用）標註影片
```

## 效果

測試集上的初步數據如下（樣本數不多，只能當量級參考）：

| 指標 | 第一輪 test（50 個號碼） | 第二輪 test2（37 個號碼） |
|---|---|---|
| 精確率（輸出的號碼有多少是對的） | 0.78 | 0.62 |
| 召回率（看得清楚的號碼有多少被讀出） | 0.58 | 0.62 |
| F1 | 0.67 | 0.62 |

示範影片在 [`成果_號碼牌辨識/demo/`](成果_號碼牌辨識/demo/)，包含三種場景：林道逆光、拱門人潮、街道側拍。

## 資料夾結構

```
.
├─ README.md                  ← 本檔
└─ 成果_號碼牌辨識/
   ├─ 一鍵執行.bat             ← Windows：安裝環境並處理所有影片
   ├─ 一鍵執行_短片段.bat      ← Windows：每支影片只跑 30 秒，用來快速測試
   ├─ requirements.txt         ← 套件清單（含實驗用套件）
   ├─ requirements_win.txt     ← 套件清單（Windows 一鍵執行用）
   ├─ models/yolo11s.pt        ← 人物偵測模型（已附）
   ├─ src/                     ← 主程式 bibread.py、run_parallel.py 與實驗程式
   ├─ work/                    ← 標註、標準答案、鎖定設定、評估結果
   ├─ demo/                    ← 示範輸出
   ├─ 輸出_短片段/             ← 短片段版的執行結果範例
   ├─ REPORT.md                ← 實驗報告
   └─ PLAN.md                  ← 實驗過程紀錄
```

## 系統需求

- Python 3.10 或 3.11（建議用 Anaconda／Miniconda 管理）
- [ffmpeg](https://ffmpeg.org/)（需要 `ffmpeg` 與 `ffprobe` 指令）
- NVIDIA 顯示卡：**選用**。有的話速度快很多；只用 CPU 也能跑，但處理時間約為影片長度的 6～46 倍。

## 安裝

### 方法一：Windows 一鍵安裝（建議）

1. 安裝 [Anaconda](https://www.anaconda.com/download) 或 [Miniconda](https://docs.conda.io/en/latest/miniconda.html)，使用預設路徑即可。
2. 安裝 ffmpeg：
   ```bat
   winget install ffmpeg
   ```
3. 下載本專案：
   ```bat
   git clone https://github.com/IWannaListenToUSayUwU/bib-number-recognition.git
   ```
4. 第一次執行 `一鍵執行.bat` 時，會自動建立名為 `bibread` 的 conda 環境，並安裝 CUDA 版 PyTorch 和所有套件，約需 5～15 分鐘。

### 方法二：手動安裝（Windows／macOS／Linux）

```bash
git clone https://github.com/IWannaListenToUSayUwU/bib-number-recognition.git
cd bib-number-recognition/成果_號碼牌辨識

conda create -n bibread python=3.11 -y
conda activate bibread

# 有 NVIDIA 顯示卡：先裝 CUDA 版 PyTorch（沒有顯示卡可跳過這行）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124

pip install -r requirements_win.txt
```

`requirements.txt` 額外包含實驗腳本用的 `easyocr`。只要使用系統本身的話，裝 `requirements_win.txt` 就夠了。

## 使用方法

### 1. 準備影片

本 repo **沒有附原始影片**，因為檔案太大，而且是別人上傳的影片。

- **用自己的影片**：任何馬拉松或路跑影片都可以。號碼牌在畫面中越大、越清楚，效果越好。
- **重現實驗結果**：實驗用的三支影片來自 YouTube：
  | 代號 | 影片 | YouTube ID |
  |---|---|---|
  | v1 | 2013 Marathon Sports End of Summer Classic Finish Line Video | [338nQ8d1Z3Y](https://www.youtube.com/watch?v=338nQ8d1Z3Y) |
  | v2 | 20th Annual Millennium Mile Finish Line Video | [61H0GRdgvEQ](https://www.youtube.com/watch?v=61H0GRdgvEQ) |
  | v3 | BBB10K Finish line camera | [8yBDOP9luc8](https://www.youtube.com/watch?v=8yBDOP9luc8) |

**使用一鍵執行時，影片要放在 repo 根目錄**，也就是 `成果_號碼牌辨識` 的上一層：

```
bib-number-recognition/
├─ 你的影片.mp4          ← 放這裡
└─ 成果_號碼牌辨識/
```

### 2. 執行

#### Windows：一鍵執行

| 檔案 | 做什麼 | 結果位置 |
|---|---|---|
| `一鍵執行.bat` | 第一次會先安裝環境，接著跑 20 秒測速，再處理根目錄下**所有** `.mp4` 的完整內容 | `成果_號碼牌辨識\輸出\` |
| `一鍵執行_短片段.bat` | 每支實驗影片只處理 30 秒，約 20～30 分鐘跑完，適合快速確認系統正常。需要先執行過一次 `一鍵執行.bat` 完成安裝 | `成果_號碼牌辨識\輸出_短片段\` |

雙擊即可。執行期間黑色視窗可以縮小，但不要關掉。

#### 命令列：處理單一影片

```bash
conda activate bibread
cd 成果_號碼牌辨識

# 多核心平行處理（建議），輸出 CSV ＋ 標註影片到指定資料夾
python src/run_parallel.py "影片.mp4" --outdir 輸出

# 只處理第 600～660 秒
python src/run_parallel.py "影片.mp4" --outdir 輸出 --start 600 --end 660

# 不輸出標註影片（比較快）
python src/run_parallel.py "影片.mp4" --outdir 輸出 --no-video
```

| 參數 | 說明 |
|---|---|
| `--outdir` | 結果資料夾（必填） |
| `--start` / `--end` | 只處理這段時間（秒）；不指定就處理整支影片 |
| `--workers N` | 平行處理的行程數；不指定時自動決定 |
| `--no-video` | 只輸出 CSV，不輸出標註影片 |

也可以用單一行程的版本：

```bash
python src/bibread.py "影片.mp4" --out 結果.csv --annotated 標註.mp4 --start 600 --end 660
```

### 3. 看結果

每支影片會產生三個檔案：

- `影片名稱.csv`：辨識出的號碼清單
- `影片名稱_標註.mp4`：只把定案的號碼畫在對應跑者身上，內容和 CSV 一致
- `log.txt`：執行紀錄

CSV 範例：

```csv
bib,time_s,time_hms,first_s,last_s,score
399,855.12,00:14:15,855.12,855.50,1.741
689,855.38,00:14:15,855.12,855.38,2.429
```

| 欄位 | 說明 |
|---|---|
| `bib` | 號碼牌號碼 |
| `time_s` / `time_hms` | 號碼最清楚的那一格的時間（秒／時:分:秒） |
| `first_s` / `last_s` | 第一次與最後一次讀到這個號碼的時間（秒） |
| `score` | 投票分數，越高越可信 |

## 已知限制

- **人潮密集時召回率低**：號碼牌常被手臂、其他跑者遮住，或角度太斜。
- **強逆光或眩光**：畫面中幾乎偵測不到文字。
- **路邊車牌、看板可能被誤判成號碼**：已加入過濾規則，但文字位置抖動時仍可能漏掉。
- **少讀或多讀一位數**：例如把 301 讀成 1301，通常是號碼牌部分被遮住造成的。
- **沒有顯示卡時很慢**：建議用 `--start` / `--end` 分段處理，或改在有 GPU 的電腦上執行。

改進方向與詳細的錯誤分析，請見 [`REPORT.md`](成果_號碼牌辨識/REPORT.md) 第 4 節與「第二輪仍未解決」。

## 使用的開源專案

- [Ultralytics YOLO11](https://github.com/ultralytics/ultralytics)：人物偵測與 ByteTrack 追蹤
- [RapidOCR](https://github.com/RapidAI/RapidOCR)：文字辨識（PP-OCRv4 模型）
- [OpenCV](https://opencv.org/)、[ffmpeg](https://ffmpeg.org/)：影片讀寫
