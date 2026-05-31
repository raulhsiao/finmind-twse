#!/usr/bin/env python3
"""
FinMind 逐筆成交量分析工具
支援輸入：股票代號 (2385) 或中文名稱 (群光)
日期參數：省略=最近交易日, YYYY-MM-DD=指定日期, N=第N近交易日
"""

import os, sys, io, base64, requests, pandas as pd, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from datetime import date, timedelta

# ── 常數 ──────────────────────────────────────────────────
BASE_URL   = "https://api.finmindtrade.com/api/v4/data"
TODAY      = date(2026, 5, 31)
OUTPUT_DIR = "/workspace/playground"
LOG_DIR    = "/workspace/logs"


class _Tee:
    """stdout を端末とバッファに同時に書き出す"""
    def __init__(self, *streams): self.streams = streams
    def write(self, data):
        for s in self.streams: s.write(data)
    def flush(self):
        for s in self.streams: s.flush()


# ── 字型 ──────────────────────────────────────────────────
def setup_zh_font():
    paths = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for p in paths:
        try:
            fm.fontManager.addfont(p)
            plt.rcParams.update({
                "font.family": fm.FontProperties(fname=p).get_name(),
                "axes.unicode_minus": False,
            })
            return
        except Exception:
            continue
    plt.rcParams["axes.unicode_minus"] = False


