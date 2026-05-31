# fm.tick.analysis — 實作 Prompt（中英文對照）
# fm.tick.analysis — Implementation Prompt (Bilingual)

> 此 prompt 可完整重現 `/workspace/.claude/commands/fm.tick.analysis.py` 的現行功能。  
> This prompt fully reproduces the current behaviour of `/workspace/.claude/commands/fm.tick.analysis.py`.

---

## 任務概述 / Task Overview

使用 FinMind API 對指定台股標的擷取 `TaiwanStockPriceTick`（歷史逐筆交易）資料，執行完整的成交量統計分析與主力行為分析，並輸出 PNG 圖表與 HTML 報表。

Use the FinMind API to fetch `TaiwanStockPriceTick` (historical tick trades) data for a specified Taiwan stock, perform full volume statistics and major-player behaviour analysis, then output a PNG chart and an HTML report.

---

## 一、輸入規格 / Input Specification

### 1.1 CLI 參數 / CLI Arguments

```
python fm.tick.analysis.py <SID_OR_NAME> [DATE_SPEC]
```

| 參數 Param | 必填 Required | 說明 Description |
|-----------|:---:|---------|
| `SID_OR_NAME` | ✓ | 股票代號（`2330`）或中文名稱（`台積電`、`群光`）/ Stock ID or Chinese name |
| `DATE_SPEC` | — | 日期規格，見下表 / Date spec, see below |

### 1.2 日期規格 / Date Specification

| 輸入 Input | 行為 Behaviour |
|-----------|---------------|
| 省略 *(omitted)* | 從今日往前最多 30 個自然日，自動找第 1 個有 Tick 資料的交易日（跳過週六日）/ Auto-find the most recent trading day with data (skip weekends) |
| `YYYY-MM-DD` | 指定日期，無資料則報錯退出 / Exact date; error-exit if no data |
| 正整數 `N` | 往前第 N 個有 Tick 資料的交易日（`1`=最近，`2`=次近）/ Nth most-recent trading day with data |

### 1.3 股票名稱解析優先順序 / Stock Name Resolution Priority

1. `stock_id` 完全符合 exact match
2. `stock_name` 完全符合 exact match
3. `stock_name` 部分符合（`str.contains`），取第一筆 partial match, first result

---

## 二、環境 / Environment

| 項目 Item | 規格 Specification |
|----------|-------------------|
| Python venv | `finmind`（`~/.local/bin/uv run --python finmind python ...`） |
| 環境變數 Env var | `FINMIND_TOKEN`（FinMind Bearer token） |
| 套件 Packages | `pandas`, `numpy`, `matplotlib`, `requests`, `io`, `base64` |
| 中文字型 CJK font | `/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc`，或 `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc` |
| 圖表後端 Backend | `matplotlib.use("Agg")`（無視窗環境）/ headless |

---

## 三、資料擷取 / Data Fetching

### 3.1 股票基本資訊

```python
GET TaiwanStockInfo
# 用於解析 stock_id ↔ stock_name, type (twse/otc), industry_category
```

### 3.2 逐筆成交資料

```python
GET TaiwanStockPriceTick
params: data_id=stock_id, start_date=date_str, end_date=date_str
```

取得後：
1. 依 `Time` 欄位升序排列 / sort ascending by `Time`
2. `volume`、`deal_price` 轉數值型態（`pd.to_numeric(errors="coerce")`）
3. 新增欄位：`amount = deal_price × volume`（逐筆計算，非區間均價）/ per-tick calculation

---

## 四、stdout 捕獲機制 / stdout Capture

在分析開始前建立 `_Tee` 類別，同時寫至端末（terminal）與 `io.StringIO` 緩衝：

Before analysis begins, create a `_Tee` class that writes simultaneously to both the terminal and an `io.StringIO` buffer:

```python
class _Tee:
    def __init__(self, *streams): self.streams = streams
    def write(self, data):
        for s in self.streams: s.write(data)
    def flush(self):
        for s in self.streams: s.flush()

_orig_stdout = sys.stdout
_buf = io.StringIO()
sys.stdout = _Tee(_orig_stdout, _buf)
```

