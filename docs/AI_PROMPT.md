## docs/AI_PROMPT.md

```markdown
# AI助手提示词

此文档包含向AI助手(如Claude或ChatGPT)介绍本项目时使用的提示词。当需要AI帮助理解代码、解决问题或提供更新建议时，可以使用此提示词。

---

我有一个名为"stock-analysis"的GitHub存储库，这是一个自动化股票分析系统，用于监控多只股票的表现，分析买入机会，并通过邮件发送分析报告。

存储库结构：
/
├── .github/workflows/
│   └── stock-analysis.yml - GitHub Actions工作流配置，每个工作日自动运行
├── scripts/
│   └── run_analysis.py - 主运行脚本，处理命令行参数和流程控制
├── stock_analysis/ - 主模块目录
│   ├── __init__.py - 包初始化文件
│   ├── data.py - 数据获取和处理模块，包含API调用和缓存逻辑
│   ├── indicators.py - 技术指标计算模块，处理MA/RSI/MACD等指标
│   ├── reporting.py - 邮件报告模块，生成和发送分析报告
│   ├── strategies.py - 买入策略模块，分析股票是否适合买入
│   ├── utils.py - 工具函数模块，包含日志和配置加载等功能
│   └── visualization.py - 可视化模块，生成股票图表
├── docs/ - 文档目录
│   └── AI_PROMPT.md - AI助手提示词
├── README.md - 项目说明文档
└── config.yaml - 配置文件，包含股票列表和策略参数等

核心功能：
1. 从Alpha Vantage API获取股票数据
2. 计算关键技术指标：MA/RSI/MACD等
3. 基于四种买入信号分析：RSI超卖、技术回调、价格位置、黄金交叉
4. 检测异常价格变动
5. 生成股价走势图
6. 发送包含分析结果的HTML邮件报告
7. GitHub Actions自动化运行

监控的股票（按顺序）：
- 苹果 (AAPL)
- 英伟达 (NVDA)
- 微软 (MSFT)
- 特斯拉 (TSLA)

环境要求：
- Python 3.6+
- 依赖库：requests, pandas, numpy, matplotlib, pyyaml

此系统使用模块化设计，易于扩展新的技术指标和买入策略。未来计划增加更多指标、回测功能和更丰富的可视化组件。
