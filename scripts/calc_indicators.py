#!/usr/bin/env python3
"""
ETF 技术指标计算与策略回测脚本。

计算指标：
  MA(5,10,20,60,120,250), EMA(12,26), MACD(12,26,9), RSI(6,14,24),
  KDJ, Bollinger Bands, ATR(14), OBV, MFI(14)

策略回测：
  1. MA 金叉死叉（MA20 x MA60）
  2. MACD 金叉死叉
  3. RSI 超卖(30)买入 / 超买(70)卖出
  4. 趋势突破（收盘价突破 MA20 + 成交量放大 1.5x）

用法：
  python calc_indicators.py --input ./data/etf_quotes.json --output ./data/indicators.json
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime
# ============================================================
#  指标计算
# ============================================================

def sma(values: list[float], period: int) -> list[float | None]:
    """简单移动平均"""
    result = [None] * len(values)
    for i in range(period - 1, len(values)):
        result[i] = sum(values[i - period + 1 : i + 1]) / period
    return result


def ema(values: list[float], period: int) -> list[float | None]:
    """指数移动平均"""
    result = [None] * len(values)
    if len(values) < period:
        return result
    multiplier = 2 / (period + 1)
    result[period - 1] = sum(values[:period]) / period
    for i in range(period, len(values)):
        result[i] = (values[i] - result[i - 1]) * multiplier + result[i - 1]
    return result


def macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD: 返回 (DIF, DEA, MACD柱)"""
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    dif = [None] * len(closes)
    for i in range(len(closes)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            dif[i] = ema_fast[i] - ema_slow[i]
    dea = ema([d if d is not None else 0 for d in dif], signal)
    macd_bar = [None] * len(closes)
    for i in range(len(closes)):
        if dif[i] is not None and dea[i] is not None:
            macd_bar[i] = 2 * (dif[i] - dea[i])
    return dif, dea, macd_bar


def rsi(closes: list[float], period: int = 14) -> list[float | None]:
    """RSI"""
    result = [None] * len(closes)
    if len(closes) < period + 1:
        return result
    gains = []
    losses = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(delta if delta > 0 else 0)
        losses.append(-delta if delta < 0 else 0)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    result[period] = 100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss != 0 else 100
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            result[i + 1] = 100
        else:
            result[i + 1] = 100 - (100 / (1 + avg_gain / avg_loss))
    return result


def kdj(highs: list[float], lows: list[float], closes: list[float], period: int = 9):
    """KDJ: 返回 (K, D, J)"""
    n = len(closes)
    K = [None] * n
    D = [None] * n
    J = [None] * n
    rsv = [None] * n
    for i in range(period - 1, n):
        h = max(highs[i - period + 1 : i + 1])
        l = min(lows[i - period + 1 : i + 1])
        rsv[i] = (closes[i] - l) / (h - l) * 100 if h != l else 50
    # KDJ 平滑
    for i in range(len(rsv)):
        if rsv[i] is None:
            continue
        if K[i - 1] is not None:
            K[i] = 2 / 3 * K[i - 1] + 1 / 3 * rsv[i]
        else:
            K[i] = rsv[i]
        if D[i - 1] is not None:
            D[i] = 2 / 3 * D[i - 1] + 1 / 3 * K[i]
        else:
            D[i] = K[i]
        J[i] = 3 * K[i] - 2 * D[i]
    return K, D, J


def bollinger(closes: list[float], period: int = 20, std_mult: float = 2):
    """布林带: 返回 (mid, upper, lower)"""
    mid = sma(closes, period)
    upper = [None] * len(closes)
    lower = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        std = math.sqrt(sum((c - mid[i]) ** 2 for c in closes[i - period + 1 : i + 1]) / period)
        upper[i] = mid[i] + std_mult * std
        lower[i] = mid[i] - std_mult * std
    return mid, upper, lower


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float | None]:
    """平均真实波幅"""
    n = len(closes)
    tr = [None] * n
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
    return sma(tr, period)


def obv(closes: list[float], volumes: list[float]) -> list[float | None]:
    """能量潮"""
    result = [None] * len(closes)
    cum = 0
    for i in range(len(closes)):
        if i == 0:
            cum = volumes[i]
        elif closes[i] > closes[i - 1]:
            cum += volumes[i]
        elif closes[i] < closes[i - 1]:
            cum -= volumes[i]
        result[i] = cum
    return result


