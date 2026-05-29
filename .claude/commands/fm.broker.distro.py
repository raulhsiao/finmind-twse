#!/usr/bin/env python3
"""
FinMind 券商分佈分析工具
分析指定台股標的 (SID 或中文名稱) 的券商買賣分佈情況
支援輸入：股票代號 (2330) 或 中文名稱 (台積電)
"""

import os, sys, requests, pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

def get_stock_info(token):
    """Get all stock info and build lookup tables"""
    resp = requests.get(
        "https://api.finmindtrade.com/api/v4/data",
        params={"dataset": "TaiwanStockInfo"},
        headers={"Authorization": f"Bearer {token}"}
    )
    data = resp.json()
    if data.get("status") != 200:
        return None, None

    df = pd.DataFrame(data["data"])

    # Build lookup tables
    # SID -> name
    sid_to_name = dict(zip(df["stock_id"], df["stock_name"]))
    # name -> SID (handle duplicates by taking first)
    name_to_sid = df.drop_duplicates(subset="stock_name").set_index("stock_name")["stock_id"].to_dict()

    return sid_to_name, name_to_sid

def resolve_sid(input_id, sid_to_name, name_to_sid):
    """
    Resolve input to SID.
    Input can be:
    - Stock ID (e.g., "2330") -> returns "2330"
    - Stock name (e.g., "台積電") -> returns "2330"
    """
    # Check if it's a stock ID (numeric)
    if input_id.isdigit() or (len(input_id) == 4 and input_id.upper().startswith("0")):
        if input_id in sid_to_name:
            return input_id, sid_to_name.get(input_id, "Unknown")
        else:
            return None, None

    # Check if it's a stock name
    if input_id in name_to_sid:
        sid = name_to_sid[input_id]
        return sid, input_id

    # Try partial match for name
    for name, sid in name_to_sid.items():
        if input_id in name or name in input_id:
            return sid, name

    return None, None

def setup_chinese_font():
    """Setup Chinese font for matplotlib, return True if successful"""
    font_paths = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]

    for zh_font_path in font_paths:
        try:
            fm.fontManager.addfont(zh_font_path)
            plt.rcParams.update({
                "font.family": fm.FontProperties(fname=zh_font_path).get_name(),
                "axes.unicode_minus": False,
            })
            return True
        except:
            continue

    # Fallback to sans-serif if no Chinese font found
    plt.rcParams.update({
        "font.family": "sans-serif",
        "axes.unicode_minus": False,
    })
    return False

