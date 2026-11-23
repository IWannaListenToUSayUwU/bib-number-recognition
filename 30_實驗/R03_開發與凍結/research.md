# 號碼牌辨識專題：網路調查（2026-11-16）

> 方法：WebSearch / WebFetch。YouTube 頁面本身無法抓取（WebFetch 失敗、curl 被代理 403），
> 所以**影片長度與解析度一律查不到**，只能從標題推測。下列影片皆為搜尋結果中實際出現的標題與網址，
> 是否為固定鏡頭、號碼牌是否清楚，**需自行開啟確認**。

## A. 台灣賽事終點（或終點前）影片候選（找到 6 支台灣 + 2 支日本備選）

| # | 標題（搜尋結果原文） | 網址 | 長度 / 解析度 | 適合理由與疑慮 |
|---|---|---|---|---|
| 1 | 2025台北馬全馬最後200m轉角 大會完賽時間4:09-10內鏡頭 4K/59.94fps | https://www.youtube.com/watch?v=hAGPCn6wjDU | 長度未知；標題寫 4K/59.94fps | 4K 高幀率最有利小字；4 小時左右完賽者人潮中等偏密。是「最後 200m 轉角」而非終點拱門，角度需確認 |
| 2 | 【4k】2022年台北馬拉松 全馬終點前最後轉角 四小時以內完賽跑友 | https://www.youtube.com/watch?v=Qd2kHAKTQhI | 長度未知；標題寫 4K | 同一拍攝點型態（疑同一作者系列），可做跨年度測試；sub-4 人潮較稀疏 |
| 3 | 2021 台北馬拉松 全馬終點 4:40前 | https://www.youtube.com/watch?v=NMDJj3RB0q8 | 未知 | 標題明寫「全馬終點」；4:40 前人潮較密，可測遮擋 |
| 4 | 【高雄馬】最完整半、全馬終點畫面 快找找你在哪裡 ⁉ | https://www.youtube.com/watch?v=yoQ6PGurn3M | 未知（標題稱「最完整」，可能很長） | 明確為終點畫面、讓跑者「找自己」，通常為固定機位、號碼牌可見 |
| 5 | 賽事全直擊 ! 國內首場金標賽事終點前畫面 快找找你在哪裡 ⁉ ( 兩小時至四小時) 【萬金石馬拉松】 | https://www.youtube.com/watch?v=VuzUa55LC9g | 未知（涵蓋 2–4 小時完賽者，可能很長） | 與 #4 疑同一系列頻道；涵蓋人潮由稀到密，適合切多段 |
| 6 | 2022萬金石馬拉松/破3列車終點直擊/一輪的運動日常 | https://www.youtube.com/watch?v=r2NmLJKYGg8 | 未知 | 有「終點直擊」，但屬個人 vlog，可能非全程固定鏡頭，優先度低 |
| 7 | （日本備選）福岡マラソン2026 定点カメラライブ映像（フィニッシュ地点/糸島市 志摩） | https://www.youtube.com/watch?v=hcpmKkN4ASg | 未知（直播存檔，通常數小時） | 官方「定點攝影機」+ 終點，最符合固定鏡頭條件 |
| 8 | （日本備選）横浜マラソン2026フィニッシュ地点アーカイブ配信 | https://www.youtube.com/watch?v=PBMrsYbxy5s | 未知（直播存檔） | 官方終點存檔；同類還有東京馬 15km 定點 https://www.youtube.com/watch?v=QU4NfldHTqE（非終點） |

- 台灣官方頻道（萬金石 https://www.youtube.com/channel/UCJi-W1K4jy_7XF50YnMDBTg 、田中馬 https://www.youtube.com/channel/UCwvEoSUiNaCNkXkhyxTocqQ ）
  搜到的多為精華剪輯，非固定終點鏡頭，不建議。
- 台灣官方「終點定點直播存檔」本次沒找到；日本大型賽事（福岡、橫濱、東京）較常提供。

## B. 免訓練、可直接取用的技術

### B1. 場景文字辨識模型（權重可從 PyPI / GitHub releases 取得）