def mfi(highs: list[float], lows: list[float], closes: list[float], volumes: list[float], period: int = 14) -> list[float | None]:
    """资金流量指标"""
    n = len(closes)
    result = [None] * n
    tp = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(n)]
    mf = [tp[i] * volumes[i] if volumes[i] is not None else 0 for i in range(n)]
    for i in range(period, n):
        pmf = sum(mf[j] for j in range(i - period + 1, i + 1) if tp[j] > tp[j - 1])
        nmf = sum(mf[j] for j in range(i - period + 1, i + 1) if tp[j] < tp[j - 1])
        mfr = pmf / nmf if nmf != 0 else 100
        result[i] = 100 - (100 / (1 + mfr))
    return result


# ============================================================
#  策略回测
# ============================================================

def backtest_ma_cross(data: list[dict], fast: int = 20, slow: int = 60, fee: float = 0.001) -> dict:
    """MA 金叉死叉策略回测"""
    closes = [d["close"] for d in data]
    ma_fast = sma(closes, fast)
    ma_slow = sma(closes, slow)

    trades = []
    position = 0  # 0=空仓, 1=持仓
    entry_price = 0

    for i in range(slow, len(closes)):
        if ma_fast[i] is None or ma_slow[i] is None:
            continue
        if ma_fast[i - 1] is None or ma_slow[i - 1] is None:
            continue

        # 金叉买入
        if position == 0 and ma_fast[i] > ma_slow[i] and ma_fast[i - 1] <= ma_slow[i - 1]:
            entry_price = closes[i] * (1 + fee)
            position = 1
            trades.append({"type": "buy", "date": data[i]["date"], "price": entry_price})

        # 死叉卖出
        elif position == 1 and ma_fast[i] < ma_slow[i] and ma_fast[i - 1] >= ma_slow[i - 1]:
            exit_price = closes[i] * (1 - fee)
            pnl_pct = (exit_price - entry_price) / entry_price
            trades.append({"type": "sell", "date": data[i]["date"], "price": exit_price, "pnl_pct": round(pnl_pct * 100, 2)})
            position = 0

    return _summarize_trades(trades, closes, data)


def backtest_macd(data: list[dict], fast: int = 12, slow: int = 26, signal: int = 9, fee: float = 0.001) -> dict:
    """MACD 金叉死叉策略回测"""
    closes = [d["close"] for d in data]
    dif, dea, _ = macd(closes, fast, slow, signal)

    trades = []
    position = 0
    entry_price = 0

    for i in range(slow + signal, len(closes)):
        if dif[i] is None or dea[i] is None or dif[i - 1] is None or dea[i - 1] is None:
            continue
        if position == 0 and dif[i] > dea[i] and dif[i - 1] <= dea[i - 1]:
            entry_price = closes[i] * (1 + fee)
            position = 1
            trades.append({"type": "buy", "date": data[i]["date"], "price": entry_price})
        elif position == 1 and dif[i] < dea[i] and dif[i - 1] >= dea[i - 1]:
            exit_price = closes[i] * (1 - fee)
            pnl_pct = (exit_price - entry_price) / entry_price
            trades.append({"type": "sell", "date": data[i]["date"], "price": exit_price, "pnl_pct": round(pnl_pct * 100, 2)})
            position = 0

    return _summarize_trades(trades, closes, data)


def backtest_rsi(data: list[dict], period: int = 14, oversold: float = 30, overbought: float = 70, fee: float = 0.001) -> dict:
    """RSI 超卖买入 / 超买卖出策略"""
    closes = [d["close"] for d in data]
    rsi_vals = rsi(closes, period)

    trades = []
    position = 0
    entry_price = 0

    for i in range(period + 1, len(closes)):
        if rsi_vals[i] is None or rsi_vals[i - 1] is None:
            continue
        if position == 0 and rsi_vals[i - 1] < oversold and rsi_vals[i] > oversold:
            entry_price = closes[i] * (1 + fee)
            position = 1
            trades.append({"type": "buy", "date": data[i]["date"], "price": entry_price})
        elif position == 1 and rsi_vals[i - 1] > overbought and rsi_vals[i] < overbought:
            exit_price = closes[i] * (1 - fee)
            pnl_pct = (exit_price - entry_price) / entry_price
            trades.append({"type": "sell", "date": data[i]["date"], "price": exit_price, "pnl_pct": round(pnl_pct * 100, 2)})
            position = 0

    return _summarize_trades(trades, closes, data)


