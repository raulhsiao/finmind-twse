#!/usr/bin/env python3
"""
逐筆交易微觀市場分析系統
分析個股的短線（日內）與中長線趨勢信號

輸入：SID (股票代號) 或 SID_NAME (股票名稱)
輸出：
  - Markdown 分析報告：/workspace/logs/{YYYYMMDD}_{SID}_analysis.md
  - HTML 互動報告：/workspace/playground/{YYYYMMDD}_{SID}_analysis.html
"""

import os
import sys
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, Dict

# Matplotlib 字型設定
import matplotlib
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

# 中文字型設定 - 使用 Noto Sans TC
ZH_FONT_PATH = Path("/workspace/packages/NotoSansTC-Regular.ttf")
if ZH_FONT_PATH.exists():
    fm.fontManager.addfont(ZH_FONT_PATH)
    zh_font_name = fm.FontProperties(fname=ZH_FONT_PATH).get_name()
    plt.rcParams.update({
        "font.family": zh_font_name,
        "font.sans-serif": [zh_font_name],
        "axes.unicode_minus": False,
    })
    print(f"[字型] 已載入：{ZH_FONT_PATH}")
else:
    print(f"[警告] 未找到中文字型：{ZH_FONT_PATH}")

# FinMind API 設定
FINMIND_BASE_URL = "https://api.finmindtrade.com/api/v4"
FINMIND_TOKEN = os.environ.get("FINMIND_TOKEN", "")

# 目錄設定
LOGS_DIR = Path("/workspace/logs")
PLAYGROUND_DIR = Path("/workspace/playground")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
PLAYGROUND_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# 資料取得函數
# ============================================================================

def get_finmind_token() -> str:
    """取得 FinMind API Token"""
    token = os.environ.get("FINMIND_TOKEN")
    if not token:
        raise ValueError("請設定 FINMIND_TOKEN 環境變數")
    return token


def fetch_tick_data(stock_id: str, date: str) -> pd.DataFrame:
    """
    抓取逐筆交易資料
    TaiwanStockPriceTick - 歷史逐筆交易 (Backer tier)

    Args:
        stock_id: 股票代號
        date: 交易日 (YYYY-MM-DD)

    Returns:
        DataFrame with columns: date, stock_id, deal_price, volume, Time, TickType
    """
    token = get_finmind_token()
    url = f"{FINMIND_BASE_URL}/data"
    params = {
        "dataset": "TaiwanStockPriceTick",
        "data_id": stock_id,
        "start_date": date,
    }
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, params=params, headers=headers)
    data = resp.json()

    if data.get("status") != 200:
        raise ValueError(f"API Error: {data.get('msg', 'Unknown error')}")

    df = pd.DataFrame(data["data"])
    print(f"[資料] 抓取逐筆交易：{len(df):,} 筆")
    return df