1. **OnnxTR**（docTR 的 ONNX 版，`pip install "onnxtr[cpu]"` 或 `"onnxtr[cpu-headless]"`，最新 0.9.0，需 Python ≥ 3.11）
   - 辨識架構：`crnn_vgg16_bn`、`crnn_mobilenet_v3_small/large`、`sar_resnet31`、`master`、`vitstr_small/base`、`parseq`、`viptr_tiny`。
   - 權重來源：程式碼內預設 URL 為 GitHub releases，例如
     `https://github.com/felixdittrich92/OnnxTR/releases/download/v0.0.1/parseq-00b40714.onnx`、
     8-bit：`https://github.com/felixdittrich92/OnnxTR/releases/download/v0.1.2/parseq_dynamic_8_bit-5b04d9f7.onnx`（`from_hub()` 才走 HF，不用即可）。
   - CPU：純 onnxruntime，有 8-bit 量化版；對單張軀幹小裁切圖很快。
   - 做法：只用 recognition predictor，輸入 PP-OCR 偵測出的文字框；輸出再以「僅數字」過濾，或與 PP-OCR 結果做投票集成。
   - 風險：訓練詞彙為法／英文字元集，非數字專用，`0/O`、`1/I` 混淆需後處理；PARSeq 對極小（高 < 16px）字仍會失敗。
2. **PP-OCRv5（ONNX）**
   - `pip install "onnxocr-ppocrv5[onnx]"`（0.0.23，wheel 19.2 MB，**模型直接包在 wheel 內**，Apache-2.0，需另裝 numpy、opencv）。最符合「只能 PyPI」的限制。
   - 另一來源：oar-ocr 的 GitHub release，`https://github.com/GreatV/oar-ocr/releases/download/v0.3.0/pp-ocrv5_mobile_rec.onnx`（15.8 MiB）、
     `.../pp-ocrv5_server_rec.onnx`（80.6 MiB）、英文專用 `.../en_pp-ocrv5_mobile_rec.onnx`（7.5 MiB）。注意其 auto-download 走 ModelScope，要手動下載。
   - CPU：mobile 版可行；server 版 80 MB，每張裁切約數十～百毫秒級（未實測），配合「只在追蹤軌跡的少數好格上跑」即可。
   - 風險：wheel 內是哪個版本（mobile/server）頁面未寫；字典含大量中文，需限制輸出為數字。
3. RapidOCR（`rapidocr`）也支援 PP-OCRv5，但其模型預設下載來源本次未確認（可能是 ModelScope），不列為首選。

### B2. 多格融合／多格超解析

- 參考作法（車牌，arXiv 2607.08896）：以 **Laplacian 變異數挑最清晰格** → **ECC 仿射對齊**其他格 → 像素平均融合成一張；
  再用公開權重的 HAT（Real-HAT-GAN-SRx4）4× 超解析，加上 PARSeq + CLIP4STR **逐字元信心加權投票**，信心 < 0.33 則棄權。
  論文中超解析是最大單一提升（7.27→9.27 wECR），但其 OCR 有微調，提升不能直接套用。
- 本專題可免訓練落地的部分：
  1. 同一 track 內用 Laplacian 變異數/字框高度排序，只取前 K 格送 OCR（省 CPU、去模糊格）。
  2. `cv2.findTransformECC` 對齊 K 格號碼牌區域後取平均或中位數 → 降雜訊（跑者有晃動、旋轉，對齊須限在號碼牌小區域）。
  3. 把現有「整串字串多數決」改成「逐字元位置 + 信心加權」投票，並以相同長度為前提。
  4. 超解析：OpenCV contrib `cv2.dnn_superres`（`pip install opencv-contrib-python`）可載入 EDSR/ESPCN/FSRCNN；
     這些 .pb 權重在 GitHub 上公開，但本次未查到確切 release 網址，需自行確認。HAT 權重多在 Google Drive/HF，可能取不到。
- 風險：GAN 超解析可能「幻想」出錯誤數字；建議只用輕量 SR 或雙三次放大 + 銳化，並用 A/B 測試驗證。

### B3. 零樣本／開放詞彙偵測找號碼牌

