# fm.tick.analysis — 實作規格 / Implementation Specification

> 版本 Version：v2（2026-05-31）  
> 腳本 Script：`/workspace/.claude/commands/fm.tick.analysis.py`  
> 技能定義 Skill：`/workspace/.claude/commands/fm.tick.analysis.md`

---

## 1. 概述 / Overview

| 中文 | English |
|------|---------|
| 對台股指定標的擷取 FinMind `TaiwanStockPriceTick` 逐筆成交資料，執行完整的成交量統計與主力行為分析，同時產生 PNG 圖表與 HTML 報表。 | Fetches FinMind `TaiwanStockPriceTick` tick-by-tick data for a given Taiwan stock, performs full volume statistics and major-player behaviour analysis, and generates both a PNG chart and an HTML report. |

---

## 2. 執行方式 / Invocation

```bash
~/.local/bin/uv run --python finmind python \
  /workspace/.claude/commands/fm.tick.analysis.py <SID_OR_NAME> [DATE_SPEC]
```

### 2.1 輸入參數 / Input Parameters

| 參數 Parameter | 型別 Type | 必填 Required | 說明 Description |
|---------------|-----------|:---:|-----------------|
| `SID_OR_NAME` | `str` | ✓ | 股票代號（`2330`）或中文名稱（`台積電`、`群光`）。支援完全符合與部分符合。 / Stock ID (`2330`) or Chinese name. Supports exact and partial match. |
| `DATE_SPEC` | `str` | — | 日期規格，見下表。省略時自動尋找最近有資料的交易日。 / Date spec, see table below. Omit to auto-find the most recent trading day with data. |

### 2.2 日期規格 / Date Specification

| 輸入 Input | 行為 Behaviour |
|-----------|---------------|
| 省略 *(omitted)* | 從 `TODAY`（`2026-05-31`）往前最多 30 個自然日，取第 1 個有 Tick 資料的交易日 / Scans backward up to 30 days, returns the 1st trading day with tick data |
| `YYYY-MM-DD` | 指定日期；若無資料則報錯退出 / Exact date; exits with error if no data found |
| 正整數 `N` *(positive integer)* | 往前找第 N 個有 Tick 資料的交易日（`1`=最近，`2`=次近） / Returns the Nth most recent trading day with data |

---

## 3. 環境依賴 / Environment

| 項目 Item | 說明 Description |
|----------|-----------------|
| Python venv | `finmind`（`/workspace/finmind`） |
| 環境變數 Env var | `FINMIND_TOKEN`（Bearer token for FinMind API） |
| 套件 Packages | `pandas`, `numpy`, `matplotlib`, `requests` |
| 字型 Font | WQY Zen Hei / Noto Sans CJK（自動偵測 auto-detected） |

---

## 4. 資料來源 / Data Sources

| Dataset | 用途 Purpose |
|---------|-------------|
| `TaiwanStockInfo` | 解析股票代號 ↔ 中文名稱、市場分類（twse/otc）、產業別 / Resolve stock ID ↔ name, market type, industry |
| `TaiwanStockPriceTick` | 逐筆成交資料：`date`, `stock_id`, `deal_price`, `volume`, `Time`, `TickType` / Tick-by-tick trades |

> `TaiwanStockPriceTick` 需要 **Sponsor tier** 訂閱。/ Requires Sponsor tier subscription.

---

## 5. 分析流程 / Analysis Pipeline

```
原始資料讀入
  → sort_values("Time")
  → volume / deal_price 轉數值型態
  → amount = deal_price × volume
  → stdout 分叉至 _Tee（端末 + StringIO 緩衝）
  → 各分析區段依序執行並 print
  → stdout 還原
  → 讀取緩衝 → 產生 HTML 報表
```

---

## 6. 分析區段 / Analysis Sections

### 6.1 基本資訊 / Basic Information

| 欄位 Field | 說明 Description |
|-----------|-----------------|
| 資料集名稱 | `TaiwanStockPriceTick` |
| 股票代號 / 中文名稱 | 解析後的 ID 與名稱 |
| 市場分類 | `twse`（上市）/ `otc`（上櫃） |
| 產業別 | FinMind `industry_category` |
| 日期 | 實際取得資料的交易日 |
| 所有欄位 | DataFrame 欄位列表 |
| 總筆數 | 當日逐筆資料筆數 |
| 缺值統計 | 各欄缺值數（無缺值則顯示「無缺值」） |

---

### 6.2 描述性統計 / Descriptive Statistics（volume，單位：張）

| 統計量 Statistic | 說明 Description |
|----------------|-----------------|
| mean | 算術平均 / Arithmetic mean |
| median | 中位數 / Median |
| mode | 眾數 / Mode（第一個） |
| std | 標準差 / Standard deviation |
| var | 變異數 / Variance |
| min / max / range | 最小、最大、全距 |
| skewness | 偏態係數 / Skewness |
| kurtosis | 超額峰態（excess kurtosis） |
| P25 / P50 / P75 / P90 / P95 / P99 | 百分位數 / Percentiles |