# ── API 工具 ───────────────────────────────────────────────
def api_get(token, params):
    r = requests.get(BASE_URL, params=params,
                     headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    j = r.json()
    if j.get("status") != 200:
        raise RuntimeError(f"API Error: {j.get('msg')}")
    return j["data"]


# ── 股票代號解析 ───────────────────────────────────────────
def resolve_stock(input_str, token):
    """回傳 (stock_id, stock_name, market_type, industry)"""
    data = api_get(token, {"dataset": "TaiwanStockInfo"})
    df = pd.DataFrame(data)

    # 完全符合 stock_id
    row = df[df["stock_id"] == input_str]
    if not row.empty:
        r = row.iloc[0]
        return r["stock_id"], r.get("stock_name", ""), r.get("type", ""), r.get("industry_category", "")

    # 完全符合 stock_name
    row = df[df["stock_name"] == input_str]
    if not row.empty:
        r = row.iloc[0]
        return r["stock_id"], r["stock_name"], r.get("type", ""), r.get("industry_category", "")

    # 部分符合 stock_name
    row = df[df["stock_name"].str.contains(input_str, na=False)]
    if not row.empty:
        r = row.iloc[0]
        return r["stock_id"], r["stock_name"], r.get("type", ""), r.get("industry_category", "")

    raise ValueError(f"找不到股票「{input_str}」，請確認代號或名稱")


# ── 交易日 Tick 查詢 ───────────────────────────────────────
def fetch_tick(stock_id, date_str, token):
    data = api_get(token, {
        "dataset":    "TaiwanStockPriceTick",
        "data_id":    stock_id,
        "start_date": date_str,
        "end_date":   date_str,
    })
    return pd.DataFrame(data) if data else pd.DataFrame()


def find_recent_tick(stock_id, token, nth=1):
    """往前找第 nth 個有資料的交易日，回傳 (df, date_str)"""
    found = 0
    for delta in range(0, 30):
        d = TODAY - timedelta(days=delta)
        if d.weekday() in (5, 6):
            continue
        date_str = d.strftime("%Y-%m-%d")
        print(f"  試查 {date_str} ...", end=" ", flush=True)
        df = fetch_tick(stock_id, date_str, token)
        if not df.empty:
            found += 1
            print(f"✓ {len(df)} 筆")
            if found == nth:
                return df, date_str
        else:
            print("無資料")
    raise RuntimeError(f"近 30 日內找不到第 {nth} 個有資料的交易日")


# ── 主分析邏輯 ─────────────────────────────────────────────
def run_analysis(stock_id, stock_name, market_type, industry, tick_df, found_date):
    tick_df = tick_df.sort_values("Time").reset_index(drop=True)
    tick_df["volume"]     = pd.to_numeric(tick_df["volume"],     errors="coerce")
    tick_df["deal_price"] = pd.to_numeric(tick_df["deal_price"], errors="coerce")
    tick_df["amount"]     = tick_df["deal_price"] * tick_df["volume"]

    ALL_COLS = ["date", "stock_id", "deal_price", "volume", "Time", "TickType"]
    total_rows = len(tick_df)

    _orig_stdout = sys.stdout
    _buf = io.StringIO()
    sys.stdout = _Tee(_orig_stdout, _buf)

    # ── HEAD / TAIL ──────────────────────────────────────
    sep = "═" * 70
    print(f"\n{sep}")
    print("▌ HEAD 5")
    print(tick_df[ALL_COLS].head(5).to_string(index=False))
    print("\n▌ TAIL 5")
    print(tick_df[ALL_COLS].tail(5).to_string(index=False))

    # ── 基本資訊 ─────────────────────────────────────────
    null_counts = tick_df.isnull().sum()
    print(f"\n{sep}")
    print("▌ 基本資訊")
    print(f"  資料集名稱  : TaiwanStockPriceTick")
    print(f"  股票代號    : {stock_id}")
    print(f"  中文名稱    : {stock_name}")
    print(f"  市場分類    : {market_type}")
    print(f"  產業別      : {industry}")
    print(f"  日期        : {found_date}")
    print(f"  所有欄位    : {list(tick_df.columns)}")
    print(f"  總筆數      : {total_rows:,}")
    nc = null_counts[null_counts > 0]
    print(f"  缺值統計    : {'無缺值' if nc.empty else nc.to_string()}")

    # ── 描述性統計 ───────────────────────────────────────
    vol = tick_df["volume"].dropna()
    v_mean   = vol.mean()
    v_median = vol.median()
    v_mode   = vol.mode().iloc[0] if not vol.mode().empty else np.nan
    v_std    = vol.std()
    v_var    = vol.var()
    v_min, v_max = vol.min(), vol.max()
    v_skew   = vol.skew()
    v_kurt   = vol.kurt()
    pcts     = vol.quantile([.25, .50, .75, .90, .95, .99])

    print(f"\n{sep}")
    print("▌ 描述性統計（volume，單位：張）")
    for label, val in [
        ("mean",     v_mean),   ("median",   v_median), ("mode",     v_mode),
        ("std",      v_std),    ("var",      v_var),    ("min",      v_min),
        ("max",      v_max),    ("range",    v_max - v_min),
        ("skewness", v_skew),   ("kurtosis", v_kurt),
        ("P25",  pcts[.25]), ("P50", pcts[.50]), ("P75", pcts[.75]),
        ("P90",  pcts[.90]), ("P95", pcts[.95]), ("P99", pcts[.99]),
    ]:
        print(f"  {label:<10}= {val:.4f}")

    # ── 成交量分佈 ───────────────────────────────────────
    bins_def = [
        ("=1",     lambda v: v == 1),
        ("=2",     lambda v: v == 2),
        ("3-5",    lambda v: (v >= 3)  & (v <= 5)),
        ("6-10",   lambda v: (v >= 6)  & (v <= 10)),
        ("11-20",  lambda v: (v >= 11) & (v <= 20)),
        ("21-50",  lambda v: (v >= 21) & (v <= 50)),
        ("51-100", lambda v: (v >= 51) & (v <= 100)),
        (">100",   lambda v: v > 100),
    ]
    total_vol = vol.sum()
    total_amt = tick_df["amount"].sum()

    rows = []
    for label, cond in bins_def:
        mask    = cond(tick_df["volume"])
        cnt     = mask.sum()
        vol_sum = tick_df.loc[mask, "volume"].sum()
        amt_sum = tick_df.loc[mask, "amount"].sum()
        rows.append({
            "區間":     label,
            "筆數":     cnt,
            "筆數佔比%": round(cnt / total_rows * 100, 2),
            "量總和":   vol_sum,
            "量佔比%":  round(vol_sum / total_vol * 100, 2),
            "金額總和": amt_sum,
            "金額佔比%": round(amt_sum / total_amt * 100, 2),
        })
    distro = pd.DataFrame(rows)

    print(f"\n{sep}")
    print("▌ 成交量分佈")
    print(distro.to_string(index=False))

    # ── 繪圖 ─────────────────────────────────────────────
    setup_zh_font()
    labels   = distro["區間"].tolist()
    cnt_vals = distro["筆數"].tolist()
    cnt_pcts = distro["筆數佔比%"].tolist()

    def nonzero(vals, lbls):
        return zip(*[(l, v) for l, v in zip(lbls, vals) if v > 0]) or ([], [])

    pie1_lbl, pie1_val = zip(*[(l, v) for l, v in zip(labels, distro["量總和"].tolist()) if v > 0])

    fig = plt.figure(figsize=(20, 7))
    fig.suptitle(f"{stock_id} {stock_name}  逐筆成交量分析  {found_date}",
                 fontsize=16, fontweight="bold", y=1.01)

    # 左：Bar
    ax1 = fig.add_subplot(1, 3, 1)
    bars = ax1.bar(labels, cnt_vals, color="#4C72B0", edgecolor="white")
    ax1.set_title("各區間 Tick 筆數", fontsize=13)
    ax1.set_xlabel("成交量區間（張）", fontsize=11)
    ax1.set_ylabel("Tick 筆數", fontsize=11)
    ax1.tick_params(axis="x", rotation=30)
    for bar, cnt, pct in zip(bars, cnt_vals, cnt_pcts):
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2, h + max(cnt_vals) * 0.005,
                 f"{cnt:,}\n({pct}%)", ha="center", va="bottom", fontsize=8)
    ax1.set_ylim(0, max(cnt_vals) * 1.18)

    # 右1：Pie 量佔比
    ax2 = fig.add_subplot(1, 3, 2)
    ax2.pie(pie1_val, labels=pie1_lbl,
            autopct=lambda p: f"{p:.1f}%" if p > 1 else "",
            startangle=90, counterclock=False, pctdistance=0.75,
            wedgeprops={"edgecolor": "white", "linewidth": 0.8})
    ax2.set_title("各區間成交量佔比\n（張數）", fontsize=13)

    # 右2：Bar chart 成交價區間 vs 成交量
    price_grp = tick_df.groupby("deal_price", sort=True)["volume"].sum().reset_index()
    if len(price_grp) > 20:
        p_min, p_max = price_grp["deal_price"].min(), price_grp["deal_price"].max()
        bin_sz = max(1, round((p_max - p_min) / 15))
        bins = np.arange(p_min, p_max + bin_sz + 1, bin_sz)
        tick_df["_pbin"] = pd.cut(tick_df["deal_price"], bins=bins, right=True)
        price_grp = tick_df.groupby("_pbin", observed=True)["volume"].sum().reset_index()
        price_grp.columns = ["label", "volume"]
        price_grp["label"] = price_grp["label"].astype(str)
        tick_df.drop(columns=["_pbin"], inplace=True)
    else:
        price_grp["label"] = price_grp["deal_price"].apply(lambda x: f"{x:.0f}")
    p_total = price_grp["volume"].sum()
    price_grp["pct"] = price_grp["volume"] / p_total * 100

    ax3 = fig.add_subplot(1, 3, 3)
    bars3 = ax3.bar(price_grp["label"], price_grp["volume"],
                    color="#55A868", edgecolor="white")
    ax3.set_title("各成交價區間成交量", fontsize=13)
    ax3.set_xlabel("成交價（元）", fontsize=11)
    ax3.set_ylabel("成交量（張）", fontsize=11)
    ax3.tick_params(axis="x", rotation=45)
    max_v3 = price_grp["volume"].max()
    for bar, vol, pct in zip(bars3, price_grp["volume"], price_grp["pct"]):
        h = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width() / 2, h + max_v3 * 0.005,
                 f"{vol:,}\n({pct:.1f}%)", ha="center", va="bottom", fontsize=7)
    ax3.set_ylim(0, max_v3 * 1.25)

    plt.tight_layout()
    out_path = f"{OUTPUT_DIR}/{stock_id}_full_volume_analysis.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n圖表已儲存：{out_path}")

    # ── 大單分析 ─────────────────────────────────────────
    total_volume = tick_df["volume"].sum()
    big_mask     = tick_df["volume"] >= 100
    big_cnt      = big_mask.sum()
    big_vol      = tick_df.loc[big_mask, "volume"].sum()

    print(f"\n{sep}")
    print("▌ 總計與大單分析")
    print(f"  當日總成交量        : {total_volume:,} 張")
    print(f"  大單（≥100張）筆數  : {big_cnt:,} 筆")
    print(f"  大單量佔比          : {big_vol:,} 張 / {big_vol/total_volume*100:.2f}%")
    print("\n  前5大單：")
    top5 = (tick_df[big_mask][["Time","deal_price","volume","TickType"]]
            .sort_values("volume", ascending=False).head(5))
    print(top5.to_string(index=False) if not top5.empty else "    無大單（當日無≥100張成交）")

    # ── 主力分析 ─────────────────────────────────────────
    major_thr  = max(10, int(round(float(pcts[.95]) * 10)))
    major_mask = tick_df["volume"] >= major_thr
    major_df   = tick_df[major_mask].copy()
    major_cnt  = len(major_df)
    major_vol  = major_df["volume"].sum()
    major_pct  = major_vol / total_volume * 100 if total_volume > 0 else 0

    major_type = pd.to_numeric(major_df["TickType"], errors="coerce")
    buy_vol    = major_df.loc[major_type == 1, "volume"].sum()
    sell_vol   = major_df.loc[major_type == 2, "volume"].sum()
    buy_ratio  = buy_vol  / major_vol * 100 if major_vol > 0 else 0
    sell_ratio = sell_vol / major_vol * 100 if major_vol > 0 else 0

    top5_major    = major_df.nlargest(5, "volume")
    top5_vol      = top5_major["volume"].sum()
    concentration = top5_vol / major_vol * 100 if major_vol > 0 else 0

    # 成本計算
    buy_amount   = (major_df.loc[major_type == 1, "deal_price"]
                    * major_df.loc[major_type == 1, "volume"]).sum()
    sell_amount  = (major_df.loc[major_type == 2, "deal_price"]
                    * major_df.loc[major_type == 2, "volume"]).sum()
    major_vwap   = major_df["amount"].sum() / major_vol if major_vol > 0 else np.nan
    buy_vwap     = buy_amount  / buy_vol  if buy_vol  > 0 else np.nan
    sell_vwap    = sell_amount / sell_vol if sell_vol > 0 else np.nan
    net_vol_cost = buy_vol - sell_vol
    net_cost     = (buy_amount - sell_amount) / net_vol_cost if net_vol_cost != 0 else np.nan

    print(f"\n{sep}")
    print("▌ 主力分析")
    print(f"  主力門檻（P95×10）     : {major_thr:,} 張")
    print(f"  主力大單筆數           : {major_cnt:,} 筆")
    print(f"  主力量                 : {major_vol:,} 張 / {major_pct:.2f}%（佔當日總量）")
    print(f"  主力主動買進比         : {buy_ratio:.2f}%  （TickType=1 外盤）")
    print(f"  主力主動賣出比         : {sell_ratio:.2f}%  （TickType=2 內盤）")
    print(f"  主力集中度（前5大單）  : {top5_vol:,} 張 / {concentration:.2f}%（佔主力量）")
    print(f"  ── 成本價 ──")
    print(f"  主力 VWAP（大單加權均價）: {major_vwap:.2f} 元")
    if not np.isnan(buy_vwap):
        print(f"  主力買進成本（外盤均價）: {buy_vwap:.2f} 元  ×  {buy_vol:,} 張")
    if not np.isnan(sell_vwap):
        print(f"  主力賣出均價（內盤均價）: {sell_vwap:.2f} 元  ×  {sell_vol:,} 張")
    if np.isnan(net_cost):
        print(f"  主力淨部位成本         : 買賣量相等，無淨部位")
    elif net_vol_cost > 0:
        print(f"  主力淨部位成本         : 淨買進 {net_vol_cost:,} 張 @ {net_cost:.2f} 元")
    else:
        print(f"  主力淨部位成本         : 淨賣出 {abs(net_vol_cost):,} 張 @ {net_cost:.2f} 元")
    print("\n  前5大主力單：")
    print(top5_major[["Time", "deal_price", "volume", "TickType"]]
          .sort_values("volume", ascending=False).to_string(index=False))
    print("\n  主力傾向：", end="")
    if buy_ratio >= 60:
        print(f"偏多（買進比 {buy_ratio:.1f}%），主力積極買入。")
    elif sell_ratio >= 60:
        print(f"偏空（賣出比 {sell_ratio:.1f}%），主力積極賣出。")
    else:
        print(f"買賣均衡（買進 {buy_ratio:.1f}% / 賣出 {sell_ratio:.1f}%），方向不明確。")

    # ── 開收盤各5筆 ──────────────────────────────────────
    first_tick = tick_df[ALL_COLS].iloc[0]
    last_tick  = tick_df[ALL_COLS].iloc[-1]

    print(f"\n{sep}")
    print("▌ 逐筆交易 — 開收盤各5筆")
    print("  開盤前5筆：")
    print(tick_df[ALL_COLS].head(5).to_string(index=False))
    print("\n  收盤後5筆：")
    print(tick_df[ALL_COLS].tail(5).to_string(index=False))

    open_price  = float(first_tick["deal_price"])
    close_price = float(last_tick["deal_price"])
    price_chg   = close_price - open_price
    price_pct   = price_chg / open_price * 100

    # ── 重點解讀 ─────────────────────────────────────────
    print(f"\n{sep}")
    print("▌ 重點解讀")

    # 1. 偏態
    print("\n① 偏態分析（skewness / kurtosis）")
    if v_skew > 2:
        print(f"  高度右偏（skewness={v_skew:.2f}），大量交易極為稀少，散戶小單主導。")
    elif v_skew > 0.5:
        print(f"  中度右偏（skewness={v_skew:.2f}），小單為主但存在法人間歇性大單。")
    else:
        print(f"  偏態較低（skewness={v_skew:.2f}），交易量分佈較均勻，法人參與度較高。")
    if v_kurt > 5:
        print(f"  尖峰厚尾（kurtosis={v_kurt:.2f}），極端大單出現頻率高於常態，存在主力佈局跡象。")
    elif v_kurt > 1:
        print(f"  輕度尖峰（kurtosis={v_kurt:.2f}），偶有較大單出現。")
    else:
        print(f"  平峰（kurtosis={v_kurt:.2f}），量分佈扁平，各規模成交均勻。")

    # 2. 中位數/眾數
    print("\n② 中位數 / 眾數分析")
    print(f"  中位數={v_median:.0f} 張，眾數={v_mode:.0f} 張。")
    if v_mode <= 2 and v_median <= 5:
        print("  典型交易規模極小，市場以散戶零碎買賣為主。")
    elif v_mode <= 10:
        print("  典型成交以小額散戶為主，偶有中型法人進出。")
    else:
        print("  眾數偏大，法人或主力參與程度較高。")

    # 3. 最大單
    max_row     = tick_df.loc[tick_df["volume"].idxmax()]
    max_vol_pct = max_row["volume"] / total_volume * 100
    print("\n③ 最大單分析")
    print(f"  最大單：{max_row['volume']:.0f} 張，時間 {max_row['Time']}，"
          f"成交價 {max_row['deal_price']} 元，TickType={max_row['TickType']}")
    print(f"  佔當日總量 {max_vol_pct:.2f}%。", end=" ")
    t = str(max_row["Time"])
    if t >= "13:25":
        print("時間接近收盤，可能為收盤撮合或尾盤大量對敲。")
    elif t <= "09:05":
        print("時間接近開盤，屬開盤集合競價大量成交。")
    else:
        print("時間位於盤中，為主力或法人積極買賣之跡象。")

    # 4. 開收盤
    direction = "上漲" if price_chg > 0 else ("下跌" if price_chg < 0 else "持平")
    print("\n④ 開收盤價格變化")
    print(f"  開盤 {open_price} 元 → 收盤 {close_price} 元，"
          f"{direction} {abs(price_chg):.2f} 元（{price_pct:+.2f}%）。")
    print(f"  開盤 TickType={first_tick['TickType']}，收盤 TickType={last_tick['TickType']}。")

    # 5. 量價背離
    distro["差異"] = (distro["量佔比%"] - distro["筆數佔比%"]).abs()
    top_d = distro.sort_values("差異", ascending=False).iloc[0]
    print("\n⑤ 量價背離觀察（筆數佔比 vs 量佔比差異最大區間）")
    print(f"  差異最大區間：【{top_d['區間']}張】")
    print(f"    筆數佔比 {top_d['筆數佔比%']:.2f}%  vs  量佔比 {top_d['量佔比%']:.2f}%"
          f"  (差異 {top_d['差異']:.2f}%)")
    if top_d["量佔比%"] > top_d["筆數佔比%"]:
        print("  → 少量筆數貢獻大量成交，為法人 / 主力集中大筆佈局的典型特徵。")
    else:
        print("  → 筆數多但量小，散戶零碎進出，對總量貢獻有限。")

    # 6. 主力成本價解讀
    print("\n⑥ 主力成本價解讀")
    print(f"  大單 VWAP（≥{major_thr}張）  : {major_vwap:.2f} 元")
    if not np.isnan(buy_vwap):
        print(f"  買進成本（外盤均價）    : {buy_vwap:.2f} 元  ×  {buy_vol:,} 張")
    if not np.isnan(sell_vwap):
        print(f"  賣出均價（內盤均價）    : {sell_vwap:.2f} 元  ×  {sell_vol:,} 張")
    if not np.isnan(net_cost):
        dir_str = "淨買進" if net_vol_cost > 0 else "淨賣出"
        print(f"  淨部位成本             : {dir_str} {abs(net_vol_cost):,} 張 @ {net_cost:.2f} 元")

    if not np.isnan(buy_vwap) and not np.isnan(sell_vwap):
        spread     = sell_vwap - buy_vwap
        spread_pct = spread / buy_vwap * 100
        if net_vol_cost < 0:
            if spread > 0:
                print(f"  → 賣出均價高於買進成本 +{spread:.2f} 元（+{spread_pct:.2f}%），"
                      f"主力獲利出貨 / 減碼。")
            else:
                print(f"  → 賣出均價低於買進成本 {spread:.2f} 元（{spread_pct:.2f}%），"
                      f"主力虧損賣出或止損。")
        else:
            float_pnl     = close_price - net_cost
            float_pnl_pct = float_pnl / net_cost * 100
            print(f"  → 淨買進，平均建倉成本 {net_cost:.2f} 元，"
                  f"收盤 {close_price} 元，"
                  f"浮盈 {float_pnl:+.2f} 元（{float_pnl_pct:+.2f}%）。")
    elif np.isnan(buy_vwap):
        print("  → 無外盤大單，主力無主動買進記錄。")
    elif np.isnan(sell_vwap):
        print("  → 無內盤大單，主力無主動賣出記錄。")

    print(f"\n{sep}")
    print("分析完成。")

    # ── HTML 報表 ─────────────────────────────────────────────
    sys.stdout = _orig_stdout
    raw_output = _buf.getvalue()
    os.makedirs(LOG_DIR, exist_ok=True)
    _html_path = f"{LOG_DIR}/{stock_id}_full_volume_analysis.html"

    _img_tag = ""
    if os.path.exists(out_path):
        with open(out_path, "rb") as _f:
            _b64 = base64.b64encode(_f.read()).decode()
        _img_tag = f'<img class="chart-img" src="data:image/png;base64,{_b64}" alt="chart">'

    if price_chg > 0:
        _dir = f'<span class="up">▲ {price_chg:.2f} 元 ({price_pct:+.2f}%)</span>'
    elif price_chg < 0:
        _dir = f'<span class="dn">▼ {abs(price_chg):.2f} 元 ({price_pct:+.2f}%)</span>'
    else:
        _dir = '<span class="flat">持平</span>'

    _bvwap = f"{buy_vwap:.2f} 元 &times; {buy_vol:,} 張" if not np.isnan(buy_vwap) else "無"
    _svwap = f"{sell_vwap:.2f} 元 &times; {sell_vol:,} 張" if not np.isnan(sell_vwap) else "無"

    if np.isnan(net_cost):
        _net = "買賣量相等"
    elif net_vol_cost < 0:
        _net = f"淨賣出 {abs(net_vol_cost):,} 張 @ {net_cost:.2f} 元"
    else:
        _net = f"淨買進 {net_vol_cost:,} 張 @ {net_cost:.2f} 元"

    if buy_ratio >= 60:
        _badge = '<span class="badge badge-green">偏多</span>'
    elif sell_ratio >= 60:
        _badge = '<span class="badge badge-red">偏空</span>'
    else:
        _badge = '<span class="badge badge-gray">均衡</span>'

    # ── 重點解讀 HTML 變數 ────────────────────────────────────
    # ① 偏態
    if v_skew > 2:
        _i1a = f'<span class="txt-blue">高度右偏（skewness={v_skew:.2f}），大量交易極為稀少，散戶小單主導。</span>'
    elif v_skew > 0.5:
        _i1a = f'<span class="txt-blue">中度右偏（skewness={v_skew:.2f}），小單為主但存在法人間歇性大單。</span>'
    else:
        _i1a = f'<span class="txt-green">偏態較低（skewness={v_skew:.2f}），交易量分佈較均勻，法人參與度較高。</span>'
    if v_kurt > 5:
        _i1b = f'<span class="txt-red">尖峰厚尾（kurtosis={v_kurt:.2f}），極端大單出現頻率高於常態，存在主力佈局跡象。</span>'
    elif v_kurt > 1:
        _i1b = f'<span class="txt-amber">輕度尖峰（kurtosis={v_kurt:.2f}），偶有較大單出現。</span>'
    else:
        _i1b = f'<span class="txt-blue">平峰（kurtosis={v_kurt:.2f}），量分佈扁平，各規模成交均勻。</span>'

    # ② 中位數/眾數（解讀文字；數值已在摘要表格中）
    if v_mode <= 2 and v_median <= 5:
        _i2 = '<span class="txt-blue">典型交易規模極小，市場以散戶零碎買賣為主。</span>'
    elif v_mode <= 10:
        _i2 = '<span class="txt-amber">典型成交以小額散戶為主，偶有中型法人進出。</span>'
    else:
        _i2 = '<span class="txt-red">眾數偏大，法人或主力參與程度較高。</span>'

    # ③ 最大單
    _mx   = tick_df.loc[tick_df["volume"].idxmax()]
    _mx_v = int(_mx["volume"])
    _mx_t = str(_mx["Time"])
    _mx_p = _mx["deal_price"]
    _mx_tt= _mx["TickType"]
    _mx_pct = _mx_v / total_volume * 100
    _i3_desc = (f'最大單 <strong>{_mx_v:,} 張</strong>，'
                f'時間 {_mx_t}，成交價 {_mx_p} 元，'
                f'TickType={_mx_tt}，佔總量 {_mx_pct:.2f}%。')
    if _mx_t >= "13:25":
        _i3_note = '<span class="txt-amber">時間接近收盤，可能為收盤撮合或尾盤大量對敲。</span>'
    elif _mx_t <= "09:05":
        _i3_note = '<span class="txt-blue">時間接近開盤，屬開盤集合競價大量成交。</span>'
    else:
        _i3_note = '<span class="txt-red">時間位於盤中，為主力或法人積極買賣之跡象。</span>'

    # ⑤ 量價背離（distro["差異"] 已於重點解讀區段計算）
    _td_iv   = str(top_d["區間"])
    _td_cp   = float(top_d["筆數佔比%"])
    _td_vp   = float(top_d["量佔比%"])
    _td_diff = float(top_d["差異"])
    if _td_vp > _td_cp:
        _i5 = '<span class="txt-red">少量筆數貢獻大量成交，為法人 / 主力集中大筆佈局的典型特徵。</span>'
    else:
        _i5 = '<span class="txt-blue">筆數多但量小，散戶零碎進出，對總量貢獻有限。</span>'

    _raw_esc = raw_output.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    _css = (
        "* { box-sizing: border-box; margin: 0; padding: 0; }"
        "body { font-family: 'Segoe UI','Noto Sans TC',sans-serif; background:#f0f2f5; color:#1a1a2e; }"
        ".header { background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%); color:white; padding:24px 32px; }"
        ".header h1 { font-size:22px; margin-bottom:4px; }"
        ".header .meta { font-size:13px; opacity:0.65; margin-top:4px; }"
        ".container { max-width:1400px; margin:24px auto; padding:0 24px; }"
        ".card { background:white; border-radius:8px; padding:20px 24px; margin-bottom:20px;"
        "        box-shadow:0 1px 4px rgba(0,0,0,.08); }"
        ".card h2 { font-size:12px; text-transform:uppercase; letter-spacing:1px; color:#64748b;"
        "           border-bottom:2px solid #e2e8f0; padding-bottom:10px; margin-bottom:16px; }"
        "table { width:100%; border-collapse:collapse; font-size:14px; }"
        "th { background:#f8fafc; color:#475569; text-align:left; padding:8px 12px;"
        "     font-size:12px; font-weight:600; border-bottom:2px solid #e2e8f0; }"
        "td { padding:8px 12px; border-bottom:1px solid #f1f5f9; }"
        "tr:last-child td { border-bottom:none; }"
        "tr:hover td { background:#f8fafc; }"
        ".up { color:#dc2626; font-weight:700; }"
        ".dn { color:#16a34a; font-weight:700; }"
        ".flat { color:#64748b; }"
        ".chart-img { width:100%; border-radius:4px; }"
        ".raw { background:#ffffff; color:#1a1a2e; padding:20px 24px; border-radius:6px;"
        "       border:1px solid #e2e8f0;"
        "       font-family:'Courier New',monospace; font-size:12px; line-height:1.7;"
        "       overflow-x:auto; white-space:pre; }"
        ".badge { display:inline-block; padding:2px 10px; border-radius:12px;"
        "         font-size:12px; font-weight:700; }"
        ".badge-red   { background:#fee2e2; color:#dc2626; }"
        ".badge-green { background:#dcfce7; color:#16a34a; }"
        ".badge-gray  { background:#f1f5f9; color:#475569; }"
        ".grid-2  { display:grid; grid-template-columns:1fr 1fr; gap:20px; }"
        ".ins-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }"
        ".ins-item { background:#f8fafc; border-radius:6px; padding:14px 16px;"
        "            border-left:4px solid #e2e8f0; }"
        ".ins-no   { font-size:11px; font-weight:700; color:#475569; margin-bottom:6px; }"
        ".ins-body { font-size:13px; line-height:1.7; color:#334155; }"
        ".txt-red   { color:#dc2626; font-weight:600; }"
        ".txt-blue  { color:#2563eb; font-weight:600; }"
        ".txt-green { color:#16a34a; font-weight:600; }"
        ".txt-amber { color:#d97706; font-weight:600; }"
        "@media (max-width:768px) { .grid-2,.ins-grid { grid-template-columns:1fr; } }"
    )

    _html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{stock_id} {stock_name} 逐筆成交量分析 {found_date}</title>
