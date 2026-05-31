# FinMind 逐筆成交量分析 Skill

對指定台股標的進行完整的 TaiwanStockPriceTick 逐筆成交量分析，包含描述性統計、量分佈圖表與重點解讀。

## 使用方式

```
/fm.tick.analysis <SID 或股票名稱> [日期參數]
```

### 參數說明

| 參數 | 類型 | 說明 | 範例 |
|------|------|------|------|
| SID 或股票名稱 | 必填 | 股票代號或中文名稱 | `2385`、`群光`、`台積電` |
| 日期參數 | 選填 | 見下表，預設為最近一個交易日 | `2026-05-29`、`3` |

### 日期參數格式

| 輸入 | 行為 |
|------|------|
| 省略 | 自動往前試查，取最近一個有 Tick 資料的交易日 |
| `YYYY-MM-DD` | 指定特定日期（若無資料則報錯） |
| 正整數 `N` | 往前找第 N 個有資料的交易日（1 = 最近，2 = 次近，依此類推） |

## 執行方式

收到使用者指令後，解析 `$ARGUMENTS` 並執行：

```bash
~/.local/bin/uv run --python finmind python /workspace/.claude/commands/fm.tick.analysis.py <SID_OR_NAME> [DATE_SPEC]
```

- 第一個參數：SID 或中文名稱（原樣傳入，腳本內部解析）
- 第二個參數（選填）：日期規格字串，省略則腳本自動尋找最近交易日

## 範例

```
/fm.tick.analysis 2385
/fm.tick.analysis 群光
/fm.tick.analysis 2330 2026-05-29
/fm.tick.analysis 台積電 3
```

## 分析內容

1. **基本資訊**：中文名稱、市場分類、產業別、日期、總筆數
2. **HEAD 5 / TAIL 5**：逐筆資料預覽
3. **描述性統計**：mean、median、mode、std、skewness、kurtosis、P25～P99
4. **成交量分佈**：文字表格 + Bar chart + 2 張 Pie chart（量佔比、金額佔比）
5. **大單分析**：≥100 張的筆數、量佔比、前 5 大單明細
6. **開收盤各一筆**：第一筆與最後一筆逐筆資料
7. **重點解讀**：偏態、中位數/眾數、最大單、開收盤變化、量價背離

## 圖表輸出

`/workspace/playground/{STOCK_ID}_full_volume_analysis.png`

## 資料來源

- `TaiwanStockInfo`：股票基本資訊查詢
- `TaiwanStockPriceTick`：歷史逐筆交易（需 Sponsor tier）

## $ARGUMENTS