---

### 6.3 成交量分佈 / Volume Distribution

8 個固定區間 / 8 fixed bins：

| 區間 Bin | 代表 Represents |
|---------|----------------|
| =1 | 單張 / Single lot |
| =2 | 兩張 |
| 3–5 | 小型散戶 / Small retail |
| 6–10 | |
| 11–20 | |
| 21–50 | 中型 / Medium |
| 51–100 | 準大單 / Near-large |
| >100 | 大單 / Large order |

每個區間輸出 / Per-bin output：**筆數、筆數佔比%、量總和、量佔比%、金額總和、金額佔比%**

---

### 6.4 圖表輸出 / Chart Output（PNG）

三子圖並排 / Three subplots (1×3)，`figsize=(20, 7)`，`dpi=150`

| 位置 Position | 類型 Type | 內容 Content |
|--------------|-----------|-------------|
| 左 Left（ax1） | Bar chart | 各量區間 Tick 筆數；每柱標示筆數＋佔比 / Tick count per volume bin, labeled with count & % |
| 中 Center（ax2） | Pie chart | 各量區間**成交量佔比**（張數）/ Volume share (lots) by bin |
| 右 Right（ax3） | Bar chart | **成交價區間 vs 成交量**；x 軸=成交價（元），y 軸=成交量（張），每柱標示量＋佔比；價格檔位 ≤20 時以實際價格為 x 軸，>20 時自動分約 15 個 bin / Volume by price level; auto-bins when >20 distinct prices |

**儲存路徑**：`/workspace/playground/{stock_id}_full_volume_analysis.png`

---

### 6.5 總計與大單分析 / Total Volume & Large Order Analysis

| 輸出 Output | 說明 Description |
|------------|-----------------|
| 當日總成交量 | `tick_df["volume"].sum()` |
| 大單筆數 | `count(volume ≥ 100)` |
| 大單量佔比 | `big_vol / total_vol × 100` |
| 前 5 大單明細 | `Time`, `deal_price`, `volume`, `TickType`，依 volume 降冪 |

> 大單門檻固定 100 張，不隨個股調整。/ Fixed threshold of 100 lots.

---

### 6.6 主力分析 / Major Player Analysis

#### 門檻計算 / Threshold Calculation

```
major_thr = max(10, round(P95 × 10))
```

> 動態閾值，隨當日流動性（P95 百分位）自動調整，最低 10 張。  
> Dynamic threshold based on daily P95; floor at 10 lots.

#### 輸出指標 / Output Metrics

| 指標 Metric | 計算 Formula | 說明 Description |
|------------|-------------|-----------------|
| 主力大單筆數 | `count(volume ≥ thr)` | |
| 主力量佔比 | `major_vol / total_vol × 100` | |
| 主動買進比 | `buy_vol / major_vol × 100` | TickType=1（外盤，主動買 / buyer-initiated） |
| 主動賣出比 | `sell_vol / major_vol × 100` | TickType=2（內盤，主動賣 / seller-initiated） |
| 主力集中度 | `top5_vol / major_vol × 100` | 前 5 大主力單佔主力量比例 |
| 主力 VWAP | `Σ(price×vol) / major_vol` | 所有大單加權均價 |
| 買進成本（外盤均價） | `buy_amount / buy_vol` | 外盤大單加權均價 |
| 賣出均價（內盤均價） | `sell_amount / sell_vol` | 內盤大單加權均價 |
| 淨部位成本 | `(buy_amount − sell_amount) / (buy_vol − sell_vol)` | 淨買進時為建倉均價；淨賣出時為出貨均價 |
| 主力傾向 | buy_ratio ≥ 60% → 偏多；sell_ratio ≥ 60% → 偏空；otherwise → 均衡 | |

---

### 6.7 逐筆交易 — 開收盤各5筆 / First & Last 5 Ticks

| 區段 Section | 資料 Data |
|-------------|----------|
| 開盤前5筆 | `tick_df[ALL_COLS].head(5)`（時間排序後前 5 筆） |
| 收盤後5筆 | `tick_df[ALL_COLS].tail(5)`（時間排序後末 5 筆） |

`ALL_COLS = ["date", "stock_id", "deal_price", "volume", "Time", "TickType"]`

---

### 6.8 重點解讀 / Key Insights（①～⑥）