def backtest_breakout(data: list[dict], ma_period: int = 20, vol_ratio: float = 1.5, fee: float = 0.001) -> dict:
    """趋势突破策略：收盘价突破 MA20 + 成交量放大（默认 1.5 倍均量）"""
    closes = [d["close"] for d in data]
    volumes = [d["volume"] for d in data]
    ma = sma(closes, ma_period)
    vol_ma = sma(volumes, ma_period)

    trades = []
    position = 0
    entry_price = 0

    for i in range(ma_period + 1, len(closes)):
        if ma[i] is None or ma[i - 1] is None or vol_ma[i] is None:
            continue
        if volumes[i] is None:
            continue

        # 突破买入：收盘价上穿 MA20 且成交量放大
        if position == 0 and closes[i] > ma[i] and closes[i - 1] <= ma[i - 1] and volumes[i] > vol_ma[i] * vol_ratio:
            entry_price = closes[i] * (1 + fee)
            position = 1
            trades.append({"type": "buy", "date": data[i]["date"], "price": entry_price})

        # 跌破卖出：收盘价跌破 MA20
        elif position == 1 and closes[i] < ma[i] and closes[i - 1] >= ma[i - 1]:
            exit_price = closes[i] * (1 - fee)
            pnl_pct = (exit_price - entry_price) / entry_price
            trades.append({"type": "sell", "date": data[i]["date"], "price": exit_price, "pnl_pct": round(pnl_pct * 100, 2)})
            position = 0

    return _summarize_trades(trades, closes, data)