def fetch_daily_price_data(stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    抓取日成交資訊用於核對
    TaiwanStockPrice - 股價日成交資訊
    """
    token = get_finmind_token()
    url = f"{FINMIND_BASE_URL}/data"
    params = {
        "dataset": "TaiwanStockPrice",
        "data_id": stock_id,
        "start_date": start_date,
        "end_date": end_date,
    }
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, params=params, headers=headers)
    data = resp.json()

    if data.get("status") != 200:
        raise ValueError(f"API Error: {data.get('msg', 'Unknown error')}")

    df = pd.DataFrame(data["data"])
    print(f"[資料] 抓取日成交資訊：{len(df):,} 筆")
    return df


def find_latest_trading_date() -> str:
    """
    尋找最近一個有資料的交易日
    如果當前時間尚未超過 15:00，則往過去找下一個交易日
    """
    token = get_finmind_token()
    url = f"{FINMIND_BASE_URL}/data"
    params = {"dataset": "TaiwanStockTradingDate"}
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, params=params, headers=headers)
    data = resp.json()

    if data.get("status") != 200:
        raise ValueError(f"API Error: {data.get('msg', 'Unknown error')}")

    trading_dates = pd.DataFrame(data["data"])["date"].tolist()
    trading_dates = sorted([d for d in trading_dates if d is not None], reverse=True)

    now = datetime.now()
    current_time_str = now.strftime("%Y-%m-%d")
    current_hour = now.hour
    current_minute = now.minute

    # 如果尚未超過 15:00，找前一個交易日
    if current_hour < 15 or (current_hour == 15 and current_minute < 30):
        for date in trading_dates:
            if date < current_time_str:
                return date
    else:
        # 已經超過 15:00，找當天或最近的交易日
        for date in trading_dates:
            if date <= current_time_str:
                return date

    return trading_dates[0] if trading_dates else datetime.now().strftime("%Y-%m-%d")


def get_stock_name(stock_id: str) -> str:
    """取得股票名稱"""
    token = get_finmind_token()
    url = f"{FINMIND_BASE_URL}/data"
    params = {"dataset": "TaiwanStockInfo"}
    headers = {"Authorization": f"Bearer {token}"}

    try:
        resp = requests.get(url, params=params, headers=headers)
        data = resp.json()

        if data.get("status") == 200:
            df = pd.DataFrame(data["data"])
            match = df[df["stock_id"] == stock_id]
            if len(match) > 0:
                return match.iloc[0]["stock_name"]
    except:
        pass

    return ""


# ============================================================================
# 資料處理函數
# ============================================================================

def parse_time(time_str: str) -> str:
    """
    解析時間字串，移除微秒部分
    FinMind API 返回的 Time 欄位格式為 HH:MM:SS.ffffff
    """
    if pd.isna(time_str):
        return ""
    time_str = str(time_str)
    if "." in time_str:
        return time_str.split(".")[0]
    return time_str


def calculate_vwap(df: pd.DataFrame) -> Tuple[pd.Series, float]:
    """
    計算 VWAP (成交量加權平均價)
    VWAP = cumsum(deal_price × volume) / cumsum(volume)
    """
    df = df.copy()
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df["deal_price"] = pd.to_numeric(df["deal_price"], errors="coerce")

    df["pv"] = df["deal_price"] * df["volume"]
    df["cum_pv"] = df["pv"].cumsum()
    df["cum_volume"] = df["volume"].cumsum()
    df["vwap"] = df["cum_pv"] / df["cum_volume"]

    final_vwap = df["vwap"].iloc[-1] if len(df) > 0 else None
    return df["vwap"], final_vwap


def analyze_buy_sell_pressure(df: pd.DataFrame) -> Dict:
    """
    分析內外盤氣勢（買賣力道指標）
    TickType=2: 主動買盤/外盤
    TickType=1: 主動賣盤/內盤
    TickType=0: 集合競價/特殊交易（不計入）
    """
    df = df.copy()
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)

    buy_volume = df[df["TickType"] == "2"]["volume"].sum()
    sell_volume = df[df["TickType"] == "1"]["volume"].sum()

    total_volume = buy_volume + sell_volume
    buy_sell_ratio = buy_volume / sell_volume if sell_volume > 0 else float("inf")

    # 判斷信號
    if buy_sell_ratio > 1.5:
        signal = "偏多", "主動買盤遠大於賣盤，追價意願高"
        signal_color = "red"
    elif buy_sell_ratio > 1.1:
        signal = "小幅偏多", "買盤略強於賣盤"
        signal_color = "red"
    elif buy_sell_ratio < 0.67:
        signal = "偏空", "主動賣盤遠大於買盤，賣壓沉重"
        signal_color = "green"
    elif buy_sell_ratio < 0.9:
        signal = "小幅偏空", "賣盤略強於買盤"
        signal_color = "green"
    else:
        signal = "中性", "買賣盤力道相當"
        signal_color = "blue"

    return {
        "buy_volume": int(buy_volume),
        "sell_volume": int(sell_volume),
        "buy_sell_ratio": round(buy_sell_ratio, 2) if buy_sell_ratio != float("inf") else "∞",
        "signal": signal[0],
        "description": signal[1],
        "color": signal_color,
    }


def analyze_large_orders(df: pd.DataFrame, threshold: int = 50) -> Dict:
    """
    分析主力大單追蹤（籌碼集中信號）
    threshold: 大單門檻（張數）
    """
    df = df.copy()
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df["deal_price"] = pd.to_numeric(df["deal_price"], errors="coerce")

    large_orders = df[df["volume"] >= threshold].copy()

    if len(large_orders) == 0:
        return {
            "large_order_count": 0,
            "large_buy_volume": 0,
            "large_sell_volume": 0,
            "large_order_ratio": 0,
            "signal": "無明顯主力",
            "description": f"無成交量 >= {threshold} 張的大單",
            "color": "blue",
        }

    large_buy = large_orders[large_orders["TickType"] == "2"]
    large_sell = large_orders[large_orders["TickType"] == "1"]

    large_buy_volume = large_buy["volume"].sum()
    large_sell_volume = large_sell["volume"].sum()

    total_volume = df["volume"].sum()
    large_order_ratio = large_orders["volume"].sum() / total_volume if total_volume > 0 else 0

    # 計算大單平均價格
    avg_buy_price = (large_buy["deal_price"] * large_buy["volume"]).sum() / large_buy_volume if large_buy_volume > 0 else 0
    avg_sell_price = (large_sell["deal_price"] * large_sell["volume"]).sum() / large_sell_volume if large_sell_volume > 0 else 0

    # 判斷信號
    if large_buy_volume > large_sell_volume * 1.5 and avg_buy_price > avg_sell_price:
        signal = "主力吃貨", "大單買盤積極，價格墊高"
        color = "red"
    elif large_sell_volume > large_buy_volume * 1.5 and avg_sell_price < avg_buy_price:
        signal = "主力出貨", "大單賣壓沉重，價格下滑"
        color = "green"
    elif large_buy_volume > large_sell_volume:
        signal = "買盤較強", "大單買盤略多"
        color = "red"
    elif large_sell_volume > large_buy_volume:
        signal = "賣盤較強", "大單賣盤略多"
        color = "green"
    else:
        signal = "多空膠著", "大單買賣力道相當"
        color = "blue"

    return {
        "large_order_count": len(large_orders),
        "large_buy_volume": int(large_buy_volume),
        "large_sell_volume": int(large_sell_volume),
        "large_order_ratio": round(large_order_ratio * 100, 2),
        "avg_buy_price": round(avg_buy_price, 2),
        "avg_sell_price": round(avg_sell_price, 2),
        "signal": signal[0],
        "description": signal[1],
        "color": color,
    }


def analyze_price_levels(df: pd.DataFrame, num_bins: int = 10) -> Dict:
    """
    分析關鍵價位的支撐與壓力（價格行為）
    """
    df = df.copy()
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df["deal_price"] = pd.to_numeric(df["deal_price"], errors="coerce")

    min_price = float(df["deal_price"].min())
    max_price = float(df["deal_price"].max())
    price_range = max_price - min_price

    if price_range == 0:
        return {
            "bins": pd.DataFrame(),
            "max_volume_price": min_price,
            "max_volume": 0,
            "support_level": min_price,
            "resistance_level": max_price,
        }

    bin_edges = np.linspace(min_price, max_price, num_bins + 1)
    df["price_bin"] = pd.cut(df["deal_price"], bins=bin_edges, include_lowest=True)

    # 計算每個價格區間的成交量
    bin_stats = df.groupby("price_bin", observed=True).agg({
        "volume": "sum",
        "deal_price": "mean"
    }).reset_index()

    bin_stats.columns = ["price_range", "volume", "avg_price"]
    bin_stats["price_mid"] = bin_stats["price_range"].apply(lambda x: float(x.mid)).astype(float)

    # 找出最大量區
    max_vol_idx = bin_stats["volume"].idxmax()
    max_volume_price = float(bin_stats.loc[max_vol_idx, "avg_price"])
    max_volume = int(bin_stats.loc[max_vol_idx, "volume"])

    # 支撐位（最大量區下方）
    support_bins = bin_stats[bin_stats["price_mid"] < max_volume_price]
    support_level = float(support_bins["price_mid"].max()) if len(support_bins) > 0 else min_price

    # 壓力位（最大量區上方）
    resistance_bins = bin_stats[bin_stats["price_mid"] > max_volume_price]
    resistance_level = float(resistance_bins["price_mid"].min()) if len(resistance_bins) > 0 else max_price

    return {
        "bins": bin_stats,
        "max_volume_price": round(max_volume_price, 2),
        "max_volume": max_volume,
        "support_level": round(support_level, 2),
        "resistance_level": round(resistance_level, 2),
    }


def analyze_time_momentum(df: pd.DataFrame) -> Dict:
    """
    分析時間節點動能（開收盤效應）
    """
    df = df.copy()
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df["deal_price"] = pd.to_numeric(df["deal_price"], errors="coerce")
    df["time_only"] = df["Time"].apply(parse_time)

    # 開盤前 15 分鐘 (09:00 - 09:15)
    opening_mask = (df["time_only"] >= "09:00:00") & (df["time_only"] <= "09:15:00")
    opening_df = df[opening_mask]

    # 收盤前 5 分鐘 (13:25 - 13:30)
    closing_mask = (df["time_only"] >= "13:25:00") & (df["time_only"] <= "13:30:00")
    closing_df = df[closing_mask]

    # 開盤分析
    opening_buy = opening_df[opening_df["TickType"] == "2"]["volume"].sum()
    opening_sell = opening_df[opening_df["TickType"] == "1"]["volume"].sum()
    opening_avg_price = (opening_df["deal_price"] * opening_df["volume"]).sum() / opening_df["volume"].sum() if opening_df["volume"].sum() > 0 else 0

    # 收盤分析
    closing_buy = closing_df[closing_df["TickType"] == "2"]["volume"].sum()
    closing_sell = closing_df[closing_df["TickType"] == "1"]["volume"].sum()
    closing_avg_price = (closing_df["deal_price"] * closing_df["volume"]).sum() / closing_df["volume"].sum() if closing_df["volume"].sum() > 0 else 0

    # 判斷信號
    if opening_buy > opening_sell * 1.2:
        opening_signal = "強勢"
        opening_color = "red"
    elif opening_sell > opening_buy * 1.2:
        opening_signal = "弱勢"
        opening_color = "green"
    else:
        opening_signal = "中性"
        opening_color = "blue"

    if closing_buy > closing_sell * 1.5:
        closing_signal = "尾盤拉抬"
        closing_color = "red"
    elif closing_sell > closing_buy * 1.5:
        closing_signal = "尾盤賣壓"
        closing_color = "green"
    else:
        closing_signal = "中性"
        closing_color = "blue"

    return {
        "opening_volume": int(opening_df["volume"].sum()),
        "opening_buy_volume": int(opening_buy),
        "opening_sell_volume": int(opening_sell),
        "opening_avg_price": round(opening_avg_price, 2),
        "opening_signal": opening_signal,
        "opening_color": opening_color,
        "closing_volume": int(closing_df["volume"].sum()),
        "closing_buy_volume": int(closing_buy),
        "closing_sell_volume": int(closing_sell),
        "closing_avg_price": round(closing_avg_price, 2),
        "closing_signal": closing_signal,
        "closing_color": closing_color,
    }


# ============================================================================
# 圖表繪製函數
# ============================================================================

def create_analysis_chart(df: pd.DataFrame, stock_id: str, stock_name: str,
                          vwap_series: pd.Series, final_vwap: float,
                          price_analysis: dict, output_path: str) -> str:
    """
    建立分析圖表（3 子圖，垂直排列）
    使用 matplotlib 繪製並儲存為 PNG
    """
    df = df.copy()
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df["deal_price"] = pd.to_numeric(df["deal_price"], errors="coerce")
    df["time_only"] = df["Time"].apply(parse_time)

    # 計算累積內外盤
    df["buy_volume"] = df.apply(lambda x: x["volume"] if x["TickType"] == "2" else 0, axis=1)
    df["sell_volume"] = df.apply(lambda x: x["volume"] if x["TickType"] == "1" else 0, axis=1)
    df["cum_buy"] = df["buy_volume"].cumsum()
    df["cum_sell"] = df["sell_volume"].cumsum()

    # 建立圖表
    fig, axes = plt.subplots(3, 1, figsize=(14, 14))
    fig.suptitle(f"{stock_id} {stock_name} 逐筆交易微觀市場分析", fontsize=16, fontweight="bold")
    fig.patch.set_facecolor("white")

    # === 取樣策略 ===
    n_points = len(df)
    if n_points <= 200:
        sample_indices = list(range(n_points))
    else:
        step = max(1, n_points // 150)
        sample_indices = list(range(0, n_points, step))
        if n_points - 1 not in sample_indices:
            sample_indices.append(n_points - 1)

    sample_times = df.iloc[sample_indices]["time_only"].tolist()
    sample_times_raw = df["time_only"].tolist()
    sample_prices = df.iloc[sample_indices]["deal_price"].tolist()
    sample_vwaps = vwap_series.iloc[sample_indices].tolist()
    sample_cum_buy = df.iloc[sample_indices]["cum_buy"].tolist()
    sample_cum_sell = df.iloc[sample_indices]["cum_sell"].tolist()

    # === X 軸標籤優化 ===
    def get_x_tick_indices(times, max_ticks=8):
        n = len(times)
        if n <= max_ticks:
            return list(range(n))

        key_indices = set()

        # 開盤 (09:00)
        for i, t in enumerate(times):
            if t and t.startswith("09:00"):
                key_indices.add(i)
                break

        # 收盤 (13:30)
        for i in range(n - 1, -1, -1):
            if times[i] and times[i].startswith("13:30"):
                key_indices.add(i)
                break
            if times[i] and times[i].startswith("13:25"):
                key_indices.add(i)
                break

        # 整點時刻
        for hour in [10, 11, 12, 13]:
            for i, t in enumerate(times):
                if t and t.startswith(f"{hour:02d}:00"):
                    key_indices.add(i)
                    break

        # 均勻補充
        remaining = max_ticks - len(key_indices)
        if remaining > 0 and n > max_ticks:
            step = n // (remaining + 1)
            for i in range(step, n, step):
                if i not in key_indices:
                    key_indices.add(i)
                if len(key_indices) >= max_ticks:
                    break

        return sorted(key_indices)

    x_tick_indices = get_x_tick_indices(sample_times, max_ticks=8)
    x_tick_labels = [sample_times[i] for i in x_tick_indices]
    x_tick_labels = [t[:5] if t and len(t) >= 5 else t for t in x_tick_labels]

    # === 子圖 1：價格與 VWAP 走勢 ===
    ax1 = axes[0]
    ax1.set_facecolor("white")

    ax1.plot(sample_times, sample_prices, "k-", linewidth=0.8, label="成交價", alpha=0.7)
    ax1.plot(sample_times, sample_vwaps, "r-", linewidth=1.5, label="VWAP")
    ax1.axhline(y=final_vwap, color="r", linestyle="--", linewidth=1, alpha=0.5,
                label=f"最終 VWAP: {final_vwap:.2f}")

    ax1.set_ylabel("價格 (元)", fontsize=11)
    ax1.set_title(f"{stock_id} {stock_name} 日內價格與 VWAP 走勢", fontsize=12)
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.set_xticks(x_tick_indices)
    ax1.set_xticklabels(x_tick_labels, rotation=45, ha="right", fontsize=8)

    # === 子圖 2：累積內外盤走勢 ===
    ax2 = axes[1]
    ax2.set_facecolor("white")

    ax2.plot(sample_times, sample_cum_buy, "r-", linewidth=1.2, label="累積買盤 (外盤)")
    ax2.plot(sample_times, sample_cum_sell, "g-", linewidth=1.2, label="累積賣盤 (內盤)")
    ax2.fill_between(range(len(sample_times)), sample_cum_buy, sample_cum_sell,
                     alpha=0.3, where=(np.array(sample_cum_buy) >= np.array(sample_cum_sell)),
                     color="red")
    ax2.fill_between(range(len(sample_times)), sample_cum_buy, sample_cum_sell,
                     alpha=0.3, where=(np.array(sample_cum_buy) < np.array(sample_cum_sell)),
                     color="green")

    ax2.set_ylabel("累積成交量 (股)", fontsize=11)
    ax2.set_title("累積內外盤走勢", fontsize=12)
    ax2.legend(loc="upper left", fontsize=9)
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks(x_tick_indices)
    ax2.set_xticklabels(x_tick_labels, rotation=45, ha="right", fontsize=8)

    # === 子圖 3：價格分佈成交量 ===
    ax3 = axes[2]
    ax3.set_facecolor("white")

    bins_df = price_analysis["bins"].copy()
    if len(bins_df) > 0:
        max_vol_price = price_analysis["max_volume_price"]
        close_price = df["deal_price"].iloc[-1] if len(df) > 0 else max_vol_price

        # 決定顏色
        colors = []
        for _, row in bins_df.iterrows():
            if abs(row["price_mid"] - max_vol_price) < 0.01:
                colors.append("blue")  # 最大量區
            elif row["price_mid"] < max_vol_price:
                colors.append("green")  # 支撐區
            else:
                colors.append("red")  # 壓力區

        y_positions = range(len(bins_df))
        y_labels = [f"{row['price_mid']:.2f}" for _, row in bins_df.iterrows()]

        bars = ax3.barh(y_positions, bins_df["volume"] / 1000, color=colors, alpha=0.7)
        ax3.set_yticks(y_positions)
        ax3.set_yticklabels(y_labels)

        # 標記線
        max_vol_idx = bins_df["price_mid"].sub(max_vol_price).abs().idxmin()
        ax3.axhline(y=max_vol_idx, color="blue", linestyle="--", linewidth=1.5,
                    label=f"最大量區：{max_vol_price:.2f}")

        # 收盤價標記
        close_idx = bins_df.apply(
            lambda row: abs(row["price_mid"] - close_price) < (bins_df["price_mid"].max() - bins_df["price_mid"].min()) / 10,
            axis=1
        )
        if close_idx.any():
            close_pos = close_idx[close_idx].index[0]
            ax3.axhline(y=close_pos, color="blue", linestyle=":", linewidth=1.5,
                        label=f"收盤價：{close_price:.2f}")

        ax3.set_xlabel("成交量 (千股)", fontsize=11)
        ax3.set_ylabel("價格區間 (元)", fontsize=11)
        ax3.set_title("價格分佈成交量", fontsize=12)
        ax3.legend(loc="lower right", fontsize=9)
        ax3.grid(True, alpha=0.3, axis="x")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()

    print(f"[圖表] 已儲存：{output_path}")
    return output_path


def create_interactive_chart(df: pd.DataFrame, stock_id: str, stock_name: str,
                              vwap_series: pd.Series, final_vwap: float,
                              price_analysis: dict, output_html: str) -> str:
    """
    建立互動式 HTML 圖表（使用 bokeh）
    """
    try:
        from bokeh.plotting import figure, output_file, save, show
        from bokeh.models import ColumnDataSource, HoverTool, Legend, Span
        from bokeh.layouts import column, gridplot
        from bokeh.io import curdoc
        curdoc().theme = None
    except ImportError:
        print("[警告] bokeh 未安裝，跳過互動式圖表")
        return None

    df = df.copy()
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df["deal_price"] = pd.to_numeric(df["deal_price"], errors="coerce")
    df["time_only"] = df["Time"].apply(parse_time)

    # 計算累積內外盤
    df["buy_volume"] = df.apply(lambda x: x["volume"] if x["TickType"] == "2" else 0, axis=1)
    df["sell_volume"] = df.apply(lambda x: x["volume"] if x["TickType"] == "1" else 0, axis=1)
    df["cum_buy"] = df["buy_volume"].cumsum()
    df["cum_sell"] = df["sell_volume"].cumsum()

    # 取樣
    n_points = len(df)
    if n_points <= 200:
        sample_indices = list(range(n_points))
    else:
        step = max(1, n_points // 150)
        sample_indices = list(range(0, n_points, step))
        if n_points - 1 not in sample_indices:
            sample_indices.append(n_points - 1)

    sample_df = df.iloc[sample_indices].copy()
    sample_df["vwap"] = vwap_series.iloc[sample_indices].values
    sample_df["index"] = range(len(sample_df))

    source = ColumnDataSource(sample_df)

    # 建立 HoverTool
    hover = HoverTool(tooltips=[
        ("時間", "@time_only"),
        ("成交價", "@deal_price{0.00}"),
        ("成交量", "@volume{0}"),
        ("VWAP", "@vwap{0.00}"),
    ])

    # 子圖 1：價格與 VWAP
    p1 = figure(title=f"{stock_id} {stock_name} 日內價格與 VWAP 走勢",
                x_axis_label="時間", y_axis_label="價格 (元)",
                width=800, height=300, tools="pan,wheel_zoom,box_zoom,reset,save")
    p1.line(x="index", y="deal_price", source=source, legend_label="成交價", color="black", alpha=0.7)
    p1.line(x="index", y="vwap", source=source, legend_label="VWAP", color="red", line_width=2)
    p1.add_layout(Span(location=final_vwap, dimension="width", line_color="red", line_style="dashed", line_alpha=0.5))
    p1.add_tools(hover)
    p1.legend.location = "top_left"
    p1.xaxis.visible = False

    # 子圖 2：累積內外盤
    p2 = figure(title="累積內外盤走勢",
                x_axis_label="時間", y_axis_label="累積成交量 (股)",
                width=800, height=300, tools="pan,wheel_zoom,box_zoom,reset,save")
    p2.line(x="index", y="cum_buy", source=source, legend_label="累積買盤 (外盤)", color="red", line_width=1.5)
    p2.line(x="index", y="cum_sell", source=source, legend_label="累積賣盤 (內盤)", color="green", line_width=1.5)
    p2.varea(x="index", y1=sample_df["cum_buy"], y2=sample_df["cum_sell"],
             fill_alpha=0.3, fill_color="gray")
    p2.add_tools(HoverTool(tooltips=[
        ("時間", "@time_only"),
        ("累積買盤", "@cum_buy{0}"),
        ("累積賣盤", "@cum_sell{0}"),
    ]))
    p2.legend.location = "top_left"
    p2.xaxis.visible = False

    # 子圖 3：價格分佈成交量
    bins_df = price_analysis["bins"].copy()
    if len(bins_df) > 0:
        max_vol_price = price_analysis["max_volume_price"]
        close_price = df["deal_price"].iloc[-1] if len(df) > 0 else max_vol_price

        bins_df["color"] = bins_df["price_mid"].apply(
            lambda x: "blue" if abs(x - max_vol_price) < 0.01 else ("green" if x < max_vol_price else "red")
        )
        bins_df["y"] = range(len(bins_df))

        bin_source = ColumnDataSource(bins_df)

        p3 = figure(title="價格分佈成交量",
                    y_axis_label="價格區間 (元)", x_axis_label="成交量 (千股)",
                    width=800, height=300, tools="pan,wheel_zoom,box_zoom,reset,save")
        p3.hbar(y="y", right="volume", height=0.8, source=bin_source,
                fill_color="color", fill_alpha=0.7, line_color=None)
        p3.add_tools(HoverTool(tooltips=[
            ("價格區間", "@price_mid{0.00}"),
            ("成交量", "@volume{0}"),
        ]))

        # 標記線
        max_vol_idx = bins_df["price_mid"].sub(max_vol_price).abs().idxmin()
        p3.add_layout(Span(location=max_vol_idx, dimension="width", line_color="blue", line_style="dashed"))

        # 連結 x 軸
        p2.x_range = p1.x_range

        grid = gridplot([[p1], [p2], [p3]], toolbar_location="right")
    else:
        grid = gridplot([[p1], [p2]], toolbar_location="right")

    output_file(output_html, title=f"{stock_id} {stock_name} 逐筆交易分析")
    save(grid)

    print(f"[互動圖表] 已儲存：{output_html}")
    return output_html


# ============================================================================
# 報告生成函數
# ============================================================================

def generate_markdown_report(stock_id: str, stock_name: str, trade_date: str,
                              df: pd.DataFrame, daily_price_df: pd.DataFrame,
                              buy_sell_analysis: dict, large_order_analysis: dict,
                              price_level_analysis: dict, time_momentum_analysis: dict,
                              final_vwap: float, chart_path: str) -> str:
    """生成 Markdown 格式分析報告"""
    df = df.copy()
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df["deal_price"] = pd.to_numeric(df["deal_price"], errors="coerce")
    df["time_only"] = df["Time"].apply(parse_time)

    # 開盤前 5 筆
    opening_5 = df.head(5)
    # 收盤前 5 筆
    closing_5 = df.tail(5)

    # 基本統計
    total_volume = df["volume"].sum()
    total_turnover = (df["deal_price"] * df["volume"]).sum()
    avg_price = df["deal_price"].mean()
    high_price = df["deal_price"].max()
    low_price = df["deal_price"].min()
    open_price = df["deal_price"].iloc[0]
    close_price = df["deal_price"].iloc[-1]

    # 與日成交資料核對
    daily_check = ""
    if len(daily_price_df) > 0:
        daily = daily_price_df.iloc[0]
        daily_open = float(daily.get("open", 0))
        daily_close = float(daily.get("close", 0))
        daily_high = float(daily.get("max", 0))
        daily_low = float(daily.get("min", 0))
        daily_vol = int(float(daily.get("Trading_Volume", 0)))

        open_match = "✓" if abs(open_price - daily_open) < 0.01 else "✗"
        close_match = "✓" if abs(close_price - daily_close) < 0.01 else "✗"
        high_match = "✓" if abs(high_price - daily_high) < 0.01 else "✗"
        low_match = "✓" if abs(low_price - daily_low) < 0.01 else "✗"
        vol_match = "✓" if abs(total_volume - daily_vol) < daily_vol * 0.1 else "✗"

        daily_check = f"""
## 📊 與日成交資訊核對

| 項目 | 逐筆資料 | 日成交資料 | 狀態 |
|------|----------|------------|------|
| 開盤價 | {open_price:.2f} | {daily_open:.2f} | {open_match} |
| 收盤價 | {close_price:.2f} | {daily_close:.2f} | {close_match} |
| 最高價 | {high_price:.2f} | {daily_high:.2f} | {high_match} |
| 最低價 | {low_price:.2f} | {daily_low:.2f} | {low_match} |
| 成交量 | {int(total_volume):,} 股 | {daily_vol:,} 股 | {vol_match} |

> 註：逐筆資料來源為 FinMind `TaiwanStockPriceTick`，其 volume 欄位可能僅記錄部分交易或採樣資料
> 日成交資料來源為 FinMind `TaiwanStockPrice`，為完整日成交統計
"""

    # 顏色標記
    def color_signal(signal: str, color: str) -> str:
        if color == "red":
            return f"<span style='color:red'>**{signal}**</span>"
        elif color == "green":
            return f"<span style='color:green'>**{signal}**</span>"
        else:
            return f"<span style='color:blue'>**{signal}**</span>"

    report = f"""# {stock_id} {stock_name} 逐筆交易微觀市場分析報告

**交易日**: {trade_date}
**分析時間**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## 📈 基本成交資訊

| 項目 | 數值 |
|------|------|
| 開盤價 | {open_price:.2f} 元 |
| 收盤價 | {close_price:.2f} 元 |
| 最高價 | {high_price:.2f} 元 |
| 最低價 | {low_price:.2f} 元 |
| 平均價 | {avg_price:.2f} 元 |
| VWAP | {final_vwap:.2f} 元 |
| 總成交量 | {int(total_volume):,} 股 |
| 總成交金額 | {int(total_turnover):,} 元 |
| 逐筆數 | {len(df):,} 筆 |

---

## 🔴🟢 內外盤氣勢分析

| 指標 | 數值 |
|------|------|
| 主動買盤（外盤） | <span style='color:red'>{buy_sell_analysis["buy_volume"]:,}</span> 股 |
| 主動賣盤（內盤） | <span style='color:green'>{buy_sell_analysis["sell_volume"]:,}</span> 股 |
| 買/賣比率 | {buy_sell_analysis["buy_sell_ratio"]} |
| **信號** | {color_signal(buy_sell_analysis["signal"], buy_sell_analysis["color"])} |

**解讀**: {buy_sell_analysis["description"]}

> 註：TickType 分類說明
> - `TickType=2`：主動買盤（外盤）- 以賣一價以上成交的主動買單
> - `TickType=1`：主動賣盤（內盤）- 以買一價以下成交的主動賣單
> - `TickType=0`：集合競價/特殊交易 - 開盤集合競價或鉅額交易，不計入內外盤統計

---

## 💰 主力大單追蹤（單筆 >= 50 張）

| 指標 | 數值 |
|------|------|
| 大單筆數 | {large_order_analysis["large_order_count"]} 筆 |
| 大單買入量 | <span style='color:red'>{large_order_analysis["large_buy_volume"]:,}</span> 股 |
| 大單賣出量 | <span style='color:green'>{large_order_analysis["large_sell_volume"]:,}</span> 股 |
| 大單佔比 | {large_order_analysis["large_order_ratio"]}% |
| 大單買入均價 | {large_order_analysis.get("avg_buy_price", "N/A")} 元 |
| 大單賣出均價 | {large_order_analysis.get("avg_sell_price", "N/A")} 元 |
| **信號** | {color_signal(large_order_analysis["signal"], large_order_analysis["color"])} |

**解讀**: {large_order_analysis["description"]}

---

## 📊 關鍵價位分析

| 項目 | 價格 |
|------|------|
| 最大量區價格 | {price_level_analysis["max_volume_price"]:.2f} 元 |
| 支撐價位 | <span style='color:green'>{price_level_analysis["support_level"]:.2f}</span> 元 |
| 壓力價位 | <span style='color:red'>{price_level_analysis["resistance_level"]:.2f}</span> 元 |

**解讀**:
- 若股價由下往上帶量突破最大量區，該區間將轉為**強支撐**
- 若跌破最大量區，則形成**沉重上檔壓力**

---

## ⏰ 時間節點動能分析

### 開盤前 15 分鐘 (09:00-09:15)
| 指標 | 數值 |
|------|------|
| 成交量 | {time_momentum_analysis["opening_volume"]:,} 股 |
| 買盤量 | <span style='color:red'>{time_momentum_analysis["opening_buy_volume"]:,}</span> 股 |
| 賣盤量 | <span style='color:green'>{time_momentum_analysis["opening_sell_volume"]:,}</span> 股 |
| 均價 | {time_momentum_analysis["opening_avg_price"]:.2f} 元 |
| **信號** | {color_signal(time_momentum_analysis["opening_signal"], time_momentum_analysis["opening_color"])} |

### 收盤前 5 分鐘 (13:25-13:30)
| 指標 | 數值 |
|------|------|
| 成交量 | {time_momentum_analysis["closing_volume"]:,} 股 |
| 買盤量 | <span style='color:red'>{time_momentum_analysis["closing_buy_volume"]:,}</span> 股 |
| 賣盤量 | <span style='color:green'>{time_momentum_analysis["closing_sell_volume"]:,}</span> 股 |
| 均價 | {time_momentum_analysis["closing_avg_price"]:.2f} 元 |
| **信號** | {color_signal(time_momentum_analysis["closing_signal"], time_momentum_analysis["closing_color"])} |

**隔日預測**: {"<span style='color:red'>尾盤拉抬通常暗示隔日開高</span>" if time_momentum_analysis["closing_signal"] == "尾盤拉抬" else "<span style='color:green'>尾盤賣壓通常暗示隔日開低</span>" if time_momentum_analysis["closing_signal"] == "尾盤賣壓" else "尾盤多空膠著，隔日走勢需觀察其他因素"}

---

## 📋 逐筆交易明細

### 開盤後 5 筆
| 時間 | 成交價 | 成交量 | TickType |
|------|--------|--------|----------|
"""

    for _, row in opening_5.iterrows():
        tick_type_desc = "<span style='color:red'>買盤</span>" if row["TickType"] == "2" else "<span style='color:green'>賣盤</span>" if row["TickType"] == "1" else str(row["TickType"])
        report += f"| {row['time_only']} | {row['deal_price']:.2f} | {int(row['volume']):,} | {tick_type_desc} |\n"

    report += """
### 收盤前 5 筆
| 時間 | 成交價 | 成交量 | TickType |
|------|--------|--------|----------|
"""

    for _, row in closing_5.iterrows():
        tick_type_desc = "<span style='color:red'>買盤</span>" if row["TickType"] == "2" else "<span style='color:green'>賣盤</span>" if row["TickType"] == "1" else str(row["TickType"])
        report += f"| {row['time_only']} | {row['deal_price']:.2f} | {int(row['volume']):,} | {tick_type_desc} |\n"

    report += daily_check

    report += f"""
---

## 📊 分析圖表

![分析圖表]({chart_path})

---

**資料來源**: FinMind 資料庫
**分析時間戳記**: {trade_date}
"""

    return report


def generate_html_report(stock_id: str, stock_name: str, trade_date: str,
                         df: pd.DataFrame, daily_price_df: pd.DataFrame,
                         buy_sell: dict, large_order: dict, price_level: dict,
                         time_momentum: dict, final_vwap: float, chart_path: str) -> str:
    """
    生成 HTML 格式分析報告，嵌入圖表
    """
    import base64

    # 將圖片轉為 base64 嵌入
    with open(chart_path, "rb") as f:
        img_base64 = base64.b64encode(f.read()).decode("utf-8")

    df = df.copy()
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df["deal_price"] = pd.to_numeric(df["deal_price"], errors="coerce")
    df["time_only"] = df["Time"].apply(parse_time)

    # 基本統計
    total_volume = df["volume"].sum()
    total_turnover = (df["deal_price"] * df["volume"]).sum()
    avg_price = df["deal_price"].mean()
    high_price = df["deal_price"].max()
    low_price = df["deal_price"].min()
    open_price = df["deal_price"].iloc[0]
    close_price = df["deal_price"].iloc[-1]

    # 開盤前 5 筆
    opening_5 = df.head(5)
    # 收盤前 5 筆
    closing_5 = df.tail(5)

    # 與日成交資料核對
    daily_check_html = ""
    if len(daily_price_df) > 0:
        daily = daily_price_df.iloc[0]
        daily_open = float(daily.get("open", 0))
        daily_close = float(daily.get("close", 0))
        daily_high = float(daily.get("max", 0))
        daily_low = float(daily.get("min", 0))
        daily_vol = int(float(daily.get("Trading_Volume", 0)))

        open_match = "✓" if abs(open_price - daily_open) < 0.01 else "✗"
        close_match = "✓" if abs(close_price - daily_close) < 0.01 else "✗"
        high_match = "✓" if abs(high_price - daily_high) < 0.01 else "✗"
        low_match = "✓" if abs(low_price - daily_low) < 0.01 else "✗"
        vol_match = "✓" if abs(total_volume - daily_vol) < daily_vol * 0.1 else "✗"

        daily_check_html = f"""
        <h2>📊 與日成交資訊核對</h2>
        <table>
            <thead><tr><th>項目</th><th>逐筆資料</th><th>日成交資料</th><th>狀態</th></tr></thead>
            <tbody>
                <tr><td>開盤價</td><td>{open_price:.2f}</td><td>{daily_open:.2f}</td><td>{open_match}</td></tr>
                <tr><td>收盤價</td><td>{close_price:.2f}</td><td>{daily_close:.2f}</td><td>{close_match}</td></tr>
                <tr><td>最高價</td><td>{high_price:.2f}</td><td>{daily_high:.2f}</td><td>{high_match}</td></tr>
                <tr><td>最低價</td><td>{low_price:.2f}</td><td>{daily_low:.2f}</td><td>{low_match}</td></tr>
                <tr><td>成交量</td><td>{int(total_volume):,} 股</td><td>{daily_vol:,} 股</td><td>{vol_match}</td></tr>
            </tbody>
        </table>
        <blockquote>
            <strong>註：</strong>逐筆資料來源為 FinMind <code>TaiwanStockPriceTick</code>，其 volume 欄位可能僅記錄部分交易或採樣資料。<br>
            日成交資料來源為 FinMind <code>TaiwanStockPrice</code>，為完整日成交統計。
        </blockquote>
        """

    # 生成開盤/收盤 5 筆表格
    def gen_tick_table(tick_df, title):
        rows = ""
        for _, row in tick_df.iterrows():
            tick_class = "red" if row["TickType"] == "2" else "green" if row["TickType"] == "1" else "blue"
            tick_text = "買盤" if row["TickType"] == "2" else "賣盤" if row["TickType"] == "1" else str(row["TickType"])
            rows += f"<tr><td>{row['time_only']}</td><td>{row['deal_price']:.2f}</td><td>{int(row['volume']):,}</td><td class='{tick_class}'>{tick_text}</td></tr>\n"
        return f"""
        <h3>{title}</h3>
        <table>
            <thead><tr><th>時間</th><th>成交價</th><th>成交量</th><th>TickType</th></tr></thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        """

    opening_table = gen_tick_table(opening_5, "開盤後 5 筆")
    closing_table = gen_tick_table(closing_5, "收盤前 5 筆")

    # 隔日預測
    next_day_pred = ""
    if time_momentum["closing_signal"] == "尾盤拉抬":
        next_day_pred = "<span class='red'>尾盤拉抬通常暗示隔日開高</span>"
    elif time_momentum["closing_signal"] == "尾盤賣壓":
        next_day_pred = "<span class='green'>尾盤賣壓通常暗示隔日開低</span>"
    else:
        next_day_pred = "尾盤多空膠著，隔日走勢需觀察其他因素"

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{stock_id} {stock_name} 逐筆交易微觀市場分析</title>
    <style>
        body {{
            font-family: "Microsoft JhengHei", "Heiti TC", "Noto Sans TC", sans-serif;
            line-height: 1.8;
            max-width: 1000px;
            margin: 0 auto;
            padding: 30px;
            background-color: #ffffff;
            color: #222;
        }}
        h1 {{
            color: #1a1a1a;
            border-bottom: 3px solid #4a90d9;
            padding-bottom: 15px;
            font-size: 1.8em;
        }}
        h2 {{
            color: #4a90d9;
            margin-top: 35px;
            font-size: 1.4em;
        }}
        h3 {{
            color: #555;
            font-size: 1.1em;
            margin-top: 20px;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
            background-color: #fff;
        }}
        th, td {{
            border: 1px solid #ccc;
            padding: 12px 15px;
            text-align: left;
        }}
        th {{
            background-color: #f0f4f8;
            font-weight: bold;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .red {{ color: #d93025; font-weight: bold; }}
        .green {{ color: #188038; font-weight: bold; }}
        .blue {{ color: #1a73e8; font-weight: bold; }}
        img {{
            max-width: 100%;
            height: auto;
            margin: 25px 0;
            border: 2px solid #ddd;
            border-radius: 6px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        hr {{
            border: none;
            border-top: 2px solid #eee;
            margin: 35px 0;
        }}
        .timestamp {{
            color: #888;
            font-size: 0.9em;
        }}
        blockquote {{
            border-left: 4px solid #ddd;
            margin: 20px 0;
            padding: 10px 20px;
            color: #666;
            background-color: #f9f9f9;
        }}
        .summary-box {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .summary-box h3 {{ color: white; margin-top: 0; }}
        .summary-box p {{ margin: 10px 0 0 0; }}
    </style>
</head>
<body>
    <h1>{stock_id} {stock_name} 逐筆交易微觀市場分析報告</h1>
    <p class="timestamp"><strong>交易日</strong>: {trade_date} | <strong>分析時間</strong>: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

    <div class="summary-box">
        <h3>📊 分析摘要</h3>
        <p>
            <strong>收盤價</strong>: {close_price:.2f} 元 |
            <strong>VWAP</strong>: {final_vwap:.2f} 元 |
            <strong>內外盤信號</strong>: <span class="{buy_sell['color']}">{buy_sell['signal']}</span> |
            <strong>主力大單</strong>: <span class="{large_order['color']}">{large_order['signal']}</span>
        </p>
    </div>

    <hr>

    <h2>📈 基本成交資訊</h2>
    <table>
        <thead><tr><th>項目</th><th>數值</th></tr></thead>
        <tbody>
            <tr><td>開盤價</td><td>{open_price:.2f} 元</td></tr>
            <tr><td>收盤價</td><td>{close_price:.2f} 元</td></tr>
            <tr><td>最高價</td><td>{high_price:.2f} 元</td></tr>
            <tr><td>最低價</td><td>{low_price:.2f} 元</td></tr>
            <tr><td>平均價</td><td>{avg_price:.2f} 元</td></tr>
            <tr><td>VWAP</td><td>{final_vwap:.2f} 元</td></tr>
            <tr><td>總成交量</td><td>{int(total_volume):,} 股</td></tr>
            <tr><td>總成交金額</td><td>{int(total_turnover):,} 元</td></tr>
            <tr><td>逐筆數</td><td>{len(df):,} 筆</td></tr>
        </tbody>
    </table>

    <hr>

    <h2>🔴🟢 內外盤氣勢分析</h2>
    <table>
        <thead><tr><th>指標</th><th>數值</th></tr></thead>
        <tbody>
            <tr><td>主動買盤（外盤）</td><td class="red">{buy_sell["buy_volume"]:,} 股</td></tr>
            <tr><td>主動賣盤（內盤）</td><td class="green">{buy_sell["sell_volume"]:,} 股</td></tr>
            <tr><td>買/賣比率</td><td>{buy_sell["buy_sell_ratio"]}</td></tr>
            <tr><td><strong>信號</strong></td><td class="{buy_sell['color']}">{buy_sell["signal"]}</td></tr>
        </tbody>
    </table>
    <p><strong>解讀</strong>: {buy_sell["description"]}</p>
    <blockquote>
        <strong>TickType 分類說明</strong><br>
        • <code>TickType=2</code>：主動買盤（外盤）- 以賣一價以上成交的主動買單<br>
        • <code>TickType=1</code>：主動賣盤（內盤）- 以買一價以下成交的主動賣單<br>
        • <code>TickType=0</code>：集合競價/特殊交易 - 開盤集合競價或鉅額交易，不計入內外盤統計
    </blockquote>

    <hr>

    <h2>💰 主力大單追蹤（單筆 &gt;= 50 張）</h2>
    <table>
        <thead><tr><th>指標</th><th>數值</th></tr></thead>
        <tbody>
            <tr><td>大單筆數</td><td>{large_order["large_order_count"]} 筆</td></tr>
            <tr><td>大單買入量</td><td class="red">{large_order["large_buy_volume"]:,} 股</td></tr>
            <tr><td>大單賣出量</td><td class="green">{large_order["large_sell_volume"]:,} 股</td></tr>
            <tr><td>大單佔比</td><td>{large_order["large_order_ratio"]}%</td></tr>
            <tr><td>大單買入均價</td><td>{large_order.get("avg_buy_price", "N/A")} 元</td></tr>
            <tr><td>大單賣出均價</td><td>{large_order.get("avg_sell_price", "N/A")} 元</td></tr>
            <tr><td><strong>信號</strong></td><td class="{large_order['color']}">{large_order["signal"]}</td></tr>
        </tbody>
    </table>
    <p><strong>解讀</strong>: {large_order["description"]}</p>

    <hr>

    <h2>📊 關鍵價位分析</h2>
    <table>
        <thead><tr><th>項目</th><th>價格</th></tr></thead>
        <tbody>
            <tr><td>最大量區價格</td><td>{price_level["max_volume_price"]:.2f} 元</td></tr>
            <tr><td>支撐價位</td><td class="green">{price_level["support_level"]:.2f} 元</td></tr>
            <tr><td>壓力價位</td><td class="red">{price_level["resistance_level"]:.2f} 元</td></tr>
        </tbody>
    </table>
    <p>
        <strong>解讀</strong>:<br>
        • 若股價由下往上帶量突破最大量區，該區間將轉為<strong>強支撐</strong><br>
        • 若跌破最大量區，則形成<strong>沉重上檔壓力</strong>
    </p>

    <hr>

    <h2>⏰ 時間節點動能分析</h2>

    <h3>開盤前 15 分鐘 (09:00-09:15)</h3>
    <table>
        <thead><tr><th>指標</th><th>數值</th></tr></thead>
        <tbody>
            <tr><td>成交量</td><td>{time_momentum["opening_volume"]:,} 股</td></tr>
            <tr><td>買盤量</td><td class="red">{time_momentum["opening_buy_volume"]:,} 股</td></tr>
            <tr><td>賣盤量</td><td class="green">{time_momentum["opening_sell_volume"]:,} 股</td></tr>
            <tr><td>均價</td><td>{time_momentum["opening_avg_price"]:.2f} 元</td></tr>
            <tr><td><strong>信號</strong></td><td class="{time_momentum['opening_color']}">{time_momentum["opening_signal"]}</td></tr>
        </tbody>
    </table>

    <h3>收盤前 5 分鐘 (13:25-13:30)</h3>
    <table>
        <thead><tr><th>指標</th><th>數值</th></tr></thead>
        <tbody>
            <tr><td>成交量</td><td>{time_momentum["closing_volume"]:,} 股</td></tr>
            <tr><td>買盤量</td><td class="red">{time_momentum["closing_buy_volume"]:,} 股</td></tr>
            <tr><td>賣盤量</td><td class="green">{time_momentum["closing_sell_volume"]:,} 股</td></tr>
            <tr><td>均價</td><td>{time_momentum["closing_avg_price"]:.2f} 元</td></tr>
            <tr><td><strong>信號</strong></td><td class="{time_momentum['closing_color']}">{time_momentum["closing_signal"]}</td></tr>
        </tbody>
    </table>
    <p><strong>隔日預測</strong>: {next_day_pred}</p>

    <hr>

    <h2>📋 逐筆交易明細</h2>
    {opening_table}
    {closing_table}

    {daily_check_html}

    <hr>

    <h2>📊 分析圖表</h2>
    <img src="data:image/png;base64,{img_base64}" alt="分析圖表">

    <hr>
    <p class="timestamp">
        <strong>資料來源</strong>: FinMind 資料庫 |
        <strong>分析時間戳記</strong>: {trade_date}
    </p>
</body>
</html>
"""

    return html


# ============================================================================
# 主程式
# ============================================================================

def main(stock_id: str = None, stock_name: str = None):
    """
    主程式
    """
    print("=" * 60)
    print("逐筆交易微觀市場分析系統")
    print("=" * 60)

    # 1. 取得股票名稱
    if stock_id:
        actual_name = get_stock_name(stock_id)
        if actual_name:
            stock_name = actual_name
            print(f"\n股票代號：{stock_id}")
            print(f"股票名稱：{stock_name}")
        else:
            stock_name = stock_name or stock_id
            print(f"\n股票代號：{stock_id}")
            print(f"股票名稱：{stock_name} (未找到中文名稱)")
    else:
        print("\n錯誤：請提供股票代號 (SID)")
        print("用法：python tick_micro_analysis.py --stock_id 2330")
        return

    # 2. 尋找最近交易日
    print("\n[步驟 1] 尋找最近交易日...")
    trade_date = find_latest_trading_date()
    print(f"  → 交易日：{trade_date}")

    # 3. 抓取逐筆交易資料
    print(f"\n[步驟 2] 抓取 {stock_id} 於 {trade_date} 的逐筆交易資料...")
    try:
        df = fetch_tick_data(stock_id, trade_date)
        print(f"  → 成功抓取 {len(df):,} 筆逐筆交易資料")
    except ValueError as e:
        print(f"  → 錯誤：{e}")
        print("  → 可能需要 Backer 或更高層級的 API 權限")
        return
    except Exception as e:
        print(f"  → 錯誤：{e}")
        return

    if len(df) == 0:
        print("  → 錯誤：無逐筆交易資料")
        return

    # 4. 抓取日成交資料用於核對
    print(f"\n[步驟 3] 抓取日成交資訊用於核對...")
    try:
        daily_df = fetch_daily_price_data(stock_id, trade_date, trade_date)
        print(f"  → 成功抓取日成交資料")
    except Exception as e:
        print(f"  → 警告：無法抓取日成交資料 - {e}")
        daily_df = pd.DataFrame()

    # 5. 執行分析
    print(f"\n[步驟 4] 執行分析...")

    # 計算 VWAP
    vwap_series, final_vwap = calculate_vwap(df)
    print(f"  → VWAP: {final_vwap:.2f}")

    # 內外盤分析
    buy_sell = analyze_buy_sell_pressure(df)
    print(f"  → 內外盤：{buy_sell['signal']} (買/賣={buy_sell['buy_sell_ratio']})")

    # 主力大單分析
    large_order = analyze_large_orders(df, threshold=50)
    print(f"  → 主力大單：{large_order['signal']}")

    # 價位分析
    price_levels = analyze_price_levels(df)
    print(f"  → 最大量區：{price_levels['max_volume_price']:.2f}")

    # 時間動能分析
    time_momentum = analyze_time_momentum(df)
    print(f"  → 開盤：{time_momentum['opening_signal']}, 收盤：{time_momentum['closing_signal']}")

    # 6. 建立圖表
    print(f"\n[步驟 5] 建立分析圖表...")
    date_str = datetime.now().strftime("%Y%m%d")
    chart_path = str(PLAYGROUND_DIR / f"{date_str}_{stock_id}_chart.png")
    create_analysis_chart(df, stock_id, stock_name, vwap_series, final_vwap, price_levels, chart_path)

    # 7. 生成 Markdown 報告
    print(f"\n[步驟 6] 生成 Markdown 報告...")
    report_md = generate_markdown_report(
        stock_id, stock_name, trade_date,
        df, daily_df,
        buy_sell, large_order, price_levels, time_momentum,
        final_vwap, chart_path
    )

    md_path = LOGS_DIR / f"{date_str}_{stock_id}_analysis.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"  → Markdown 報告：{md_path}")

    # 8. 生成 HTML 報告
    print(f"\n[步驟 7] 生成 HTML 報告...")
    html_content = generate_html_report(
        stock_id, stock_name, trade_date,
        df, daily_df,
        buy_sell, large_order, price_levels, time_momentum,
        final_vwap, chart_path
    )

    html_path = PLAYGROUND_DIR / f"{date_str}_{stock_id}_analysis.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"  → HTML 報告：{html_path}")

    # 9. 輸出摘要
    print("\n" + "=" * 60)
    print("分析摘要")
    print("=" * 60)
    print(f"股票：{stock_id} {stock_name}")
    print(f"交易日：{trade_date}")
    print(f"總成交量：{int(df['volume'].sum()):,} 股")
    print(f"VWAP: {final_vwap:.2f} 元")
    print(f"收盤價：{df['deal_price'].iloc[-1]:.2f} 元")
    print(f"內外盤信號：{buy_sell['signal']} (買:{buy_sell['buy_volume']:,} / 賣:{buy_sell['sell_volume']:,})")
    print(f"主力大單：{large_order['signal']}")
    print(f"開盤信號：{time_momentum['opening_signal']}")
    print(f"收盤信號：{time_momentum['closing_signal']}")
    print(f"最大量區：{price_levels['max_volume_price']:.2f} 元")
    print(f"支撐位：{price_levels['support_level']:.2f} 元")
    print(f"壓力位：{price_levels['resistance_level']:.2f} 元")
    print("=" * 60)
    print(f"分析時間戳記：{trade_date}")
    print("=" * 60)

    return {
        "stock_id": stock_id,
        "stock_name": stock_name,
        "trade_date": trade_date,
        "md_path": str(md_path),
        "html_path": str(html_path),
        "chart_path": chart_path,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="逐筆交易微觀市場分析系統")
    parser.add_argument("--stock_id", type=str, help="股票代號 (SID)")
    parser.add_argument("--stock_name", type=str, help="股票名稱 (SID_NAME，可選)")

    args = parser.parse_args()

    if args.stock_id:
        main(args.stock_id, args.stock_name)
    else:
        print("未指定股票代號，預設分析台積電 (2330)")
        main("2330")
