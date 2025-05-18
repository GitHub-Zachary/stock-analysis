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

## 配置说明

系统通过`config.yaml`文件进行配置：

```yaml
# Alpha Vantage API配置
api_key: ""  # 留空使用环境变量

# 股票配置
symbols:
  - TSLA
  - AAPL
  - NVDA

# 股票中文名称映射
symbol_names:
  TSLA: "特斯拉"
  AAPL: "苹果"
  NVDA: "英伟达"

# 策略参数
strategy:
  rsi_threshold: 30              # RSI超卖阈值
  price_position_threshold: 33   # 价格位置阈值(%)
  ma_proximity_threshold: 0.05   # 均线附近阈值(5%)
  anomaly_threshold: 0.15        # 异常价格变动阈值(15%)