分析結束後還原 stdout，讀取 `_buf.getvalue()` 作為 HTML 報表的「原始輸出」區塊。  
After analysis, restore stdout and use `_buf.getvalue()` as the raw-output section of the HTML report.

---

## 五、分析區段輸出 / Analysis Output Sections

各區段以 `"═" × 70` 分隔線分隔。/ Sections separated by `"═" × 70`.

---

### 5.1 基本資訊 / Basic Information

輸出以下欄位 / Output the following fields:

```
資料集名稱  : TaiwanStockPriceTick
股票代號    : {stock_id}
中文名稱    : {stock_name}
市場分類    : {market_type}        # twse 或 otc
產業別      : {industry}
日期        : {found_date}
所有欄位    : {list(tick_df.columns)}
總筆數      : {total_rows:,}
缺值統計    : 無缺值 / 或各欄缺值數
```

---

### 5.2 描述性統計 / Descriptive Statistics（volume，單位：張）

計算並輸出以下統計量 / Compute and print:

| 統計量 | 計算 |
|--------|------|
| mean | `vol.mean()` |
| median | `vol.median()` |
| mode | `vol.mode().iloc[0]` |
| std | `vol.std()` |
| var | `vol.var()` |
| min / max / range | `vol.min()`, `vol.max()`, `max - min` |
| skewness | `vol.skew()` |
| kurtosis | `vol.kurt()` (excess kurtosis) |
| P25 / P50 / P75 / P90 / P95 / P99 | `vol.quantile([.25, .50, .75, .90, .95, .99])` |

---

### 5.3 成交量分佈 / Volume Distribution

以下 8 個固定區間 / 8 fixed bins:

```
=1 | =2 | 3-5 | 6-10 | 11-20 | 21-50 | 51-100 | >100
```

每個區間計算 / Per bin compute:

| 欄位 Column | 計算 Formula |
|------------|-------------|
| 筆數 | `count` |
| 筆數佔比% | `count / total_rows × 100` |
| 量總和 | `sum(volume)` |
| 量佔比% | `sum(volume) / total_vol × 100` |
| 金額總和 | `sum(amount)`（逐筆 `deal_price × volume`） |
| 金額佔比% | `sum(amount) / total_amt × 100` |

輸出為對齊文字表格（`DataFrame.to_string(index=False)`）。  
Print as aligned text table using `DataFrame.to_string(index=False)`.

---

### 5.4 圖表 / Charts

**三子圖並排（1×3），figsize=(20, 7)，dpi=150**  
**Three subplots (1×3), figsize=(20, 7), dpi=150**

標題格式 / suptitle: `"{stock_id} {stock_name}  逐筆成交量分析  {found_date}"`

#### 左（ax1）：Tick 筆數 Bar chart

- x-axis = 成交量區間（張）/ volume bins
- y-axis = Tick 筆數 / tick count
- 每柱標示：筆數 + 百分比 / each bar labeled with count & %
- color = `#4C72B0`

#### 中（ax2）：成交量佔比 Pie chart

- 各區間成交量（張數）佔比 / volume share by bin (lots)
- 去除量為 0 的區間 / exclude zero-volume bins
- `autopct` 顯示佔比 > 1% 的 slice / show % only for slices > 1%

#### 右（ax3）：成交價區間成交量 Bar chart

- x-axis = 成交價（元）/ deal price levels
- y-axis = 成交量（張）/ volume (lots)
- 每柱標示：量 + 百分比 / each bar labeled with volume & %
- color = `#55A868`
- **自動分 bin 規則 / Auto-binning rule**:
  - 若成交價檔位 ≤ 20：直接以實際成交價為 x 軸 / use exact prices as x-axis
  - 若 > 20：`bin_size = max(1, round((max_price - min_price) / 15))`，合併為約 15 個 bin / merge into ~15 bins

**儲存路徑 / Save path**: `/workspace/playground/{stock_id}_full_volume_analysis.png`

---

### 5.5 總計與大單分析 / Total Volume & Block Trade Analysis

```
當日總成交量        : {total_volume:,} 張
大單（≥100張）筆數  : {big_cnt:,} 筆
大單量佔比          : {big_vol:,} 張 / {pct:.2f}%

前5大單：
Time | deal_price | volume | TickType   （依 volume 降冪）
```