<style>{_css}</style>
</head>
<body>
<div class="header">
  <h1>{stock_id}&nbsp;&nbsp;{stock_name}&nbsp;&nbsp;逐筆成交量分析</h1>
  <div class="meta">{found_date} &nbsp;／&nbsp; {market_type} &nbsp;／&nbsp; {industry}
    &nbsp;／&nbsp; 總筆數 {total_rows:,} &nbsp;／&nbsp; 總成交量 {total_volume:,} 張</div>
</div>
<div class="container">

  <div class="card">
    <h2>成交量分析圖表</h2>
    {_img_tag}
  </div>

  <div class="grid-2">
    <div class="card">
      <h2>價格與基本統計</h2>
      <table>
        <tr><th>指標</th><th>數值</th></tr>
        <tr><td>開盤價</td><td>{open_price:.0f} 元</td></tr>
        <tr><td>收盤價</td><td>{close_price:.0f} 元</td></tr>
        <tr><td>漲跌</td><td>{_dir}</td></tr>
        <tr><td>均量（mean）</td><td>{v_mean:.2f} 張</td></tr>
        <tr><td>中位數</td><td>{v_median:.0f} 張</td></tr>
        <tr><td>眾數</td><td>{v_mode:.0f} 張</td></tr>
        <tr><td>標準差</td><td>{v_std:.2f}</td></tr>
        <tr><td>偏態（skewness）</td><td>{v_skew:.2f}</td></tr>
        <tr><td>峰態（kurtosis）</td><td>{v_kurt:.2f}</td></tr>
      </table>
    </div>

    <div class="card">
      <h2>主力分析</h2>
      <table>
        <tr><th>指標</th><th>數值</th></tr>
        <tr><td>主力門檻（P95×10）</td><td>{major_thr:,} 張</td></tr>
        <tr><td>主力量佔比</td><td>{major_vol:,} 張 &nbsp;/&nbsp; {major_pct:.2f}%</td></tr>
        <tr><td>主動買進比（外盤）</td><td>{buy_ratio:.2f}%</td></tr>
        <tr><td>主動賣出比（內盤）</td><td>{sell_ratio:.2f}%</td></tr>
        <tr><td>主力集中度（前5大單）</td><td>{concentration:.2f}%</td></tr>
        <tr><td>大單 VWAP</td><td>{major_vwap:.2f} 元</td></tr>
        <tr><td>買進成本（外盤均價）</td><td>{_bvwap}</td></tr>
        <tr><td>賣出均價（內盤均價）</td><td>{_svwap}</td></tr>
        <tr><td>淨部位成本</td><td>{_net}</td></tr>
        <tr><td>主力傾向</td><td>{_badge}</td></tr>
      </table>
    </div>
  </div>

  <div class="card">
    <h2>重點解讀</h2>
    <div class="ins-grid">
      <div class="ins-item">
        <div class="ins-no">① 偏態分析</div>
        <div class="ins-body">{_i1a}<br><br>{_i1b}</div>
      </div>
      <div class="ins-item">
        <div class="ins-no">② 中位數 / 眾數</div>
        <div class="ins-body">中位數 <strong>{v_median:.0f}</strong> 張，眾數 <strong>{v_mode:.0f}</strong> 張。<br><br>{_i2}</div>
      </div>
      <div class="ins-item">
        <div class="ins-no">③ 最大單分析</div>
        <div class="ins-body">{_i3_desc}<br><br>{_i3_note}</div>
      </div>
      <div class="ins-item">
        <div class="ins-no">⑤ 量價背離（差異最大區間：{_td_iv} 張）</div>
        <div class="ins-body">筆數佔比 {_td_cp:.2f}%&nbsp;vs&nbsp;量佔比 {_td_vp:.2f}%（差 {_td_diff:.2f}%）<br><br>{_i5}</div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>原始輸出</h2>
    <div class="raw">{_raw_esc}</div>
  </div>

