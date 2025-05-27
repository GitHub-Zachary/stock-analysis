# 股票分析系统

这是一个自动化股票分析系统，可以每日监控多只股票的表现，分析买入机会，并自动发送包含分析结果的邮件报告。

## 主要功能

- 获取股票数据：价格、交易量、技术指标等
- 计算关键技术指标：移动平均线、RSI、MACD、布林带等
- 检测异常价格变动（如股票拆分）
- 基于多种买入信号进行分析：
  - RSI低于阈值（超卖）
  - 价格低于50日均线但高于200日均线（技术回调）
  - 价格在52周范围的下1/3位置
  - 黄金交叉形态（50日均线在200日均线之上）且价格在50日均线附近
- 生成股价走势图
- 发送包含完整分析的HTML格式邮件报告
- 通过GitHub Actions自动化运行

## 项目结构

```
stock_analysis/
├── stock_analysis/           # 主模块
│   ├── __init__.py           # 包初始化
│   ├── data.py               # 数据获取和处理
│   ├── indicators.py         # 技术指标计算
│   ├── strategies.py         # 买入策略
│   ├── visualization.py      # 图表生成
│   ├── reporting.py          # 邮件报告
│   └── utils.py              # 工具函数
├── scripts/
│   └── run_analysis.py       # 主运行脚本
├── config.yaml               # 配置文件
└── .github/
    └── workflows/
        └── stock-analysis.yml  # GitHub Actions工作流
```

## 配置说明

系统通过`config.yaml`文件进行配置：

```yaml
# Alpha Vantage API配置
api_key: ""  # 留空使用环境变量 ALPHA_VANTAGE_API_KEY

# 股票配置
symbols:
  - AAPL
  - NVDA
  - MSFT
  - TSLA

# 股票中文名称映射
symbol_names:
  TSLA: "特斯拉"
  AAPL: "苹果"
  MSFT: "微软"
  NVDA: "英伟达"

# 策略参数
strategy:
  rsi_threshold: 30              # RSI超卖阈值
  price_position_threshold: 33   # 价格位置阈值(%)
  ma_proximity_threshold: 0.05   # 均线附近阈值(5%)
  anomaly_threshold: 0.15        # 异常价格变动阈值(15%)
```

## 使用方法

### 命令行参数

- `--config`：指定配置文件路径（默认为`config.yaml`）
- `--symbol`：分析单一股票（例如：`--symbol TSLA`）
- `--symbols`：分析多只股票（例如：`--symbols TSLA,AAPL,NVDA`）
- `--no-email`：仅进行分析，不发送邮件
- `--cache-expiry`：设置缓存过期时间（小时）

### GitHub Actions自动化

该项目配置了GitHub Actions工作流，可以：
- 每个工作日美国东部时间16:30自动运行
- 通过手动触发工作流并指定股票代码运行

## 环境要求

- Python 3.6+
- 依赖库：requests, pandas, numpy, matplotlib, pyyaml

## 注意事项

- Alpha Vantage API有使用频率限制，建议不要过于频繁地运行脚本
- 邮件发送需要正确配置邮箱服务器信息
- Gmail用户需要使用应用密码而不是账户密码
