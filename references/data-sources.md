# ETF 分析数据源参考

## 数据获取规范

1. 优先使用公开、合法、可访问的数据源
2. 在报告中明确列出实际使用的数据源、接口名称、数据日期和获取时间
3. 无法获取的数据标注为「未获取」或「公开数据不足」
4. 不同数据源冲突时，列出差异并说明采用依据

---

## 数据质量标注（P0）

所有获取到的数据**必须**标注质量等级：

| 质量等级 | 含义 | 示例 |
|----------|------|------|
| verified | 实时或当日数据，来源权威 | 实时行情、交易所公告 |
| estimated | 基于历史数据推算，或存在延迟 | 季报持仓（延迟45天+）、估值估算 |
| missing | 完全无法获取 | 某些财务指标、非A股持仓详情 |
| stale | 数据已过时，可能不再反映真实情况 | 超过60天的持仓数据、过时新闻 |

标注格式：
```json
"data_quality": {
  "price": {"quality": "verified", "delay_days": 0},
  "holdings": {"quality": "stale", "delay_days": 45, "note": "基于最新季报"}
}
```

**综合数据质量**：在 signal schema 中使用整体判断：
- `verified`：核心数据全部 verified
- `estimated`：部分关键数据为 estimated
- `mixed`：多种质量混合，需谨慎
- `missing`：关键数据缺失，结论置信度大幅降低

---

## 事件证据等级

对新闻、公告、政策等信息**必须**标注证据等级：

| 等级 | 证据来源 | 行动含义 |
|------|----------|----------|
| A | 公司公告、交易所文件、监管披露、财报 | 可进入候选 |
| B | 权威财经媒体、多源交叉验证、产业链确认 | 可观察或候选 |
| C | 单一媒体、传闻、社媒热度 | 只观察 |
| D | 无法核验、标题党、盘后小作文 | 禁止作为买入理由 |

标注格式：
```json
{"title": "...", "evidence_level": "A", "source": "上交所公告", ...}
```

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

| 数据 | 接口函数 | 参数示例 | 数据质量 |
|------|---------|---------|---------|
| ETF 基本信息 | `fund_etf_fund_info_em()` | `fund="510300"` | verified |
| ETF 实时行情 | `fund_etf_spot_em()` | 无 | verified |
| ETF 历史行情 | `fund_etf_hist_em()` | `symbol="510300"` | verified |
| ETF 持仓明细 | `fund_etf_hold_detail_em()` | `fund="510300"` | stale（季报延迟） |
| ETF 基金规模变动 | `fund_etf_scale_em()` | `fund="510300"` | estimated |
| 指数行情 | `index_zh_a_hist()` | `symbol="sh000300"` | verified |
| 指数成分股 | `index_stock_cons()` | `index="000300"` | stale |
| 股票基本信息 | `stock_individual_info_em()` | `symbol="600519"` | verified |
| 股票财务指标 | `stock_financial_analysis_indicator()` | `symbol="600519"` | stale（季报延迟） |
| 股票历史行情 | `stock_zh_a_hist()` | `symbol="600519"` | verified |
| 资金流向 | `stock_individual_fund_flow()` | `symbol="600519"` | estimated |

### 网页数据源（WebFetch）

| 数据源 | URL | 用途 | 证据等级 |
|--------|-----|------|---------|
| 东方财富 ETF 中心 | `https://fund.eastmoney.com/etf/` | ETF 列表、基本信息 | B |
| 天天基金 ETF | `https://fund.eastmoney.com/fund.html` | 基金详情、持仓 | B |
| 巨潮资讯 | `http://www.cninfo.com.cn/` | 基金公告、财报 | A |
| 上交所官网 | `http://www.sse.com.cn/` | 上交所 ETF 列表、公告 | A |
| 深交所官网 | `http://www.szse.cn/` | 深交所 ETF 列表、公告 | A |
| 中证指数官网 | `https://www.csindex.com.cn/` | 指数详情、成分股、估值 | A |
| 国证指数官网 | `https://www.cnindex.com.cn/` | 指数信息 | A |
| 新浪财经 | `https://finance.sina.com.cn/` | 行情、新闻 | C |
| 雪球 | `https://xueqiu.com/` | 用户讨论、情绪分析 | D |
| 东方财富股吧 | `https://guba.eastmoney.com/` | 散户情绪 | D |

---

## 美股 / 港股 ETF 数据源

| 数据源 | 用途 | 方式 | 证据等级 |
|--------|------|------|---------|
| Yahoo Finance | 美股/港股 ETF 行情、基本信息 | `yfinance` 库或 WebFetch | B |
| SEC EDGAR | 美股基金公告、持仓 | `https://www.sec.gov/edgar/` | A |
| ETF.com | 美股 ETF 分析 | `https://www.etf.com/` | B |
| ETFdb.com | 美股 ETF 数据库 | `https://etfdb.com/` | B |

---

## 数据获取优先级

在实际分析中，按以下优先级尝试：

1. **AKShare**（优先，覆盖面最广，免费，无需额外配置）
2. **东方财富 / 天天基金**（通过 efinance 库或 WebFetch）
3. **交易所官网**（上交所、深交所，数据权威但接口可能不友好）
4. **新浪财经 / 腾讯财经**（通过 WebFetch）
5. **Yahoo Finance**（美股/港股首选，通过 yfinance）
6. **雪球 / 股吧**（情绪分析，通过 WebFetch，证据等级 D）

如果前序数据源可以满足分析需求，可跳过后续数据源。

---

## 常见降级策略

| 场景 | 降级方案 | 数据质量标注 |
|------|---------|-------------|
| 无法获取持仓明细 | 使用跟踪指数的成分股作为代理 | `estimated`，标注"使用指数成分股代理" |
| 无法获取分钟级行情 | 仅使用日线数据，注明精度限制 | `verified`（日线），标注精度 |
| 无法获取机构研报 | 仅使用公开新闻和社交媒体情绪 | `missing`（研报） |
| 无法获取完整财务数据 | 使用最近的季报或半年报数据 | `stale`，标注报告期和延迟天数 |
| 数据源之间数据冲突 | 优先采用交易所官网数据，其次基金公司官网，最后第三方数据平台 | 标注采用依据和冲突详情 |
