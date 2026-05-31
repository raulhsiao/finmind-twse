# TaiwanStockPriceTick 逐筆成交量分析 Prompt

---

## 中文版

```
STOCK_ID = 2385

使用 FinMind API TaiwanStockPriceTick（歷史逐筆交易）對股票代號 {STOCK_ID} 進行完整的逐筆成交量分析。
```

### 步驟

1. 先查詢 `TaiwanStockInfo` 取得該股票的中文名稱、市場分類（TWSE/TPEx）、產業別。
2. 查詢 `TaiwanStockPriceTick`，`start_date` 自動尋找最近一個有資料的交易日（從今日往前逐日試查）。
3. 取出所有逐筆資料，無需處理，依 `Time` 欄位排序。

---

### 輸出內容與格式

#### HEAD 5 / TAIL 5

列印完整欄位（`date`, `stock_id`, `deal_price`, `volume`, `Time`, `TickType`）的前 5 筆與後 5 筆。

#### 基本資訊

- 資料集名稱、股票代號、中文名稱、市場分類、產業別、日期、所有欄位、總筆數、缺值數

#### 描述性統計（針對 `volume` 欄位）

- `mean`、`median`、`mode`、`std`、`var`、`min`、`max`、`range`、`skewness`、`kurtosis`
- 百分位數：P25、P50、P75、P90、P95、P99

#### 成交量分佈

文字表格，欄位如下：

| 欄位 | 說明 |
|------|------|
| 區間 | `=1`, `=2`, `3-5`, `6-10`, `11-20`, `21-50`, `51-100`, `>100` |
| 筆數 | 該區間的 Tick 筆數 |
| 筆數佔比 | 筆數 / 總筆數 |
| 量總和 | 該區間的成交量加總（張） |
| 量佔比 | 量總和 / 當日總量 |

圖表（左右並排，中文標題與標籤）：

- **左：Bar chart**
  - x-axis = 成交量區間
  - y-axis = Tick 筆數
  - 每柱標示筆數與百分比

- **右1：Pie chart（成交量佔比）**
  - 以 Bar chart 的 x-axis 各區間為索引
  - 計算每區間的成交量總和（張數）
  - 標示各區間名稱與百分比

- **右2：Pie chart（成交金額佔比）**
  - 以 Bar chart 的 x-axis 各區間為索引
  - 對每一筆 tick **個別**計算 `deal_price × volume`（逐筆計算，非區間簡化）
  - 再依區間加總，標示各區間名稱與百分比

#### 總計與大單分析

- 當日總成交量
- 大單（≥ 100 張）筆數與量佔比
- 前 5 大單：`Time`, `deal_price`, `volume`, `TickType`

#### 逐筆交易 — 開收盤各一筆

| | 欄位 |
|-|------|
| 開盤第一筆 | `date`, `stock_id`, `deal_price`, `volume`, `Time`, `TickType` |
| 收盤最後一筆 | `date`, `stock_id`, `deal_price`, `volume`, `Time`, `TickType` |

#### 重點解讀（依實際數據動態生成）

1. **偏態分析**：依 `skewness` / `kurtosis` 判斷分佈形態，說明散戶 vs 法人結構
2. **中位數 / 眾數**：說明典型交易規模與主導者
3. **最大單分析**：說明最大單筆數、時間、量佔比，判斷是否為收盤撮合
4. **開收盤價格變化**：漲跌幅、TickType 方向
5. **量價背離觀察**：找出量佔比 vs 筆數佔比差異最大的區間，說明法人/主力佈局特徵

---

### 技術規範

| 項目 | 規格 |
|------|------|
| 語言與套件 | Python：`requests` + `pandas` + `matplotlib`，使用 `finmind` venv |
| 圖表字型 | `/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc`（WenQuanYi 中文字型）|
| 右2 金額計算 | 必須逐筆計算：`tick_df["amount"] = tick_df["deal_price"] * tick_df["volume"]`，再對各區間內的 `amount` 欄位加總，**不得**使用區間平均價格簡化 |
| 圖表輸出路徑 | `/workspace/playground/{STOCK_ID}_full_volume_analysis.png` |