> 大單門檻固定 100 張。/ Fixed threshold of 100 lots.

---

### 5.6 主力分析 / Major Player Analysis

#### 動態門檻計算 / Dynamic Threshold

```python
major_thr = max(10, int(round(float(P95) * 10)))
```

P95 為當日成交量的第 95 百分位數，最低 10 張。  
P95 is the 95th percentile of daily volume; floor at 10 lots.

#### 輸出指標 / Output Metrics

```
主力門檻（P95×10）     : {major_thr:,} 張
主力大單筆數           : {major_cnt:,} 筆
主力量                 : {major_vol:,} 張 / {major_pct:.2f}%（佔當日總量）
主力主動買進比         : {buy_ratio:.2f}%  （TickType=1 外盤）
主力主動賣出比         : {sell_ratio:.2f}%  （TickType=2 內盤）
主力集中度（前5大單）  : {top5_vol:,} 張 / {concentration:.2f}%（佔主力量）
── 成本價 ──
主力 VWAP（大單加權均價）: {major_vwap:.2f} 元
主力買進成本（外盤均價）: {buy_vwap:.2f} 元  ×  {buy_vol:,} 張
主力賣出均價（內盤均價）: {sell_vwap:.2f} 元  ×  {sell_vol:,} 張
主力淨部位成本         : 淨買進/淨賣出 {abs(net_vol_cost):,} 張 @ {net_cost:.2f} 元

前5大主力單：
Time | deal_price | volume | TickType   （依 volume 降冪）

主力傾向：
  buy_ratio ≥ 60%  → 偏多（主力積極買入）
  sell_ratio ≥ 60% → 偏空（主力積極賣出）
  otherwise        → 買賣均衡
```

#### TickType 語義 / TickType Semantics

| TickType | 中文 | English |
|---------|------|---------|
| `1` | 外盤（主動買，買方掛市價） | Uptick — buyer-initiated |
| `2` | 內盤（主動賣，賣方掛市價） | Downtick — seller-initiated |

#### 成本計算公式 / Cost Calculation

```python
buy_amount   = Σ(deal_price × volume)  for TickType=1 major trades
sell_amount  = Σ(deal_price × volume)  for TickType=2 major trades
major_vwap   = Σ(all major amount) / major_vol
buy_vwap     = buy_amount  / buy_vol   # NaN if buy_vol == 0
sell_vwap    = sell_amount / sell_vol  # NaN if sell_vol == 0
net_vol_cost = buy_vol - sell_vol
net_cost     = (buy_amount - sell_amount) / net_vol_cost  # NaN if net_vol_cost == 0
```

---

### 5.7 逐筆交易 — 開收盤各5筆 / First & Last 5 Ticks

```
開盤前5筆：
tick_df[["date","stock_id","deal_price","volume","Time","TickType"]].head(5)

收盤後5筆：
tick_df[["date","stock_id","deal_price","volume","Time","TickType"]].tail(5)
```

開收盤價格取自第一筆 / 最後一筆的 `deal_price`，用於重點解讀④與HTML摘要。  
Open / close prices are taken from first / last tick's `deal_price`, used in insight ④ and the HTML summary.

---

### 5.8 重點解讀 / Key Insights（①～⑥）

#### ① 偏態分析（Skewness / Kurtosis）

```
skewness > 2     → 高度右偏，散戶小單主導
skewness 0.5~2   → 中度右偏，法人間歇性大單
skewness < 0.5   → 偏態低，法人參與度較高

kurtosis > 5     → 尖峰厚尾，極端大單頻率高，存在主力佈局跡象
kurtosis 1~5     → 輕度尖峰，偶有較大單
kurtosis < 1     → 平峰，各規模成交均勻
```

#### ② 中位數 / 眾數（Median / Mode）

```
mode ≤ 2 且 median ≤ 5  → 典型規模極小，散戶主導
mode ≤ 10               → 小額散戶為主，偶有中型法人
otherwise               → 眾數偏大，法人/主力參與程度較高
```

#### ③ 最大單分析（Largest Single Order）

顯示：量（張）、時間、成交價、TickType、佔當日總量%