def plot_normal_distribution(top20_buy, top20_sell, sid, stock_name, output_dir="/workspace/playground"):
    """Plot normal distribution charts for buy and sell volumes"""
    font_available = setup_chinese_font()

    # Use Chinese or English labels based on font availability
    if font_available:
        labels = {
            'title': f"{sid} {stock_name} — Top 20 券商買賣分佈常態分佈圖",
            'buy_hist_title': 'Top 20 買進券商 — 買入股數分佈',
            'sell_hist_title': 'Top 20 賣出券商 — 賣出股數分佈',
            'buy_qq_title': 'Top 20 買進券商 — Q-Q 圖',
            'sell_qq_title': 'Top 20 賣出券商 — Q-Q 圖',
            'buy_xlabel': '買入股數',
            'sell_xlabel': '賣出股數',
            'ylabel': '密度',
            'qq_xlabel': '理論分位數',
            'qq_ylabel': '實際分位數',
        }
    else:
        labels = {
            'title': f"{sid} {stock_name} - Top 20 Broker Distribution",
            'buy_hist_title': 'Top 20 Buy Brokers - Buy Volume',
            'sell_hist_title': 'Top 20 Sell Brokers - Sell Volume',
            'buy_qq_title': 'Top 20 Buy Brokers - Q-Q Plot',
            'sell_qq_title': 'Top 20 Sell Brokers - Q-Q Plot',
            'buy_xlabel': 'Buy Volume (shares)',
            'sell_xlabel': 'Sell Volume (shares)',
            'ylabel': 'Density',
            'qq_xlabel': 'Theoretical Quantiles',
            'qq_ylabel': 'Actual Quantiles',
        }

    buy_data = top20_buy["buy_total"]
    sell_data = top20_sell["sell_total"]

    buy_mean = buy_data.mean()
    buy_std = buy_data.std()
    sell_mean = sell_data.mean()
    sell_std = sell_data.std()

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(labels['title'], fontsize=16, fontweight='bold')

    # Manual normal distribution calculation
    from math import sqrt, exp, pi
    def norm_pdf(x, mean, std):
        return (1.0 / (std * sqrt(2 * pi))) * exp(-0.5 * ((x - mean) / std) ** 2)

    # 1. Buy histogram with normal curve
    ax1 = axes[0, 0]
    ax1.hist(buy_data, bins=8, edgecolor='black', alpha=0.7, color='red', density=True)
    x_buy = np.linspace(buy_data.min(), buy_data.max(), 100)
    y_buy = [norm_pdf(x, buy_mean, buy_std) for x in x_buy]
    ax1.plot(x_buy, y_buy, 'r--', linewidth=2, label=f'Normal\nμ={buy_mean:,.0f}, σ={buy_std:,.0f}')
    ax1.axvline(buy_mean, color='red', linestyle='-', linewidth=2, label=f'Mean={buy_mean:,.0f}')
    ax1.axvline(buy_data.median(), color='blue', linestyle=':', linewidth=2, label=f'Median={buy_data.median():,.0f}')
    ax1.set_xlabel(labels['buy_xlabel'])
    ax1.set_ylabel(labels['ylabel'])
    ax1.set_title(labels['buy_hist_title'])
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    # 2. Sell histogram with normal curve
    ax2 = axes[0, 1]
    ax2.hist(sell_data, bins=8, edgecolor='black', alpha=0.7, color='green', density=True)
    x_sell = np.linspace(sell_data.min(), sell_data.max(), 100)
    y_sell = [norm_pdf(x, sell_mean, sell_std) for x in x_sell]
    ax2.plot(x_sell, y_sell, 'g--', linewidth=2, label=f'Normal\nμ={sell_mean:,.0f}, σ={sell_std:,.0f}')
    ax2.axvline(sell_mean, color='green', linestyle='-', linewidth=2, label=f'Mean={sell_mean:,.0f}')
    ax2.axvline(sell_data.median(), color='blue', linestyle=':', linewidth=2, label=f'Median={sell_data.median():,.0f}')
    ax2.set_xlabel(labels['sell_xlabel'])
    ax2.set_ylabel(labels['ylabel'])
    ax2.set_title(labels['sell_hist_title'])
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    # 3. Buy QQ plot
    ax3 = axes[1, 0]
    sorted_buy = np.sort(buy_data)
    n = len(sorted_buy)
    theoretical_quantiles = np.percentile(np.random.normal(0, 1, 10000), np.linspace(0, 100, n) * (n - 1) / n)
    ax3.scatter(theoretical_quantiles, sorted_buy, alpha=0.7, color='red', s=30)
    min_q, max_q = min(theoretical_quantiles), max(theoretical_quantiles)
    min_a, max_a = min(sorted_buy), max(sorted_buy)
    ax3.plot([min_q, max_q], [min_a, max_a], 'r--', linewidth=2)
    ax3.set_title(labels['buy_qq_title'])
    ax3.set_xlabel(labels['qq_xlabel'])
    ax3.set_ylabel(labels['qq_ylabel'])
    ax3.grid(True, alpha=0.3)

    # 4. Sell QQ plot
    ax4 = axes[1, 1]
    sorted_sell = np.sort(sell_data)
    n = len(sorted_sell)
    theoretical_quantiles = np.percentile(np.random.normal(0, 1, 10000), np.linspace(0, 100, n) * (n - 1) / n)
    ax4.scatter(theoretical_quantiles, sorted_sell, alpha=0.7, color='green', s=30)
    min_q, max_q = min(theoretical_quantiles), max(theoretical_quantiles)
    min_a, max_a = min(sorted_sell), max(sorted_sell)
    ax4.plot([min_q, max_q], [min_a, max_a], 'g--', linewidth=2)
    ax4.set_title(labels['sell_qq_title'])
    ax4.set_xlabel(labels['qq_xlabel'])
    ax4.set_ylabel(labels['qq_ylabel'])
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = f"{output_dir}/{sid}_{stock_name}_broker_distro.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    return output_path