---
---

## English Version

```
STOCK_ID = 2385

Perform a complete tick-by-tick volume analysis for stock {STOCK_ID} using the FinMind API
dataset TaiwanStockPriceTick (historical tick trades).
```

### Steps

1. Query `TaiwanStockInfo` to retrieve the stock's Chinese name, market classification (TWSE/TPEx), and industry category.
2. Query `TaiwanStockPriceTick`. Automatically find the most recent trading day with available data by probing backward from today one day at a time (skip weekends).
3. Load all tick records and sort by the `Time` column. No other preprocessing needed.

---

### Output Sections

#### HEAD 5 / TAIL 5

Print the first 5 and last 5 rows with all columns:
`date`, `stock_id`, `deal_price`, `volume`, `Time`, `TickType`.

#### Basic Information

- Dataset name, stock ID, Chinese name, market classification, industry, date, all column names, total row count, null value counts.

#### Descriptive Statistics (`volume` column only)

- `mean`, `median`, `mode`, `std`, `var`, `min`, `max`, `range`, `skewness`, `kurtosis`
- Percentiles: P25, P50, P75, P90, P95, P99

#### Volume Distribution

Print a text table with the following bins and columns:

| Column | Description |
|--------|-------------|
| Bin | `=1`, `=2`, `3-5`, `6-10`, `11-20`, `21-50`, `51-100`, `>100` |
| Tick Count | Number of ticks in each bin |
| Count % | Tick count / total ticks |
| Volume Sum | Total volume (lots) in each bin |
| Volume % | Volume sum / total daily volume |

Chart (side by side, all titles and labels in **Chinese**):

- **Left: Bar chart**
  - x-axis = volume bin
  - y-axis = tick count
  - Annotate each bar with its count and percentage

- **Right 1: Pie chart (volume share)**
  - Index by the same volume bins as the bar chart
  - Compute the sum of volume (lots) per bin
  - Label each slice with bin name and percentage

- **Right 2: Pie chart (trade amount share)**
  - Index by the same volume bins as the bar chart
  - Compute trade amount by multiplying `deal_price × volume` on **every individual tick** first (per-tick calculation — do **not** use a simplified bin-average price)
  - Then sum the per-tick amounts within each bin
  - Label each slice with bin name and percentage

#### Summary & Block Trade Analysis

- Total daily volume
- Block trade (≥ 100 lots) count and volume share
- Top-5 block trades: `Time`, `deal_price`, `volume`, `TickType`

#### Opening and Closing Ticks

| | Columns |
|-|---------|
| First tick of the day | `date`, `stock_id`, `deal_price`, `volume`, `Time`, `TickType` |
| Last tick of the day | `date`, `stock_id`, `deal_price`, `volume`, `Time`, `TickType` |

#### Key Insights (dynamically generated from actual data)

1. **Skewness analysis**: interpret distribution shape from `skewness` / `kurtosis`; characterize retail vs. institutional trading structure.
2. **Median / mode**: describe the typical trade size and dominant participant type.
3. **Largest block trade**: timestamp, volume, volume share; assess whether it is a closing auction match.
4. **Open-to-close price change**: absolute and percentage change, TickType direction.
5. **Volume-price divergence**: identify the bin where the gap between volume % and count % is largest; interpret institutional / major-player positioning.

---

### Technical Specifications

| Item | Specification |
|------|---------------|
| Language / Libraries | Python with `requests`, `pandas`, `matplotlib`; use `finmind` venv |
| Chinese font for charts | `/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc` (WenQuanYi) |
| Right 2 amount calculation | **Must** be computed per tick: `tick_df["amount"] = tick_df["deal_price"] * tick_df["volume"]`, then aggregate `amount` by bin — do **not** use a simplified bin-average price |
| Chart output path | `/workspace/playground/{STOCK_ID}_full_volume_analysis.png` |


# 把以上的功能整理成 skill 'fm.tick.analysis' ，輸入參數可以是交易對象編號或中文名稱，日期可以是指定過去的交易天數或是內建值最近一天的交易日