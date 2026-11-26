# 三層設定（2026-11-23 起）

原則：**能用分數調的參數只有全域一套；每個機位只設定「不需要正確答案就能填」的東西。**
不要為單一影片調參數——部署時沒有正確答案可以調，而且 R13 證實「在某一段調好的設定」換一段就會變差。

| 層 | 資料夾 | 內容 | 誰、什麼時候設定 |
|---|---|---|---|
| 全域（演算法） | `global\GLOBAL_vX.json` | 每秒格數、OCR、投票規則、提早停止、OCR 閘門（不動的人不讀）、過線模組、定案模式 | 開發時定版；**定版後不再修改**，要改就另存新版號；要在至少兩個機位的調整集＋檢查集驗證 |
| 比賽（賽事資料） | `race\<比賽>.json`＋號碼名單 | 號碼位數、號碼名單（只放號碼，**不放成績時間**）、號碼布顏色規則、時鐘顯示什麼時間 | 賽前從主辦單位拿到；同一場比賽的所有機位共用 |
| 機位（幾何） | `camera\<機位>.json` | 畫面大小、計時線（兩點＋上游點）、只讀線附近的範圍、時鐘在畫面哪裡 | 架好攝影機後點選；不需要標正確答案 |

片段屬於哪個機位、哪場比賽：`20_測試基準\MANIFEST.json` 每個片段的 `camera`、`race` 欄位。

## 目前的檔案
- `global\GLOBAL_v2_2.json`：v2.2（2026-11-18 定版）改寫成三層格式，只用來確認新流程能重現 v2.2（R14 驗證）。
- `global\GLOBAL_v3_0.json`：R13 的建議：v2.2 ＋ 不動的人不讀 ＋ 只讀線附近 ＋ 定案用號碼名單＋共識解碼＋號碼布顏色。一直是候選，被 v3.1 取代，沒有定版。
- `global\GLOBAL_v3_1.json`：**目前定版**（2026-11-24，R18）。內容是 v3.0 ＋ 追蹤門檻和讀字門檻分開（`extract9.py`：min_h 40、ocr_min_h 100）＋ 定案 `long_trim`（號碼前多印字的長讀數，取名單上唯一的 5 碼片段）。
- `race\tpe2022_full.json`、`race\tpe2022_full_bibs.txt`：2022 臺北馬全馬（5 碼，7,811 個號碼，取自完賽者；真實部署要換成報名名單）。
- `race\xinwu2026.json`、`race\xinwu2026_bibs.txt`：2026 新屋魚米之鄉（5 碼，10K＋21K 完賽者 3,315 個號碼，R17）。
- `camera\tpe_corner_CD.json`：第一支影片轉角機位（C、D）。`camera\tpe_corner_AB.json`：同一支影片 A、B（機位略不同、計時線未量，只能輸出出現的號碼）。
  `camera\tpe2_finish.json`：第二支影片終點線機位（含時鐘位置）。
  `camera\xinwu_finish.json`：新屋終點（960×720）。計時線是 Claude 依畫面估計的，使用者還沒確認。這個機位檔有覆寫過線參數（min_travel 10、decide_after 5）。

## 機位層可以覆寫的過線參數（v3.1 起）
`settings.apply_camera` 允許機位檔的 `crossing` 覆寫 `min_travel`、`decide_after`、`u_range`、`max_gap`（`CAMERA_CROSSING_KEYS`），其他鍵會報錯。
這幾個參數和畫面幾何有關：線離鏡頭多遠、人在線前多遠開始被追蹤。它們可以從畫面量出來，不需要用分數調。
  計時線的原始檔仍在 `10_程式\work\LINE_*.json`（舊實驗要用，不改），機位檔內記了來源 sha256。

## 定案模式會依比賽資料自動退回
全域 `decision.mode` → `fallback` 依序：有名單＋顏色規則 → `cons_color`；只有名單 → `cons`；只有號碼位數 → `len5`；什麼都沒有 → `v22`。

## 怎麼用
- 正式實驗：`call "%~dp0..\跑實驗.bat" Rxx_名稱 GLOBAL_v3_1 tpe_C_600 tpe_D_1800`。設定檔名寫全域層的檔名即可，機位、比賽依 MANIFEST 自動合併。
  除了 raw.jsonl、result.csv，還會寫 events.csv（過線事件＋號碼定案）和 score_v2.json。
- 程式：`10_程式\src\settings.py`（讀取、合併）、`ocrgate.py`（要不要做 OCR）、`bibrules.py`（號碼定案規則、過線事件）。
  抽取程式由全域檔的 `extract.script` 指定：v3.0 是 `extract8.py`，v3.1 是 `extract9.py`。

## 還沒改的絕對像素參數（研究流程 第 7 節 #9）
`extract.min_h`（v3.1 是 40 px）、`extract.ocr_min_h`（100 px）、`aggregate.size_ref=abs40`（字高 40 px）、`crossing.min_travel`（全域 100 px，機位層可以覆寫）、機位層的 `zone.up_px/down_px`。
換解析度或距離差很多的機位時要注意。R17 的新屋（960×720）就是因為 min_h、min_travel 而讓凍結版 0 個過線。
改成相對值需要另一輪實驗驗證：R13 前曾試過相對字高權重，舊影片精確度下降，所以沒採用。