def _summarize_trades(trades: list[dict], closes: list[float], data: list[dict]) -> dict:
    """汇总回测统计"""
    sells = [t for t in trades if t["type"] == "sell"]
    wins = [t for t in sells if t["pnl_pct"] > 0]

    if not sells:
        return {
            "total_trades": 0,
            "win_rate": None,
            "avg_return": None,
            "total_return": None,
            "max_drawdown": None,
            "sharpe": None,
            "profit_loss_ratio": None,
            "trades": trades,
        }

    returns = [t["pnl_pct"] / 100 for t in sells]
    cumulative = 1.0
    max_cum = 1.0
    max_dd = 0.0
    for r in returns:
        cumulative *= (1 + r)
        max_cum = max(max_cum, cumulative)
        max_dd = max(max_dd, max_cum - cumulative)

    avg_ret = sum(returns) / len(returns)
    std_ret = math.sqrt(sum((r - avg_ret) ** 2 for r in returns) / len(returns)) if len(returns) > 1 else 0
    sharpe = (avg_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0

    win_trades = [t for t in sells if t["pnl_pct"] > 0]
    loss_trades = [t for t in sells if t["pnl_pct"] <= 0]
    avg_win = sum(t["pnl_pct"] for t in win_trades) / len(win_trades) if win_trades else 0
    avg_loss = abs(sum(t["pnl_pct"] for t in loss_trades) / len(loss_trades)) if loss_trades else 0
    pl_ratio = avg_win / avg_loss if avg_loss > 0 else None

    total_return = (cumulative - 1) * 100
    start_val = closes[0] if closes else 1
    benchmark_return = ((closes[-1] - closes[0]) / closes[0] * 100) if closes and closes[0] > 0 else 0

    return {
        "total_trades": len(sells),
        "total_signals": len(trades),
        "win_rate": round(len(wins) / len(sells) * 100, 2) if sells else None,
        "avg_return_pct": round(avg_ret * 100, 2),
        "total_return_pct": round(total_return, 2),
        "benchmark_return_pct": round(benchmark_return, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "sharpe_ratio": round(sharpe, 3),
        "profit_loss_ratio": round(pl_ratio, 2) if pl_ratio else None,
        "date_range": f"{data[0]['date']} ~ {data[-1]['date']}",
        "trades": trades[-20:],  # 只保留最近 20 笔交易
    }


# ============================================================
#  主流程
# ============================================================

def compute_all_indicators(data: list[dict]) -> dict:
    """计算所有技术指标"""
    closes = [d["close"] for d in data]
    highs = [d["high"] for d in data]
    lows = [d["low"] for d in data]
    volumes = [d["volume"] for d in data]
    n = len(closes)

    # MA
    ma_periods = [5, 10, 20, 60, 120, 250]
    mas = {f"MA{p}": sma(closes, p) for p in ma_periods}

    # EMA
    emas = {"EMA12": ema(closes, 12), "EMA26": ema(closes, 26)}

    # MACD
    dif, dea, macd_bar = macd(closes)

    # RSI
    rsis = {f"RSI{p}": rsi(closes, p) for p in [6, 14, 24]}

    # KDJ
    K, D, J = kdj(highs, lows, closes)

    # Bollinger
    bb_mid, bb_upper, bb_lower = bollinger(closes)

    # ATR
    atr_vals = atr(highs, lows, closes)

    # OBV
    obv_vals = obv(closes, volumes)

    # MFI
    mfi_vals = mfi(highs, lows, closes, volumes)

    # 取最新值
    def latest(arr):
        val = arr[-1] if arr else None
        return round(val, 4) if isinstance(val, float) else val

    # 趋势判断
    def trend_judgment():
        """基于多均线和 MACD 的趋势判断"""
        if mas["MA20"][-1] is None or mas["MA60"][-1] is None:
            return "数据不足"
        ma_bull = mas["MA5"][-1] and mas["MA20"][-1] and mas["MA60"][-1]
        if ma_bull and mas["MA5"][-1] > mas["MA20"][-1] > mas["MA60"][-1]:
            ma_status = "多头排列"
        elif ma_bull and mas["MA5"][-1] < mas["MA20"][-1] < mas["MA60"][-1]:
            ma_status = "空头排列"
        else:
            ma_status = "均线交织"

        if dif[-1] is not None and dea[-1] is not None:
            if dif[-1] > dea[-1] > 0:
                macd_status = "MACD 多头强势"
            elif dif[-1] > dea[-1]:
                macd_status = "MACD 金叉"
            elif dif[-1] < dea[-1] < 0:
                macd_status = "MACD 空头强势"
            elif dif[-1] < dea[-1]:
                macd_status = "MACD 死叉"
            else:
                macd_status = "MACD 不明"
        else:
            macd_status = "未知"

        return f"{ma_status}，{macd_status}"

    # 支撑 / 压力位
    def find_levels():
        recent_closes = closes[-60:] if len(closes) >= 60 else closes
        support = min(recent_closes)
        resistance = max(recent_closes)
        ma_fibs = []
        if mas["MA20"][-1]:
            ma_fibs.append(mas["MA20"][-1])
        if mas["MA60"][-1]:
            ma_fibs.append(mas["MA60"][-1])
        if mas["MA120"][-1]:
            ma_fibs.append(mas["MA120"][-1])
        return {
            "support_near": round(float(support), 4),
            "resistance_near": round(float(resistance), 4),
            "ma_supports": [round(float(x), 4) for x in ma_fibs],
        }

    # 顶/底背离（复用已计算的 RSI14）
    def check_divergence(rsi14: list):
        if len(closes) < 60:
            return "数据不足"
        recent_c = closes[-20:]
        recent_rsi = rsi14[-20:]
        if recent_rsi[-1] is None:
            return "无法判断"
        # 简化背离检测
        c_high = max(recent_c)
        c_high_idx = recent_c.index(c_high)
        rsi_high = max(r for r in recent_rsi if r is not None)
        rsi_high_idx = [i for i, r in enumerate(recent_rsi) if r == rsi_high][0]

        c_low = min(recent_c)
        c_low_idx = recent_c.index(c_low)
        rsi_low = min(r for r in recent_rsi if r is not None)
        rsi_low_idx = [i for i, r in enumerate(recent_rsi) if r == rsi_low][0]

        signals = []
        if c_high_idx > rsi_high_idx and c_high > recent_c[rsi_high_idx]:
            signals.append("顶背离（价格新高、RSI不新高）")
        if c_low_idx > rsi_low_idx and c_low < recent_c[rsi_low_idx]:
            signals.append("底背离（价格新低、RSI不新低）")
        return "; ".join(signals) if signals else "无明显背离"

    return {
        "code": "",
        "latest_price": round(closes[-1], 4) if closes else None,
        "latest_date": data[-1]["date"] if data else None,
        "moving_averages": {k: latest(v) for k, v in mas.items()},
        "ema": {k: latest(v) for k, v in emas.items()},
        "macd": {"DIF": latest(dif), "DEA": latest(dea), "BAR": latest(macd_bar)},
        "rsi": {k: latest(v) for k, v in rsis.items()},
        "kdj": {"K": latest(K), "D": latest(D), "J": latest(J)},
        "bollinger": {"mid": latest(bb_mid), "upper": latest(bb_upper), "lower": latest(bb_lower)},
        "atr": latest(atr_vals),
        "obv_latest": latest(obv_vals),
        "mfi": latest(mfi_vals),
        "trend": trend_judgment(),
        "support_resistance": find_levels(),
        "divergence": check_divergence(rsis["RSI14"]),
        "price_vs_ma": {
            "vs_MA20": round((closes[-1] / mas["MA20"][-1] - 1) * 100, 2) if mas["MA20"][-1] else None,
            "vs_MA60": round((closes[-1] / mas["MA60"][-1] - 1) * 100, 2) if mas["MA60"][-1] else None,
            "vs_MA120": round((closes[-1] / mas["MA120"][-1] - 1) * 100, 2) if mas["MA120"][-1] else None,
            "vs_MA250": round((closes[-1] / mas["MA250"][-1] - 1) * 100, 2) if mas["MA250"][-1] else None,
        },
        "computed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def compute_quant_stats(data: list[dict]) -> dict:
    """计算量化统计指标"""
    closes = [d["close"] for d in data]

    # 收益率
    def period_return(days: int) -> float | None:
        if len(closes) <= days:
            return None
        return round((closes[-1] / closes[-days - 1] - 1) * 100, 2)

    # 年化波动率
    if len(closes) < 2:
        return {}
    log_returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    avg_log_ret = sum(log_returns) / len(log_returns)
    annualized_vol = math.sqrt(sum((r - avg_log_ret) ** 2 for r in log_returns) / (len(log_returns) - 1)) * math.sqrt(252) if len(log_returns) > 1 else 0

    # 最大回撤
    peak = closes[0]
    max_dd = 0.0
    for c in closes:
        if c > peak:
            peak = c
        dd = (peak - c) / peak
        max_dd = max(max_dd, dd)

    # 夏普比率（假设无风险利率 2%）
    rf = 0.02
    sharpe = ((avg_log_ret * 252) - rf) / annualized_vol if annualized_vol > 0 else 0

    # 索提诺比率
    downside = [r for r in log_returns if r < 0]
    downside_std = math.sqrt(sum(r**2 for r in downside) / len(downside)) * math.sqrt(252) if downside else 0
    sortino = ((avg_log_ret * 252) - rf) / downside_std if downside_std > 0 else 0

    # VaR (95% 置信，历史模拟法)
    sorted_returns = sorted(log_returns)
    var_idx = int(len(sorted_returns) * 0.05)
    var_95 = abs(sorted_returns[var_idx]) if var_idx < len(sorted_returns) else None

    return {
        "returns": {
            "5d_pct": period_return(5),
            "20d_pct": period_return(20),
            "60d_pct": period_return(60),
            "120d_pct": period_return(120),
            "250d_pct": period_return(250),
        },
        "annualized_volatility_pct": round(annualized_vol * 100, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "sharpe_ratio": round(sharpe, 3),
        "sortino_ratio": round(sortino, 3),
        "var_95_daily_pct": round(var_95 * 100, 4) if var_95 else None,
    }


def main():
    parser = argparse.ArgumentParser(description="技术指标计算与回测")
    parser.add_argument("--input", required=True, help="输入行情 JSON 文件路径")
    parser.add_argument("--output", required=True, help="输出指标 JSON 文件路径")
    parser.add_argument("--fee", type=float, default=0.001, help="交易手续费率（默认 0.1%%）")
    args = parser.parse_args()

    # 读取行情数据
    with open(args.input, "r", encoding="utf-8") as f:
        quotes = json.load(f)

    data = quotes.get("data", [])
    if not data:
        print("[ERROR] 行情数据为空")
        sys.exit(1)

    print(f"加载 {len(data)} 条行情数据")

    # 计算技术指标
    indicators = compute_all_indicators(data)
    indicators["code"] = quotes.get("code", "")

    # 量化统计
    quant = compute_quant_stats(data)

    # 策略回测
    backtests = {
        "ma_cross_20_60": backtest_ma_cross(data, fast=20, slow=60, fee=args.fee),
        "macd": backtest_macd(data, fee=args.fee),
        "rsi_30_70": backtest_rsi(data, fee=args.fee),
        "trend_breakout": backtest_breakout(data, fee=args.fee),
    }

    result = {
        "indicators": indicators,
        "quant_stats": quant,
        "backtests": backtests,
        "computed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] 指标计算结果已写入 {args.output}")


if __name__ == "__main__":
    main()
