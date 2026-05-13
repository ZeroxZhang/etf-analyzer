#!/usr/bin/env python3
"""
ETF 数据获取脚本。

支持模式：
  basics   — ETF 基础信息（名称、代码、交易所、管理人、费率、规模、净值等）
  quotes   — ETF 历史日线行情（OHLCV，默认 2 年）
  holdings — ETF 完整持仓列表（代码、名称、权重、行业）
  index    — 跟踪指数数据（名称、成分股、估值、历史分位）
  stock    — 单只 A 股基本信息 + 财务指标 + 近期行情
  all      — 以上全部

用法：
  python fetch_etf_data.py --code 510300 --mode basics --output ./data/
  python fetch_etf_data.py --code 510300 --mode all --output ./data/
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

# 顶层导入，提前检测缺失依赖
try:
    import akshare as ak

    HAS_AKSHARE = True
except ImportError:
    ak = None  # type: ignore
    HAS_AKSHARE = False

try:
    import yfinance as yf

    HAS_YFINANCE = True
except ImportError:
    yf = None  # type: ignore
    HAS_YFINANCE = False


def detect_exchange(code: str) -> str:
    """识别 ETF 所属交易所"""
    if not code.isdigit():
        return "美股/港股"
    first_char = code[0]
    if first_char == "5":
        return "上交所"
    elif first_char in ("0", "1", "3"):
        return "深交所"
    return f"未知（代码：{code}）"


def ensure_output_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def fetch_basics_akshare(etf_code: str, output_dir: str) -> dict:
    """使用 AKShare 获取 ETF 基础信息"""
    if not HAS_AKSHARE:
        return {"error": "akshare 未安装，请运行 pip install akshare"}
    try:

        # 获取 ETF 实时行情列表，筛选目标代码
        df = ak.fund_etf_spot_em()
        row = df[df["代码"] == etf_code]
        if row.empty:
            return {"error": f"未找到 ETF 代码 {etf_code}", "source": "AKShare/fund_etf_spot_em"}

        row = row.iloc[0]
        result = {
            "code": str(row.get("代码", "")),
            "name": str(row.get("名称", "")),
            "exchange": detect_exchange(etf_code),
            "type": str(row.get("类型", "")),
            "price": float(row.get("最新价", 0)) if row.get("最新价") else None,
            "nav": float(row.get("IOPV", 0)) if row.get("IOPV") else None,
            "change_pct": float(row.get("涨跌幅", 0)) if row.get("涨跌幅") else None,
            "volume": float(row.get("成交量", 0)) if row.get("成交量") else None,
            "amount": float(row.get("成交额", 0)) if row.get("成交额") else None,
            "source": "AKShare/fund_etf_spot_em",
            "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        # 尝试获取更多基础信息
        try:
            info_df = ak.fund_etf_fund_info_em(fund=etf_code)
            if not info_df.empty:
                info = info_df.iloc[0]
                result["manager"] = str(info.get("基金管理人", ""))
                result["custodian"] = str(info.get("基金托管人", ""))
                result["inception_date"] = str(info.get("成立日期", ""))
                result["list_date"] = str(info.get("上市日期", ""))
                result["tracking_index"] = str(info.get("跟踪指数", ""))
                result["management_fee"] = float(info.get("管理费率", 0)) if info.get("管理费率") else None
                result["custodian_fee"] = float(info.get("托管费率", 0)) if info.get("托管费率") else None
                result["total_size"] = float(info.get("基金规模", 0)) if info.get("基金规模") else None
        except Exception:
            pass  # 基础信息补充失败不影响主流程

        # 计算折溢价
        if result.get("price") and result.get("nav") and result["nav"] > 0:
            result["premium"] = round((result["price"] - result["nav"]) / result["nav"] * 100, 2)

        path = os.path.join(output_dir, "etf_basics.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[OK] ETF 基础信息已写入 {path}")
        return result

    except Exception as e:
        return {"error": str(e), "source": "AKShare"}


def fetch_quotes_akshare(etf_code: str, output_dir: str, years: int = 2) -> dict:
    """使用 AKShare 获取 ETF 历史日线行情"""
    if not HAS_AKSHARE:
        return {"error": "akshare 未安装，请运行 pip install akshare"}
    try:

        start_date = (datetime.now() - timedelta(days=years * 365)).strftime("%Y%m%d")
        end_date = datetime.now().strftime("%Y%m%d")

        df = ak.fund_etf_hist_em(symbol=etf_code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")

        if df is None or df.empty:
            return {"error": f"未获取到 {etf_code} 历史行情数据", "source": "AKShare/fund_etf_hist_em"}

        data = []
        for _, row in df.iterrows():
            data.append({
                "date": str(row.get("日期", "")),
                "open": float(row.get("开盘", 0)) if row.get("开盘") else None,
                "high": float(row.get("最高", 0)) if row.get("最高") else None,
                "low": float(row.get("最低", 0)) if row.get("最低") else None,
                "close": float(row.get("收盘", 0)) if row.get("收盘") else None,
                "volume": float(row.get("成交量", 0)) if row.get("成交量") else None,
                "amount": float(row.get("成交额", 0)) if row.get("成交额") else None,
            })

        result = {
            "code": etf_code,
            "data": data,
            "count": len(data),
            "date_range": f"{data[0]['date']} ~ {data[-1]['date']}" if data else "empty",
            "source": "AKShare/fund_etf_hist_em",
            "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        path = os.path.join(output_dir, "etf_quotes.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[OK] ETF 行情数据已写入 {path}（{len(data)} 条）")
        return result

    except Exception as e:
        return {"error": str(e)}


def fetch_holdings_akshare(etf_code: str, output_dir: str) -> dict:
    """使用 AKShare 获取 ETF 持仓数据"""
    if not HAS_AKSHARE:
        return {"error": "akshare 未安装，请运行 pip install akshare"}
    try:

        df = ak.fund_etf_hold_detail_em(fund=etf_code)
        if df is None or df.empty:
            return {"error": f"未获取到 {etf_code} 持仓数据", "source": "AKShare/fund_etf_hold_detail_em"}

        holdings = []
        for _, row in df.iterrows():
            raw_weight = float(row.get("占净值比例", row.get("权重", 0)))
            # AKShare 返回的占净值比例可能是百分比（如 5.0 表示 5%）或小数（如 0.05 表示 5%）
            weight = raw_weight / 100.0 if raw_weight > 1 else raw_weight
            holdings.append({
                "code": str(row.get("股票代码", row.get("代码", ""))),
                "name": str(row.get("股票名称", row.get("名称", ""))),
                "weight": round(weight, 6),
                "shares": float(row.get("持股数", row.get("持仓数量", 0))) if row.get("持股数") or row.get("持仓数量") else None,
                "market_value": float(row.get("持仓市值", 0)) if row.get("持仓市值") else None,
            })

        result = {
            "etf_code": etf_code,
            "total_holdings": len(holdings),
            "holdings": holdings,
            "top10_weight_sum": round(sum(h["weight"] for h in holdings[:10]), 4) if len(holdings) >= 10 else None,
            "source": "AKShare/fund_etf_hold_detail_em",
            "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        path = os.path.join(output_dir, "holdings.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[OK] 持仓数据已写入 {path}（{len(holdings)} 只标的）")
        return result

    except Exception as e:
        return {"error": str(e)}


def fetch_index_akshare(etf_code: str, output_dir: str) -> dict:
    """获取 ETF 跟踪指数的数据"""
    if not HAS_AKSHARE:
        return {"error": "akshare 未安装，请运行 pip install akshare"}
    try:

        # 先获取 ETF 基本信息以确定跟踪指数
        try:
            info_df = ak.fund_etf_fund_info_em(fund=etf_code)
            tracking_index = str(info_df.iloc[0].get("跟踪指数", "")) if not info_df.empty else ""
        except Exception:
            tracking_index = ""

        # 映射常见跟踪指数到指数代码
        index_map = {
            "沪深300": "000300",
            "中证500": "000905",
            "中证1000": "000852",
            "上证50": "000016",
            "科创50": "000688",
            "创业板指": "399006",
            "中证红利": "000922",
            "中证全指证券公司": "399975",
            "中证银行": "399986",
            "中证军工": "399967",
            "中证白酒": "399997",
            "中证医疗": "399989",
            "中证新能源": "399808",
            "国证芯片": "980017",
        }

        index_code = None
        for name, code in index_map.items():
            if name in tracking_index:
                index_code = code
                break

        result = {
            "etf_code": etf_code,
            "tracking_index_name": tracking_index,
            "index_code": index_code,
            "source": "AKShare",
            "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        # 尝试获取指数估值
        if index_code:
            try:
                pe_df = ak.index_value_hist_funddb(symbol=index_code, indicator="市盈率")
                pb_df = ak.index_value_hist_funddb(symbol=index_code, indicator="市净率")

                def get_latest_and_percentile(df):
                    if df is None or df.empty:
                        return None, None
                    latest = float(df.iloc[-1].get("市盈率", df.iloc[-1].get("市净率", 0)))
                    values = [float(v) for v in df.iloc[:, 1] if float(v) > 0]
                    percentile = round(sum(1 for v in values if v <= latest) / len(values) * 100, 2) if values else None
                    return latest, percentile

                pe_val, pe_pct = (None, None)
                pb_val, pb_pct = (None, None)
                if pe_df is not None and not pe_df.empty:
                    pe_val, pe_pct = get_latest_and_percentile(pe_df)
                if pb_df is not None and not pb_df.empty:
                    pb_val, pb_pct = get_latest_and_percentile(pb_df)

                result["pe"] = pe_val
                result["pe_percentile"] = pe_pct
                result["pb"] = pb_val
                result["pb_percentile"] = pb_pct
            except Exception:
                result["pe"] = None
                result["pb"] = None

        path = os.path.join(output_dir, "index_data.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[OK] 指数数据已写入 {path}")
        return result

    except Exception as e:
        return {"error": str(e)}


def fetch_stock_info_akshare(stock_code: str, output_dir: str) -> dict:
    """使用 AKShare 获取单只 A 股基本信息 + 财务指标"""
    if not HAS_AKSHARE:
        return {"error": "akshare 未安装，请运行 pip install akshare"}
    try:

        result = {"code": stock_code, "source": "AKShare", "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M")}

        # 个股基本信息
        try:
            info_df = ak.stock_individual_info_em(symbol=stock_code)
            if not info_df.empty:
                info_dict = dict(zip(info_df["item"], info_df["value"]))
                result["name"] = str(info_dict.get("股票简称", ""))
                result["sector"] = str(info_dict.get("行业", ""))
                result["total_market_cap"] = float(info_dict.get("总市值", 0)) if info_dict.get("总市值") else None
                result["circulating_market_cap"] = float(info_dict.get("流通市值", 0)) if info_dict.get("流通市值") else None
        except Exception:
            pass

        # 财务指标
        try:
            fin_df = ak.stock_financial_analysis_indicator(symbol=stock_code)
            if fin_df is not None and not fin_df.empty:
                latest = fin_df.iloc[0]
                result["financials"] = {
                    "roe": float(latest.get("净资产收益率", 0)) if latest.get("净资产收益率") else None,
                    "net_margin": float(latest.get("销售净利率", 0)) if latest.get("销售净利率") else None,
                    "gross_margin": float(latest.get("销售毛利率", 0)) if latest.get("销售毛利率") else None,
                    "debt_ratio": float(latest.get("资产负债率", 0)) if latest.get("资产负债率") else None,
                    "revenue_growth": float(latest.get("营业收入同比增长", 0)) if latest.get("营业收入同比增长") else None,
                    "profit_growth": float(latest.get("净利润同比增长", 0)) if latest.get("净利润同比增长") else None,
                    "report_date": str(latest.get("报告期", "")),
                }
        except Exception:
            result["financials"] = None

        # 近期行情
        try:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
            price_df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
            if price_df is not None and not price_df.empty:
                latest_close = float(price_df.iloc[-1]["收盘"])
                result["price_data"] = {
                    "latest_price": latest_close,
                    "change_1m": None,  # 需要更多数据计算
                    "change_3m": None,
                    "change_1y": None,
                }
                if len(price_df) >= 20:
                    result["price_data"]["change_1m"] = round((latest_close - float(price_df.iloc[-20]["收盘"])) / float(price_df.iloc[-20]["收盘"]) * 100, 2)
                if len(price_df) >= 60:
                    result["price_data"]["change_3m"] = round((latest_close - float(price_df.iloc[-60]["收盘"])) / float(price_df.iloc[-60]["收盘"]) * 100, 2)
                if len(price_df) >= 250:
                    result["price_data"]["change_1y"] = round((latest_close - float(price_df.iloc[0]["收盘"])) / float(price_df.iloc[0]["收盘"]) * 100, 2)
        except Exception:
            result["price_data"] = None

        # 写入文件（每个标的单独文件）
        path = os.path.join(output_dir, f"stock_{stock_code}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[OK] 个股数据已写入 {path}")
        return result

    except Exception as e:
        return {"error": str(e)}


def fetch_yfinance(etf_code: str, output_dir: str) -> dict:
    """使用 yfinance 获取美股/港股 ETF 数据（备用）"""
    if not HAS_YFINANCE:
        return {"error": "yfinance 未安装，请运行 pip install yfinance"}
    try:

        ticker = yf.Ticker(etf_code)
        # yfinance .info 属性可能发起多轮网络请求，使用 fast_info 减少延迟
        try:
            info = ticker.info
        except Exception:
            info = {}

        # 基础信息
        basics = {
            "code": etf_code,
            "name": info.get("shortName") or info.get("longName", ""),
            "exchange": info.get("exchange", ""),
            "type": info.get("quoteType", ""),
            "price": info.get("regularMarketPrice"),
            "nav": info.get("navPrice"),
            "size": info.get("totalAssets"),
            "management_fee": info.get("annualReportExpenseRatio"),
            "avg_volume": info.get("averageVolume"),
            "inception_date": info.get("fundInceptionDate"),
            "tracking_index": info.get("underlyingSymbol", ""),
            "source": "Yahoo Finance",
            "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        path = os.path.join(output_dir, "etf_basics.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(basics, f, ensure_ascii=False, indent=2)
        print(f"[OK] ETF 基础信息(yfinance)已写入 {path}")

        # 历史行情
        hist = ticker.history(period="2y")
        data = []
        for date, row in hist.iterrows():
            data.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row["Volume"]),
            })

        quotes = {
            "code": etf_code,
            "data": data,
            "count": len(data),
            "date_range": f"{data[0]['date']} ~ {data[-1]['date']}" if data else "empty",
            "source": "Yahoo Finance",
            "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        path = os.path.join(output_dir, "etf_quotes.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(quotes, f, ensure_ascii=False, indent=2)
        print(f"[OK] ETF 行情数据(yfinance)已写入 {path}（{len(data)} 条）")

        return basics

    except Exception as e:
        return {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="ETF 数据获取脚本")
    parser.add_argument("--code", required=True, help="ETF 代码，如 510300")
    parser.add_argument("--mode", default="all",
                        choices=["basics", "quotes", "holdings", "index", "stock", "all"],
                        help="获取模式（默认 all）")
    parser.add_argument("--output", default="./data/", help="输出目录（默认 ./data/）")
    parser.add_argument("--source", default="akshare", choices=["akshare", "yfinance"],
                        help="数据源（默认 akshare，美股 ETF 建议用 yfinance）")
    args = parser.parse_args()

    output_dir = ensure_output_dir(args.output)

    # 判断是否是美股/港股代码（包含字母）
    is_cn_etf = args.code.isdigit() and len(args.code) == 6

    if args.source == "yfinance" or not is_cn_etf:
        if args.mode in ("basics", "all"):
            fetch_yfinance(args.code, output_dir)
        else:
            print("[WARN] yfinance 模式下仅支持 basics/quotes。请使用 --mode basics 或 all")
        return

    # A 股 ETF
    modes = {
        "basics": lambda: fetch_basics_akshare(args.code, output_dir),
        "quotes": lambda: fetch_quotes_akshare(args.code, output_dir),
        "holdings": lambda: fetch_holdings_akshare(args.code, output_dir),
        "index": lambda: fetch_index_akshare(args.code, output_dir),
        "stock": lambda: fetch_stock_info_akshare(args.code, output_dir),
    }

    if args.mode == "all":
        for mode_name, fn in modes.items():
            if mode_name == "stock":
                continue  # stock 模式需要单独指定股票代码
            print(f"\n--- 获取 {mode_name} ---")
            result = fn()
            if isinstance(result, dict) and "error" in result:
                print(f"[FAIL] {mode_name}: {result['error']}")
    elif args.mode in modes:
        result = modes[args.mode]()
        if isinstance(result, dict) and "error" in result:
            print(f"[FAIL] {args.mode}: {result['error']}")
            sys.exit(1)
    else:
        print(f"未知模式: {args.mode}")


if __name__ == "__main__":
    main()