```
Time ≥ "13:25"  → 時間接近收盤，可能為收盤撮合或尾盤大量對敲
Time ≤ "09:05"  → 時間接近開盤，屬開盤集合競價大量成交
otherwise       → 時間位於盤中，為主力或法人積極買賣之跡象
```

#### ④ 開收盤價格變化（Open-to-Close Price Change）

```
顯示：開盤價 → 收盤價，漲跌金額（元），漲跌幅（%）
顯示：開盤 TickType，收盤 TickType
```

#### ⑤ 量價背離觀察（Volume / Count Divergence）

```python
distro["差異"] = abs(distro["量佔比%"] - distro["筆數佔比%"])
top_d = distro.sort_values("差異", ascending=False).iloc[0]
# 取差異最大區間
```

```
量佔比% > 筆數佔比% → 少量筆數貢獻大量成交，法人/主力集中大筆佈局
量佔比% < 筆數佔比% → 筆數多但量小，散戶零碎進出
```

#### ⑥ 主力成本價解讀（Major Player Cost Price）

```python
spread = sell_vwap - buy_vwap
spread_pct = spread / buy_vwap × 100

# 淨賣出且 spread > 0
→ 賣出均價高於買進成本 +{spread:.2f} 元，主力獲利出貨 / 減碼

# 淨賣出且 spread < 0
→ 賣出均價低於買進成本，主力虧損賣出或止損

# 淨買進
→ 淨買進，平均建倉成本 {net_cost:.2f} 元，
  收盤 {close_price} 元，浮盈 {close-net:.2f} 元（{pct:+.2f}%）
```

---

## 六、HTML 報表產生 / HTML Report Generation

### 6.1 產生時機 / When Generated

stdout 還原後，讀取 `_buf.getvalue()` 並產生 HTML，儲存至：  
After restoring stdout, read `_buf.getvalue()` and write HTML to:

```
/workspace/logs/{stock_id}_full_volume_analysis.html
```

### 6.2 圖片嵌入 / Image Embedding

```python
with open(png_path, "rb") as f:
    b64 = base64.b64encode(f.read()).decode()
img_tag = f'<img src="data:image/png;base64,{b64}">'
```

HTML 為單一自包含檔案（無外部資源依賴）。/ Self-contained single file, no external dependencies.

### 6.3 HTML 頁面結構 / HTML Page Layout

```
Header
  └─ 股號、名稱、日期、市場、產業、總筆數、總成交量

成交量分析圖表（全寬）
  └─ base64 嵌入 PNG

grid-2（左右各半）
  ├─ 價格與基本統計
  │    開盤價、收盤價、漲跌（▲紅 / ▼綠）
  │    mean / median / mode / std / skewness / kurtosis
  └─ 主力分析
       門檻、量佔比、買進比%、賣出比%、集中度
       大單 VWAP、買進成本、賣出均價、淨部位成本
       主力傾向 badge（偏多=綠、偏空=紅、均衡=灰）

重點解讀（ins-grid 2×2）
  ├─ ① 偏態分析
  ├─ ② 中位數 / 眾數
  ├─ ③ 最大單分析
  └─ ⑤ 量價背離
  （④開收盤、⑥主力成本已在上方卡片呈現，不重複）

原始輸出（全寬）
  └─ 完整 terminal 文字，白底黑字，等寬字型（Courier New）
     特殊字元 &, <, > 以 str.replace() 轉義
```

### 6.4 重點解讀顏色規則 / Insight Colour Coding

| 顏色 Colour | CSS | 使用情境 When Used |
|------------|-----|-------------------|
| 🔴 紅 | `.txt-red` | 主力佈局跡象（高 kurtosis）、法人高度參與、盤中大量異常 |
| 🔵 藍 | `.txt-blue` | 中性：散戶主導、開盤競價、平峰 |
| 🟢 綠 | `.txt-green` | 均衡：低偏態、法人穩定參與 |
| 🟠 橙 | `.txt-amber` | 次要注意：輕度尖峰、收盤撮合大單 |

---

## 七、輸出檔案摘要 / Output File Summary

| 檔案 File | 路徑 Path |
|----------|----------|
| PNG 圖表 | `/workspace/playground/{stock_id}_full_volume_analysis.png` |
| HTML 報表 | `/workspace/logs/{stock_id}_full_volume_analysis.html` |
