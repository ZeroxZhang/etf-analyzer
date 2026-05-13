# ETF 分析数据源参考

## 数据获取规范

1. 优先使用公开、合法、可访问的数据源
2. 在报告中明确列出实际使用的数据源、接口名称、数据日期和获取时间
3. 无法获取的数据标注为「未获取」或「公开数据不足」
4. 不同数据源冲突时，列出差异并说明采用依据

---

## 中国 A 股 / 场内 ETF 数据源

### Python 库

| 库 | 用途 | 安装 |
|----|------|------|
| **AKShare** | 最全面的中国金融数据接口，覆盖 ETF 信息、行情、持仓、指数 | `pip install akshare` |
| **Tushare** | 股票/基金/指数数据，需注册获取 token | `pip install tushare` |
| **efinance** | 东方财富数据接口 | `pip install efinance` |
| **baostock** | 免费证券数据 | `pip install baostock` |
| **yfinance** | 美股/港股 ETF 数据 | `pip install yfinance` |

### 常用 AKShare 接口

| 数据 | 接口函数 | 参数示例 |
|------|---------|---------|
| ETF 基本信息 | `fund_etf_fund_info_em()` | `fund="510300"` |
| ETF 实时行情 | `fund_etf_spot_em()` | 无 |
| ETF 历史行情 | `fund_etf_hist_em()` | `symbol="510300"` |
| ETF 持仓明细 | `fund_etf_hold_detail_em()` | `fund="510300"` |
| ETF 基金规模变动 | `fund_etf_scale_em()` | `fund="510300"` |
| 指数行情 | `index_zh_a_hist()` | `symbol="sh000300"` |
| 指数成分股 | `index_stock_cons()` | `index="000300"` |
| 股票基本信息 | `stock_individual_info_em()` | `symbol="600519"` |
| 股票财务指标 | `stock_financial_analysis_indicator()` | `symbol="600519"` |
| 股票历史行情 | `stock_zh_a_hist()` | `symbol="600519"` |
| 资金流向 | `stock_individual_fund_flow()` | `symbol="600519"` |

### 网页数据源（WebFetch）

| 数据源 | URL | 用途 |
|--------|-----|------|
| 东方财富 ETF 中心 | `https://fund.eastmoney.com/etf/` | ETF 列表、基本信息 |
| 天天基金 ETF | `https://fund.eastmoney.com/fund.html` | 基金详情、持仓 |
| 巨潮资讯 | `http://www.cninfo.com.cn/` | 基金公告、财报 |
| 上交所官网 | `http://www.sse.com.cn/` | 上交所 ETF 列表、公告 |
| 深交所官网 | `http://www.szse.cn/` | 深交所 ETF 列表、公告 |
| 中证指数官网 | `https://www.csindex.com.cn/` | 指数详情、成分股、估值 |
| 国证指数官网 | `https://www.cnindex.com.cn/` | 指数信息 |
| 新浪财经 | `https://finance.sina.com.cn/` | 行情、新闻 |
| 雪球 | `https://xueqiu.com/` | 用户讨论、情绪分析 |
| 东方财富股吧 | `https://guba.eastmoney.com/` | 散户情绪 |

---

## 美股 / 港股 ETF 数据源

| 数据源 | 用途 | 方式 |
|--------|------|------|
| Yahoo Finance | 美股/港股 ETF 行情、基本信息 | `yfinance` 库或 WebFetch |
| SEC EDGAR | 美股基金公告、持仓 | `https://www.sec.gov/edgar/` |
| ETF.com | 美股 ETF 分析 | `https://www.etf.com/` |
| ETFdb.com | 美股 ETF 数据库 | `https://etfdb.com/` |

---

## 数据获取优先级

在实际分析中，按以下优先级尝试：

1. **AKShare**（优先，覆盖面最广，免费，无需额外配置）
2. **东方财富 / 天天基金**（通过 efinance 库或 WebFetch）
3. **交易所官网**（上交所、深交所，数据权威但接口可能不友好）
4. **新浪财经 / 腾讯财经**（通过 WebFetch）
5. **Yahoo Finance**（美股/港股首选，通过 yfinance）
6. **雪球 / 股吧**（情绪分析，通过 WebFetch）

如果前序数据源可以满足分析需求，可跳过后续数据源。

---

## 常见降级策略

| 场景 | 降级方案 |
|------|---------|
| 无法获取持仓明细 | 使用跟踪指数的成分股作为代理 |
| 无法获取分钟级行情 | 仅使用日线数据，注明精度限制 |
| 无法获取机构研报 | 仅使用公开新闻和社交媒体情绪 |
| 无法获取完整财务数据 | 使用最近的季报或半年报数据 |
| 数据源之间数据冲突 | 优先采用交易所官网数据，其次基金公司官网，最后第三方数据平台 |