| 序號 | 項目 | 條件邏輯 / Decision Logic |
|-----|------|--------------------------|
| ① | 偏態分析 Skewness | skewness > 2 → 高度右偏；0.5~2 → 中度右偏；< 0.5 → 偏態低。kurtosis > 5 → 尖峰厚尾（主力跡象）；1~5 → 輕度尖峰；< 1 → 平峰 |
| ② | 中位數/眾數 Median/Mode | mode ≤ 2 且 median ≤ 5 → 散戶主導；mode ≤ 10 → 小額散戶；otherwise → 法人/主力高度參與 |
| ③ | 最大單 Largest Order | 顯示量、時間、價、TickType、佔比；Time ≥ 13:25 → 收盤撮合；Time ≤ 09:05 → 開盤競價；否則 → 盤中主力 |
| ④ | 開收盤價格變化 Price Change | 第一筆 deal_price → 開盤；最後一筆 → 收盤；計算漲跌金額與百分比，顯示 TickType |
| ⑤ | 量價背離 Count/Volume Divergence | 計算各區間 `abs(量佔比% − 筆數佔比%)`；取差異最大區間，量佔比 > 筆數佔比 → 主力集中大筆；反之 → 散戶零碎 |
| ⑥ | 主力成本價解讀 Major Player Cost | 計算 spread = 賣出均價 − 買進成本；淨賣出且 spread > 0 → 獲利出貨；淨賣出且 spread < 0 → 虧損止損；淨買進 → 顯示建倉成本與收盤浮盈 |

---

## 7. 輸出檔案 / Output Files

| 檔案 File | 路徑 Path | 說明 Description |
|----------|-----------|-----------------|
| PNG 圖表 | `/workspace/playground/{stock_id}_full_volume_analysis.png` | 三子圖分析圖表 |
| HTML 報表 | `/workspace/logs/{stock_id}_full_volume_analysis.html` | 自包含報表，含圖表（base64 嵌入）、摘要卡片、重點解讀、原始輸出 |

---

## 8. HTML 報表結構 / HTML Report Structure

HTML 為**單一自包含檔案**（圖片以 base64 嵌入，無外部資源依賴）。  
The HTML is a **self-contained single file** (image embedded as base64, no external dependencies).

| 區塊 Section | 版型 Layout | 說明 Description |
|-------------|-------------|-----------------|
| Header | 全寬 full-width | 股號、名稱、日期、市場、產業、總筆數、總成交量 |
| 成交量分析圖表 | 全寬 | PNG 以 `<img src="data:image/png;base64,...">` 嵌入 |
| 價格與基本統計 | grid-2 左 | 開收盤（含漲跌色彩 ▲▼）、mean/median/mode/std/skew/kurt |
| 主力分析 | grid-2 右 | 門檻、量佔比、買賣比、VWAP、成本價、淨部位、傾向 badge（偏多/偏空/均衡） |
| 重點解讀 | ins-grid 2×2 | ①偏態、②中位數/眾數、③最大單、⑤量價背離（④⑥資訊已在上方卡片，不重複） |
| 原始輸出 | 全寬 | 完整 terminal 文字，白底黑字等寬字型，含邊框 |

### 8.1 重點解讀顏色規則 / Insight Colour Coding

| 顏色 Colour | CSS class | 使用情境 When Used |
|------------|-----------|-------------------|
| 🔴 紅 Red | `.txt-red` | 警示：主力佈局跡象（高 kurtosis）、法人/主力高度參與、盤中大量異常、量佔比高度集中 |
| 🔵 藍 Blue | `.txt-blue` | 中性資訊：散戶主導、開盤競價、量分佈均勻、量佔比正常 |
| 🟢 綠 Green | `.txt-green` | 均衡訊號：偏態低，法人穩定參與 |
| 🟠 橙 Amber | `.txt-amber` | 次要注意：輕度尖峰、中型法人偶入、收盤撮合大單 |

---

## 9. 技術實作細節 / Technical Implementation Notes

| 項目 Item | 說明 Description |
|----------|-----------------|
| stdout 雙寫 Tee | `_Tee` 類別同時寫至端末與 `io.StringIO`；分析完成後還原 stdout，讀取緩衝內容填入 HTML 原始輸出區塊 / `_Tee` writes to both terminal and buffer; buffer content becomes the HTML raw output block |
| 成交價分 bin | 成交價檔位 ≤20：直接以實際價格為 x 軸；>20：`bin_size = round((max−min)/15)`，自動合併 / ≤20 distinct prices: use as-is; >20: auto-bin into ~15 buckets |
| 主力門檻下限 | `max(10, round(P95×10))`，避免低流動性個股門檻過低 / Floor at 10 lots to prevent under-thresholding for illiquid stocks |
| TickType 語義 | `1` = 外盤（主動買，買方掛市價）= buyer-initiated uptick；`2` = 內盤（主動賣）= seller-initiated downtick |
| HTML 特殊字元 | raw output 的 `&`, `<`, `>` 以 `str.replace()` 手動轉義（不依賴 `html` 模組） / Manual HTML-escaping via `str.replace()` |
| 圖片嵌入 | PNG 儲存後以 `base64.b64encode` 讀入並嵌入 `<img src="data:image/png;base64,...">` |