</div>
</body>
</html>"""

    with open(_html_path, "w", encoding="utf-8") as _f:
        _f.write(_html)
    print(f"HTML 報表已儲存：{_html_path}")


# ── CLI 入口 ───────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("用法：python fm.tick.analysis.py <SID或股票名稱> [日期參數]")
        print("  日期參數（選填）：")
        print("    省略        → 最近一個有資料的交易日")
        print("    YYYY-MM-DD  → 指定日期")
        print("    N（正整數）  → 第 N 近的有資料交易日")
        sys.exit(0)

    token = os.environ.get("FINMIND_TOKEN")
    if not token:
        print("錯誤：FINMIND_TOKEN 未設定。請執行：export FINMIND_TOKEN='your_token_here'")
        sys.exit(1)

    input_str = sys.argv[1]
    date_spec = sys.argv[2] if len(sys.argv) > 2 else None

    # 解析股票
    print(f"查詢股票資訊：{input_str} ...")
    stock_id, stock_name, market_type, industry = resolve_stock(input_str, token)
    print(f"  → {stock_id} {stock_name}（{market_type} / {industry}）")

    # 取得 Tick 資料
    print("\n取得逐筆資料...")
    if date_spec is None:
        tick_df, found_date = find_recent_tick(stock_id, token, nth=1)
    elif date_spec.isdigit():
        nth = int(date_spec)
        tick_df, found_date = find_recent_tick(stock_id, token, nth=nth)
    else:
        # 視為 YYYY-MM-DD
        print(f"  指定日期 {date_spec} ...", end=" ", flush=True)
        tick_df = fetch_tick(stock_id, date_spec, token)
        if tick_df.empty:
            print("無資料")
            sys.exit(f"指定日期 {date_spec} 無逐筆資料，請確認是否為交易日或訂閱方案")
        found_date = date_spec
        print(f"✓ {len(tick_df)} 筆")

    run_analysis(stock_id, stock_name, market_type, industry, tick_df, found_date)


if __name__ == "__main__":
    main()