- **YOLOE（ultralytics，`pip install ultralytics`）**：權重在 GitHub releases，例如
  `https://github.com/ultralytics/assets/releases/download/v8.4.0/yoloe-26s-seg.pt`；`model.set_classes(["race bib"])`。
  - 文字提示首次需從 GitHub pip 安裝 `ultralytics/CLIP`，並下載 MobileCLIP 文字編碼器（`mobileclip2_b.ts` 約 254 MB）；
    下載來源文件未明寫，可能不通。對策：在能連網處先 `save_prompt_embeddings()`，之後 `load_prompt_embeddings()`／匯出，部署端就不需文字編碼器。
  - CPU：文件稱 n/s 可在 CPU 低解析度跑；只在 YOLO 找到的人體軀幹裁切上跑可大幅省時。
- **YOLO-World（ultralytics）**：類似，同樣需 CLIP 文字編碼器；未另行查證下載來源。
- **Grounding DINO**：權重 `https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth`，
  支援 `--cpu-only`；但（依既有了解，本次頁面未確認）其文字編碼器 `bert-base-uncased` 預設從 Hugging Face 下載 → 在本環境大概率不可行，且 CPU 每張數秒，不適合影片。
- 整體風險：「bib」不是常見詞彙，零樣本召回不穩；但專題已有軀幹裁切 + PP-OCR 文字偵測，零樣本偵測的邊際效益可能有限，建議只當「縮小 OCR 區域」的實驗。

### B4. 已公開的號碼牌偵測權重

- 搜尋中**沒找到放在 GitHub releases 的現成權重**；找到的是放在 repo 內的 Darknet 權重：
  - ericBayless/bib-detector（MIT）：`Data/YOLO/bib_detector/RBNR2_custom-yolov4-tiny-detector_best.weights`；
    訓練資料為 RBNR set1+2，**原始 127 張**，擴增至 5,088 張；另有 SVHN 訓練的數字讀取器。
  - Lwhieldon/BibObjectDetection：`weights-classes/RBNR_custom-yolov4-tiny-detector_best.weights`（RBNR，自稱 mAP 約 99%）與 SVHN 權重；未寫張數。
- 取得：從 GitHub repo 直接下載檔案；OpenCV `cv2.dnn.readNetFromDarknet` 即可在 CPU 跑 YOLOv4-tiny（很快）。
- 風險：資料極少（RBNR 全集僅 217 張、290 個號碼牌）、非台灣號碼牌樣式、終點遠景小號碼牌未必能抓到；mAP 99% 是同分布測試，不可信為泛化能力。
  另有 YOLOv8 號碼牌論文（BDBD+SVHN 訓練）在 TGCRBNW 資料集多數 < 50%，未見公開權重。Roboflow Universe 有許多資料集/模型，但需 Roboflow API，不在限制內。

## 建議優先順序（CPU、免訓練）
1. 加入 OnnxTR PARSeq（8-bit）作第二辨識器，與 PP-OCR 逐字元信心投票。
2. track 內挑清晰格 + ECC 對齊融合，再送 OCR。
3. 換 `onnxocr-ppocrv5` 比較 v4/v5。
4. 零樣本偵測與 YOLOv4-tiny 號碼牌權重僅作對照實驗。

## 資料來源
- YouTube 搜尋結果：上表各影片網址；萬金石／田中馬頻道網址見 A 節
- https://pypi.org/project/onnxtr/
- https://github.com/felixdittrich92/OnnxTR/releases
- https://raw.githubusercontent.com/felixdittrich92/OnnxTR/main/onnxtr/models/recognition/models/parseq.py
- https://pypi.org/project/onnxocr-ppocrv5/
- https://docs.rs/crate/oar-ocr/0.8.1/source/docs/models.md
- https://docs.ultralytics.com/models/yoloe
- https://github.com/idea-research/groundingdino
- https://arxiv.org/pdf/2607.08896
- https://github.com/ericBayless/bib-detector
- https://gh.r-mj.com/Lwhieldon/BibObjectDetection （github.com/Lwhieldon/BibObjectDetection 鏡像）
- https://oa.upm.es/87873/
- 未能讀取：YouTube 各影片頁（無法取得長度／解析度）、https://github.com/Kefabd/Athlete-LENS（rate limit）