def analyze_broker_distribution(sid, stock_name, days=60):
    token = os.environ.get("FINMIND_TOKEN")
    if not token:
        print("錯誤：FINMIND_TOKEN 未設定。請執行：export FINMIND_TOKEN='your_token_here'")
        sys.exit(1)

    base_url = "https://api.finmindtrade.com/api/v4/taiwan_stock_trading_daily_report"
    headers = {"Authorization": f"Bearer {token}"}

    # 計算日期範圍
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)
    dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d")
             for i in range((end_date - start_date).days + 1)]

    # 抓取交易資料
    all_data = []
    for date in dates:
        params = {"data_id": sid, "date": date}
        resp = requests.get(base_url, params=params, headers=headers)
        data = resp.json()
        if data.get("status") == 200 and data["data"]:
            all_data.extend(data["data"])

    if not all_data:
        print(f"警告：{sid} 在過去 {days} 天內無交易資料")
        sys.exit(0)

    df = pd.DataFrame(all_data)

    # 依券商彙總
    broker_stats = df.groupby("securities_trader").agg(
        buy_total=("buy", "sum"),
        sell_total=("sell", "sum")
    ).reset_index()

    # 全市場成交量
    all_volume_buy = broker_stats["buy_total"].sum()
    all_volume_sell = broker_stats["sell_total"].sum()

    # Top 20 買進券商
    top20_buy = broker_stats.nlargest(20, "buy_total").copy()
    top20_volume_buy = top20_buy["buy_total"].sum()
    top20_volume_sell = top20_buy["sell_total"].sum()

    # Top 20 賣出券商
    top20_sell = broker_stats.nlargest(20, "sell_total").copy()
    top20_volume_sell_2 = top20_sell["sell_total"].sum()
    top20_volume_buy_2 = top20_sell["buy_total"].sum()

    # 其他券商
    top20_buy_brokers = set(top20_buy["securities_trader"])
    other_brokers = broker_stats[~broker_stats["securities_trader"].isin(top20_buy_brokers)]
    other_volume_buy = other_brokers["buy_total"].sum()
    other_volume_sell = other_brokers["sell_total"].sum()

    # 佔比
    pct_top20_buy = top20_volume_buy / all_volume_buy * 100 if all_volume_buy > 0 else 0
    pct_top20_sell = top20_volume_sell / all_volume_sell * 100 if all_volume_sell > 0 else 0

    # 常態分佈統計
    buy_mean = top20_buy["buy_total"].mean()
    buy_std = top20_buy["buy_total"].std()
    buy_median = top20_buy["buy_total"].median()
    buy_min = top20_buy["buy_total"].min()
    buy_max = top20_buy["buy_total"].max()

    sell_mean = top20_sell["sell_total"].mean()
    sell_std = top20_sell["sell_total"].std()
    sell_median = top20_sell["sell_total"].median()
    sell_min = top20_sell["sell_total"].min()
    sell_max = top20_sell["sell_total"].max()

    # 輸出結果
    stock_display = f"{sid} {stock_name}" if stock_name else sid
    print(f"  {stock_display} — 過去 {days} 天券商買賣分佈分析")
    print("=" * 70)
    print("=" * 70)
    print(f"\n全市場總成交量:")
    print(f"  all.volume.buy  = {all_volume_buy:>15,} 股")
    print(f"  all.volume.sell = {all_volume_sell:>15,} 股")
    print(f"\nTop 20 買進券商:")
    print(f"  top20.volume.buy  = {top20_volume_buy:>15,} 股")
    print(f"  top20.volume.sell = {top20_volume_sell:>15,} 股")
    print(f"\nTop 20 賣出券商:")
    print(f"  top20.volume.buy  = {top20_volume_buy_2:>15,} 股")
    print(f"  top20.volume.sell = {top20_volume_sell_2:>15,} 股")
    print(f"\n其他券商:")
    print(f"  other.volume.buy  = {other_volume_buy:>15,} 股")
    print(f"  other.volume.sell = {other_volume_sell:>15,} 股")
    print(f"\n佔比分析:")
    print(f"  top20.volume.buy / all.volume.buy   = {pct_top20_buy:>6.2f}%")
    print(f"  top20.volume.sell / all.volume.sell = {pct_top20_sell:>6.2f}%")

    print("\n" + "=" * 70)
    print("  Top 20 買進券商明細 (按買進量排名)")
    print("=" * 70)
    print(f"{'排名':<4} {'券商':<14} {'買進股數':>14} {'賣出股數':>14} {'買賣超':>14}")
    print("-" * 70)
    for i, (_, row) in enumerate(top20_buy.iterrows(), 1):
        net = row["buy_total"] - row["sell_total"]
        sign = "+" if net >= 0 else ""
        print(f"{i:<4} {row['securities_trader']:<14} {row['buy_total']:>14,} {row['sell_total']:>14,} {sign}{net:>13,}")

    print("\n" + "=" * 70)
    print("  Top 20 賣出券商明細 (按賣出量排名)")
    print("=" * 70)
    print(f"{'排名':<4} {'券商':<14} {'買進股數':>14} {'賣出股數':>14} {'買賣超':>14}")
    print("-" * 70)
    for i, (_, row) in enumerate(top20_sell.iterrows(), 1):
        net = row["buy_total"] - row["sell_total"]
        sign = "+" if net >= 0 else ""
        print(f"{i:<4} {row['securities_trader']:<14} {row['buy_total']:>14,} {row['sell_total']:>14,} {sign}{net:>13,}")

    print("\n" + "=" * 70)
    print("  Top 20 買進券商 — 買入股數常態分佈統計")
    print("=" * 70)
    print(f"  平均值 (Mean)   : {buy_mean:>15,.0f} 股")
    print(f"  標準差 (Std Dev): {buy_std:>15,.0f} 股")
    print(f"  中位數 (Median) : {buy_median:>15,.0f} 股")
    print(f"  最小值 (Min)    : {buy_min:>15,.0f} 股")
    print(f"  最大值 (Max)    : {buy_max:>15,.0f} 股")
    print(f"\n  常態分佈區間:")
    print(f"    Mean ± 1σ: {max(0, buy_mean - buy_std):>12,.0f} ~ {buy_mean + buy_std:>12,.0f} 股")
    print(f"    Mean ± 2σ: {max(0, buy_mean - 2*buy_std):>12,.0f} ~ {buy_mean + 2*buy_std:>12,.0f} 股")

    print("\n" + "=" * 70)
    print("  Top 20 賣出券商 — 賣出股數常態分佈統計")
    print("=" * 70)
    print(f"  平均值 (Mean)   : {sell_mean:>15,.0f} 股")
    print(f"  標準差 (Std Dev): {sell_std:>15,.0f} 股")
    print(f"  中位數 (Median) : {sell_median:>15,.0f} 股")
    print(f"  最小值 (Min)    : {sell_min:>15,.0f} 股")
    print(f"  最大值 (Max)    : {sell_max:>15,.0f} 股")
    print(f"\n  常態分佈區間:")
    print(f"    Mean ± 1σ: {max(0, sell_mean - sell_std):>12,.0f} ~ {sell_mean + sell_std:>12,.0f} 股")
    print(f"    Mean ± 2σ: {max(0, sell_mean - 2*sell_std):>12,.0f} ~ {sell_mean + 2*sell_std:>12,.0f} 股")

    # 繪製常態分佈圖
    print("\n" + "=" * 70)
    print("  繪製常態分佈圖...")
    print("=" * 70)
    try:
        chart_path = plot_normal_distribution(top20_buy, top20_sell, sid, stock_name)
        print(f"  圖表已儲存至：{chart_path}")
        if not setup_chinese_font():
            print("  注意：系統無中文字型，圖表使用英文標籤")
    except Exception as e:
        print(f"  圖表繪製失敗：{e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python fm.broker.distro.py <SID 或股票名稱> [days]")
        print("  SID: 股票代號 (例如：2330) 或 股票名稱 (例如：台積電)")
        print("  days: 分析天數 (預設 60)")
        sys.exit(1)

    token = os.environ.get("FINMIND_TOKEN")
    if not token:
        print("錯誤：FINMIND_TOKEN 未設定。請執行：export FINMIND_TOKEN='your_token_here'")
        sys.exit(1)

    input_id = sys.argv[1]
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 60

    # Get stock info lookup tables
    sid_to_name, name_to_sid = get_stock_info(token)

    if sid_to_name is None:
        print("錯誤：無法獲取股票資訊")
        sys.exit(1)

    # Resolve input to SID
    sid, stock_name = resolve_sid(input_id, sid_to_name, name_to_sid)

    if sid is None:
        print(f"錯誤：找不到股票 '{input_id}'")
        print("請使用股票代號 (例如：2330) 或 完整股票名稱 (例如：台積電)")
        sys.exit(1)

    analyze_broker_distribution(sid, stock_name, days)
