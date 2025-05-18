import requests
import pandas as pd
import numpy as np
import os
import pickle
import smtplib
import logging
import argparse
import yaml
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import base64

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"stock_tracker_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_config(config_file="config.yaml"):
    """加载配置文件"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            logger.info(f"成功加载配置文件: {config_file}")
            return config
    except Exception as e:
        logger.error(f"加载配置文件失败: {str(e)}")
        # 返回默认配置
        return {
            "symbols": ["TSLA", "AAPL", "NVDA"],
            "symbol_names": {"TSLA": "特斯拉", "AAPL": "苹果", "NVDA": "英伟达"},
            "strategy": {
                "rsi_threshold": 30,
                "price_position_threshold": 33,
                "ma_proximity_threshold": 0.05,
                "anomaly_threshold": 0.15
            }
        }

def get_api_data(url, max_retries=3, retry_delay=10):
    """带重试机制的API请求函数"""
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url)
            data = response.json()
            
            # 检查是否返回了有效内容
            if "Note" in data and "API call frequency" in data["Note"]:
                logger.warning(f"API频率限制触发：{data['Note']}")
                time.sleep(retry_delay * (attempt + 1))  # 指数退避
                continue
                
            return data
        except Exception as e:
            logger.error(f"API请求失败 (尝试 {attempt+1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise

def detect_price_anomalies(df, threshold=0.15):
    """
    检测历史数据中异常价格变动
    
    参数:
    df (DataFrame): 包含至少'close'列的股票价格数据框架
    threshold (float): 触发异常检测的价格变动百分比阈值(默认15%)
    
    返回:
    dict: 包含检测结果的字典
    """
    # 确保数据按日期排序
    df = df.sort_index()
    
    # 计算每日价格变动百分比
    df['price_change_pct'] = df['close'].pct_change() * 100
    
    # 检查是否有任何一天价格变动超过阈值(正负)
    large_changes = df[abs(df['price_change_pct']) > threshold * 100]
    
    result = {
        "detected": False,
        "date": None,
        "change_pct": None
    }
    
    if not large_changes.empty:
        # 找出最大变动的日期
        max_change_idx = large_changes['price_change_pct'].abs().idxmax()
        change_pct = large_changes.loc[max_change_idx, 'price_change_pct']
        
        result["detected"] = True
        result["date"] = max_change_idx.strftime("%Y-%m-%d")
        result["change_pct"] = round(change_pct, 2)
    
    return result

def get_stock_data_with_cache(symbol, api_key, cache_dir="cache", cache_expiry_hours=4):
    """获取股票数据，支持本地缓存"""
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{symbol}_data.pkl")
    
    # 检查缓存是否存在且有效
    if os.path.exists(cache_file):
        file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
        if datetime.now() - file_time < timedelta(hours=cache_expiry_hours):
            try:
                with open(cache_file, 'rb') as f:
                    logger.info(f"使用缓存数据: {symbol}")
                    return pickle.load(f)
            except Exception as e:
                logger.warning(f"读取缓存失败: {str(e)}")
    
    # 获取新数据
    data = get_stock_data(symbol, api_key)
    
    # 保存到缓存
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(data, f)
    except Exception as e:
        logger.warning(f"保存缓存失败: {str(e)}")
    
    return data

def get_stock_data(symbol, api_key):
    """
    使用Alpha Vantage API获取股票的相关数据
    """
    logger.info(f"开始获取{symbol}股票数据...")
    
    # 获取股票日线数据
    url_daily = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&outputsize=full&apikey={api_key}"
    data_daily = get_api_data(url_daily)
    
    # 打印API响应的键，用于调试
    logger.debug(f"API Response Keys: {data_daily.keys()}")
    
    # 等待一下，避免API请求过快
    time.sleep(1)
    
    # 获取公司概览数据（包含市盈率）
    url_overview = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={symbol}&apikey={api_key}"
    data_overview = get_api_data(url_overview)
    
    # 打印概览数据的键，用于调试
    logger.debug(f"Overview Response Keys: {data_overview.keys()}")
    
    # 将日线数据转换为DataFrame
    time_series = data_daily.get("Time Series (Daily)", {})
    if not time_series:
        logger.error("Error: No time series data returned from API")
        logger.error(f"Full API response: {data_daily}")
        raise ValueError(f"Failed to get time series data from Alpha Vantage for {symbol}")
        
    df = pd.DataFrame(time_series).T
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    
    # 将字符串转换为浮点数
    for col in df.columns:
        df[col] = pd.to_numeric(df[col])
    
    # 重命名列
    df.columns = ['open', 'high', 'low', 'close', 'volume']
    
    # 计算技术指标
    df = calculate_technical_indicators(df)
    
    # 获取当前数据
    latest_date = df.index[-1]
    current_price = df.loc[latest_date, 'close']
    ma50 = df.loc[latest_date, 'ma50']
    ma200 = df.loc[latest_date, 'ma200']
    rsi = df.loc[latest_date, 'rsi']
    
    # 计算52周最高价和最低价
    one_year_ago = latest_date - timedelta(days=365)
    df_52_weeks = df[df.index >= one_year_ago]
    high_52_week = df_52_weeks['high'].max()
    low_52_week = df_52_weeks['low'].min()
    
    # 获取市盈率
    pe_ratio = float(data_overview.get("PERatio", 0))
    
    # 检测52周内是否有价格异常变动
    price_anomaly = detect_price_anomalies(df_52_weeks)
    
    # 构建结果数据字典，包含TTM市盈率和14日RSI
    result = {
        "date": latest_date.strftime("%Y-%m-%d"),
        "current_price": round(current_price, 2),
        "high_52_week": round(high_52_week, 2),
        "low_52_week": round(low_52_week, 2),
        "ma50": round(ma50, 2),
        "ma200": round(ma200, 2),
        "rsi": round(rsi, 2),  # 14日RSI
        "pe_ratio": round(pe_ratio, 2),  # TTM市盈率
        "price_anomaly": price_anomaly,  # 价格异常检测结果
        "df": df  # 添加完整的DataFrame用于绘图
    }
    
    logger.info(f"成功获取{symbol}股票数据，最新日期: {result['date']}")
    return result

def calculate_technical_indicators(df):
    """计算各种技术指标"""
    # 计算50日和200日移动平均线
    df['ma50'] = df['close'].rolling(window=50).mean()
    df['ma200'] = df['close'].rolling(window=200).mean()
    
    # 计算14日RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 添加MACD指标
    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp12 - exp26
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['signal']
    
    # 添加布林带
    df['ma20'] = df['close'].rolling(window=20).mean()
    std20 = df['close'].rolling(window=20).std()
    df['upper_band'] = df['ma20'] + (std20 * 2)
    df['lower_band'] = df['ma20'] - (std20 * 2)
    
    return df

def analyze_buy_strategy(data, strategy_params=None):
    """
    根据股票的数据分析是否适合买入
    返回买入策略分析结果
    """
    if strategy_params is None:
        strategy_params = {
            "rsi_threshold": 30,
            "price_position_threshold": 33,
            "ma_proximity_threshold": 0.05
        }
    
    current_price = data["current_price"]
    high_52_week = data["high_52_week"]
    low_52_week = data["low_52_week"]
    ma50 = data["ma50"]
    ma200 = data["ma200"]
    rsi = data["rsi"]
    pe_ratio = data["pe_ratio"]
    
    # 计算当前价格相对于52周范围的位置（0-100%）
    price_position = (current_price - low_52_week) / (high_52_week - low_52_week) * 100
    
    # 初始化买入信号
    buy_signals = []
    
    # 策略1: RSI < threshold 表示超卖，可能是买入机会
    rsi_threshold = strategy_params.get("rsi_threshold", 30)
    if rsi < rsi_threshold:
        buy_signals.append(f"RSI低于{rsi_threshold}，处于超卖区域")
    
    # 策略2: 价格低于50日均线但高于200日均线，可能是技术回调
    if current_price < ma50 and current_price > ma200:
        buy_signals.append("价格低于50日均线但高于200日均线，可能是技术回调")
    
    # 策略3: 价格在52周范围的下1/3位置
    price_position_threshold = strategy_params.get("price_position_threshold", 33)
    if price_position < price_position_threshold:
        buy_signals.append(f"价格在52周范围的下{price_position_threshold}%位置 ({price_position:.2f}%)")
    
    # 策略4: 50日均线在200日均线之上（黄金交叉后的走势）且价格在50日均线附近
    ma_proximity_threshold = strategy_params.get("ma_proximity_threshold", 0.05)
    if ma50 > ma200 and abs(current_price - ma50) / ma50 < ma_proximity_threshold:
        buy_signals.append("均线呈现黄金交叉形态，且价格在50日均线附近")
    
    # 买入建议
    recommendation = "不建议买入"
    if len(buy_signals) >= 2:
        recommendation = "可以考虑买入"
    elif len(buy_signals) == 1:
        recommendation = "观望"
    
    # 当前市场位置评估
    if price_position < 20:
        market_position = "接近历史低点，可能被低估"
    elif price_position < 40:
        market_position = "处于较低位置，可能具有一定价值"
    elif price_position < 60:
        market_position = "处于中间位置，价格适中"
    elif price_position < 80:
        market_position = "处于较高位置，可能面临回调风险"
    else:
        market_position = "接近历史高点，可能被高估"
    
    result = {
        "buy_signals": buy_signals,
        "signals_count": len(buy_signals),
        "recommendation": recommendation,
        "market_position": market_position,
        "price_position_percentage": round(price_position, 2)
    }
    
    logger.info(f"分析完成: {result['recommendation']}, 信号数量: {result['signals_count']}")
    return result

def create_price_chart(df, symbol_name, days=30):
    """
    创建过去30天的股价折线图，并返回Base64编码的图像
    """
    # 获取最近days天的数据
    recent_data = df.iloc[-days:]
    
    # 创建图形
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # 绘制收盘价折线图
    ax.plot(recent_data.index, recent_data['close'], 'b-', linewidth=2, label='Close Price')
    
    # 绘制50日均线
    if 'ma50' in recent_data.columns:
        ax.plot(recent_data.index, recent_data['ma50'], 'r--', linewidth=1.5, label='50-Day MA')
    
    # 绘制200日均线
    if 'ma200' in recent_data.columns:
        ax.plot(recent_data.index, recent_data['ma200'], 'g--', linewidth=1.5, label='200-Day MA')
    
    # 设置图表标题和标签
    ax.set_title(f'{symbol_name} Stock Price - Last {days} Days', fontsize=14)
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Price (USD)', fontsize=12)
    
    # 设置x轴日期格式
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))  # 每5天显示一个日期
    plt.xticks(rotation=45)
    
    # 添加网格线
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # 添加图例
    ax.legend(loc='best')
    
    # 添加最新收盘价标注
    latest_date = recent_data.index[-1]
    latest_price = recent_data['close'].iloc[-1]
    ax.annotate(f'${latest_price:.2f}', 
                xy=(latest_date, latest_price),
                xytext=(10, 0),
                textcoords='offset points',
                fontsize=12,
                fontweight='bold',
                color='blue')
    
    # 自动调整布局
    plt.tight_layout()
    
    # 将图表转换为Base64编码的图像
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=100)
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    
    # 关闭图表，释放内存
    plt.close(fig)
    
    # 转换为Base64字符串
    image_base64 = base64.b64encode(image_png).decode('utf-8')
    
    return image_base64

def send_email_report(stock_data, analysis_data, email_config, symbol_name):
    """发送分析报告到指定邮箱"""
    # 从环境变量或配置获取邮箱配置
    sender_email = email_config.get("from") or os.environ.get("EMAIL_FROM")
    sender_password = email_config.get("password") or os.environ.get("EMAIL_PASSWORD")
    receiver_email = email_config.get("to") or os.environ.get("EMAIL_TO")
    
    if not sender_email or not sender_password or not receiver_email:
        logger.error("邮箱配置缺失，无法发送邮件")
        return {"status": "error", "message": "邮箱配置缺失"}
    
    # 打印邮箱配置（不包含密码）
    logger.info(f"准备发送邮件从 {sender_email} 到 {receiver_email}")
    
    # 创建今天的日期字符串
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 创建邮件对象
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = f"{symbol_name}股票分析 - {today}"
    
    # 设置信号颜色和状态表情
    if analysis_data["recommendation"] == "可以考虑买入":
        signal_color = "green"
        emoji = "🟢"
    elif analysis_data["recommendation"] == "观望":
        signal_color = "orange"
        emoji = "🟠"
    else:
        signal_color = "red"
        emoji = "🔴"
    
    # 格式化买入信号显示
    buy_signals_html = ""
    if analysis_data["buy_signals"]:
        buy_signals_html = "<ul style='margin: 5px 0;'>"
        for signal in analysis_data["buy_signals"]:
            buy_signals_html += f"<li>{signal}</li>"
        buy_signals_html += "</ul>"
    else:
        buy_signals_html = "无买入信号"
    
    # 创建价格异常提示（如有）
    anomaly_note = ""
    if stock_data.get("price_anomaly", {}).get("detected", False):
        anomaly = stock_data["price_anomaly"]
        # 根据价格变动方向提供不同提示
        if anomaly["change_pct"] < 0:
            anomaly_note = f""" <span style="font-size:11px;color:#666;">(注意: 在{anomaly["date"]}检测到价格下跌{abs(anomaly["change_pct"])}%，可能是股票拆分)</span>"""
        else:
            anomaly_note = f""" <span style="font-size:11px;color:#666;">(注意: 在{anomaly["date"]}检测到价格上涨{anomaly["change_pct"]}%，可能是股票合并或其他重大事件)</span>"""
    
    # 创建过去30天的股价折线图
    price_chart_base64 = create_price_chart(stock_data["df"], symbol_name)
    
    # 创建HTML邮件内容
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; color: #333; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
            th {{ background-color: #f2f2f2; font-weight: bold; }}
            .recommendation {{ 
                font-weight: bold; 
                color: {signal_color}; 
                font-size: 18px; 
                padding: 15px;
                background-color: #f9f9f9;
                border-radius: 5px;
                display: inline-block;
                margin-top: 15px;
            }}
            h3 {{ 
                color: #333; 
                border-bottom: 1px solid #ddd; 
                padding-bottom: 8px;
                margin-top: 25px;
            }}
            .data-section {{ margin-bottom: 25px; }}
            ul {{ padding-left: 20px; }}
            li {{ margin-bottom: 5px; }}
            .chart-container {{
                margin: 20px 0;
                padding: 10px;
                background-color: #f9f9f9;
                border-radius: 5px;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="data-section">
            <h3>当前数据</h3>
            <table>
                <tr><th>指标</th><th>数值</th></tr>
                <tr><td>当前股价</td><td>${stock_data["current_price"]}</td></tr>
                <tr><td>52周最高价</td><td>${stock_data["high_52_week"]}{anomaly_note}</td></tr>
                <tr><td>52周最低价</td><td>${stock_data["low_52_week"]}</td></tr>
                <tr><td>200日均线</td><td>${stock_data["ma200"]}</td></tr>
                <tr><td>50日均线</td><td>${stock_data["ma50"]}</td></tr>
                <tr><td>RSI值 (14日)</td><td>{stock_data["rsi"]}</td></tr>
                <tr><td>市盈率(TTM)</td><td>{stock_data["pe_ratio"]}</td></tr>
            </table>
            
            <!-- 添加过去30天的股价图表 -->
            <div class="chart-container">
                <img src="data:image/png;base64,{price_chart_base64}" alt="{symbol_name}股票过去30天价格走势" style="max-width:100%;">
            </div>
        </div>
        
        <div class="data-section">
            <h3>买入策略分析</h3>
            <table>
                <tr><th>指标</th><th>数值</th></tr>
                <tr><td>买入信号</td><td>{buy_signals_html}</td></tr>
                <tr><td>信号数量</td><td>{analysis_data["signals_count"]}</td></tr>
                <tr><td>市场位置</td><td>{analysis_data["market_position"]}</td></tr>
                <tr><td>价格位置</td><td>{analysis_data["price_position_percentage"]}%</td></tr>
            </table>
            
            <div style="margin-top: 20px; text-align: center;">
                <p class="recommendation">{emoji} 买入建议: {analysis_data["recommendation"]}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # 添加HTML内容到邮件
    msg.attach(MIMEText(html, 'html'))
    
    try:
        # 连接到SMTP服务器
        if sender_email.endswith("gmail.com"):
            server = smtplib.SMTP('smtp.gmail.com', 587)
        elif sender_email.endswith("outlook.com") or sender_email.endswith("hotmail.com"):
            server = smtplib.SMTP('smtp.office365.com', 587)
        elif sender_email.endswith("yahoo.com"):
            server = smtplib.SMTP('smtp.mail.yahoo.com', 587)
        else:
            # 默认使用Gmail，你可以根据需要修改
            server = smtplib.SMTP('smtp.gmail.com', 587)
        
        server.starttls()  # 启用安全传输
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, receiver_email, text)
        server.quit()
        logger.info(f"邮件已成功发送到 {receiver_email}")
        return {"status": "success", "message": f"邮件已发送到 {receiver_email}"}
    except Exception as e:
        logger.error(f"发送邮件失败: {str(e)}")
        return {"status": "error", "message": f"发送邮件失败: {str(e)}"}

def send_error_email(symbol, error, email_config):
    """发送错误报告邮件"""
    sender_email = email_config.get("from") or os.environ.get("EMAIL_FROM")
    sender_password = email_config.get("password") or os.environ.get("EMAIL_PASSWORD")
    receiver_email = email_config.get("to") or os.environ.get("EMAIL_TO")
    
    if not sender_email or not sender_password or not receiver_email:
        logger.error("邮箱配置缺失，无法发送错误邮件")
        return {"status": "error", "message": "邮箱配置缺失"}
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = f"{symbol}股票分析 - 错误报告 - {datetime.now().strftime('%Y-%m-%d')}"
    
    error_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            .error {{ color: red; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h2>{symbol}股票分析 - 错误报告</h2>
        <p class="error">执行脚本时发生错误:</p>
        <p>{str(error)}</p>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(error_content, 'html'))
    
    try:
        if sender_email.endswith("gmail.com"):
            server = smtplib.SMTP('smtp.gmail.com', 587)
        elif sender_email.endswith("outlook.com"):
            server = smtplib.SMTP('smtp.office365.com', 587)
        else:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        logger.info("错误报告邮件已发送")
        return {"status": "success", "message": "错误报告邮件已发送"}
    except Exception as email_error:
        logger.error(f"发送错误报告邮件失败: {str(email_error)}")
        return {"status": "error", "message": f"发送错误报告邮件失败: {str(email_error)}"}

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='股票分析工具')
    parser.add_argument('--config', type=str, default='config.yaml', help='配置文件路径')
    parser.add_argument('--symbol', type=str, help='分析特定股票代码，例如：TSLA')
    parser.add_argument('--symbols', type=str, help='分析多只股票，逗号分隔，例如：TSLA,AAPL,NVDA')
    parser.add_argument('--no-email', action='store_true', help='不发送邮件，仅进行分析')
    parser.add_argument('--cache-expiry', type=int, default=4, help='缓存过期时间(小时)')
    args = parser.parse_args()
    
    # 加载配置
    config = load_config(args.config)
    
    # 确定要分析的股票列表
    symbols_to_analyze = []
    if args.symbol:
        symbols_to_analyze = [args.symbol]
    elif args.symbols:
        symbols_to_analyze = [s.strip() for s in args.symbols.split(',')]
    else:
        # 使用配置文件中的股票列表
        symbols_to_analyze = config.get('symbols', ["TSLA", "AAPL", "NVDA"])
    
    # 从环境变量或配置获取API密钥
    api_key = config.get('api_key') or os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        logger.error("缺少Alpha Vantage API密钥，请在配置文件设置或通过环境变量ALPHA_VANTAGE_API_KEY提供")
        return {"status": "error", "error": "缺少API密钥"}
    
    # 处理每只股票
    results = []
    for symbol in symbols_to_analyze:
        try:
            symbol_name = config.get('symbol_names', {}).get(symbol, symbol)
            logger.info(f"开始处理 {symbol} ({symbol_name})...")
            
            # 获取股票数据
            stock_data = get_stock_data_with_cache(
                symbol, 
                api_key, 
                cache_expiry_hours=args.cache_expiry
            )
            
            # 分析买入策略
            strategy_params = config.get('strategy', {})
            analysis_result = analyze_buy_strategy(stock_data, strategy_params)
            
            # 是否发送邮件
            email_result = None
            if not args.no_email:
                email_config = config.get('email', {})
                email_result = send_email_report(
                    stock_data, 
                    analysis_result, 
                    email_config, 
                    symbol_name
                )
            
            # 将结果添加到列表
            result = {
                "symbol": symbol,
                "symbol_name": symbol_name,
                "status": "success",
                "analysis": analysis_result
            }
            
            if email_result:
                result["email"] = email_result
                
            results.append(result)
            logger.info(f"{symbol} 处理完成")
            
        except Exception as e:
            logger.error(f"{symbol} 处理失败: {str(e)}", exc_info=True)
            # 发送错误报告邮件
            if not args.no_email:
                email_config = config.get('email', {})
                send_error_email(symbol, str(e), email_config)
            
            results.append({
                "symbol": symbol,
                "status": "error",
                "error": str(e)
            })
    
    # 汇总报告
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = len(results) - success_count
    
    logger.info(f"全部处理完成。成功: {success_count}, 失败: {error_count}")
    for r in results:
        if r["status"] == "success":
            symbol = r["symbol"]
            recommendation = r["analysis"]["recommendation"]
            signals = r["analysis"]["signals_count"]
            logger.info(f"  {symbol}: {recommendation} (信号数: {signals})")
        else:
            logger.info(f"  {r['symbol']}: 失败 - {r.get('error', '未知错误')}")
    
    return {
        "status": "success" if error_count == 0 else "partial_success" if success_count > 0 else "error",
        "success_count": success_count,
        "error_count": error_count,
        "results": results
    }

if __name__ == "__main__":
    try:
        result = main()
        exit_code = 0 if result["status"] in ["success", "partial_success"] else 1
        exit(exit_code)
    except Exception as e:
        logger.error(f"程序执行过程中发生未处理的异常: {str(e)}", exc_info=True)
        exit(1)
