import requests
import pandas as pd
import numpy as np
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta

def get_tesla_data():
    """
    使用Alpha Vantage API获取特斯拉股票的相关数据
    """
    # 从环境变量获取API密钥
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    symbol = "TSLA"  # 特斯拉股票代码
    
    # 获取股票日线数据
    url_daily = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&outputsize=full&apikey={api_key}"
    response_daily = requests.get(url_daily)
    data_daily = response_daily.json()
    
    # 打印API响应的键，用于调试
    print(f"API Response Keys: {data_daily.keys()}")
    
    # 等待一下，避免API请求过快
    import time
    time.sleep(1)
    
    # 获取公司概览数据（包含市盈率）
    url_overview = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={symbol}&apikey={api_key}"
    response_overview = requests.get(url_overview)
    data_overview = response_overview.json()
    
    # 打印概览数据的键，用于调试
    print(f"Overview Response Keys: {data_overview.keys()}")
    
    # 将日线数据转换为DataFrame
    time_series = data_daily.get("Time Series (Daily)", {})
    if not time_series:
        print("Error: No time series data returned from API")
        print(f"Full API response: {data_daily}")
        raise ValueError("Failed to get time series data from Alpha Vantage")
        
    df = pd.DataFrame(time_series).T
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    
    # 将字符串转换为浮点数
    for col in df.columns:
        df[col] = pd.to_numeric(df[col])
    
    # 重命名列
    df.columns = ['open', 'high', 'low', 'close', 'volume']
    
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
    
    # 构建结果数据字典
    result = {
        "date": latest_date.strftime("%Y-%m-%d"),
        "current_price": round(current_price, 2),
        "high_52_week": round(high_52_week, 2),
        "low_52_week": round(low_52_week, 2),
        "ma50": round(ma50, 2),
        "ma200": round(ma200, 2),
        "rsi": round(rsi, 2),
        "pe_ratio": round(pe_ratio, 2)
    }
    
    return result

def analyze_buy_strategy(data):
    """
    根据特斯拉股票的数据分析是否适合买入
    返回买入策略分析结果
    """
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
    
    # 策略1: RSI < 30 表示超卖，可能是买入机会
    if rsi < 30:
        buy_signals.append("RSI低于30，处于超卖区域")
    
    # 策略2: 价格低于50日均线但高于200日均线，可能是技术回调
    if current_price < ma50 and current_price > ma200:
        buy_signals.append("价格低于50日均线但高于200日均线，可能是技术回调")
    
    # 策略3: 价格在52周范围的下1/3位置
    if price_position < 33:
        buy_signals.append(f"价格在52周范围的下1/3位置 ({price_position:.2f}%)")
    
    # 策略4: 50日均线在200日均线之上（黄金交叉后的走势）且价格在50日均线附近
    if ma50 > ma200 and abs(current_price - ma50) / ma50 < 0.05:
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
    
    return result

def send_email_report(stock_data, analysis_data):
    """发送分析报告到指定邮箱"""
    # 从环境变量获取邮箱配置
    sender_email = os.environ.get("EMAIL_FROM")
    sender_password = os.environ.get("EMAIL_PASSWORD")
    receiver_email = os.environ.get("EMAIL_TO")
    
    # 打印邮箱配置（不包含密码）
    print(f"Sending email from {sender_email} to {receiver_email}")
    
    # 创建今天的日期字符串
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 创建邮件对象
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = f"特斯拉股票分析 - {today}"
    
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
    
    # 创建HTML邮件内容
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .recommendation {{ font-weight: bold; color: {signal_color}; }}
        </style>
    </head>
    <body>
        <h2>特斯拉股票分析 - {today}</h2>
        
        <h3>当前数据</h3>
        <table>
            <tr><th>指标</th><th>数值</th></tr>
            <tr><td>当前股价</td><td>${stock_data["current_price"]}</td></tr>
            <tr><td>52周最高价</td><td>${stock_data["high_52_week"]}</td></tr>
            <tr><td>52周最低价</td><td>${stock_data["low_52_week"]}</td></tr>
            <tr><td>200日均线</td><td>${stock_data["ma200"]}</td></tr>
            <tr><td>50日均线</td><td>${stock_data["ma50"]}</td></tr>
            <tr><td>RSI值</td><td>{stock_data["rsi"]}</td></tr>
            <tr><td>市盈率(P/E)</td><td>{stock_data["pe_ratio"]}</td></tr>
        </table>
        
        <h3>买入策略分析</h3>
        <table>
            <tr><th>指标</th><th>数值</th></tr>
            <tr><td>买入信号</td><td>{", ".join(analysis_data["buy_signals"]) if analysis_data["buy_signals"] else "无买入信号"}</td></tr>
            <tr><td>信号数量</td><td>{analysis_data["signals_count"]}</td></tr>
            <tr><td>市场位置</td><td>{analysis_data["market_position"]}</td></tr>
            <tr><td>价格位置</td><td>{analysis_data["price_position_percentage"]}%</td></tr>
        </table>
        
        <p class="recommendation">{emoji} 买入建议: {analysis_data["recommendation"]}</p>
        
        <p><small>此邮件由自动系统生成，请勿回复。</small></p>
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
        print(f"邮件已成功发送到 {receiver_email}")
        return {"status": "success", "message": f"邮件已发送到 {receiver_email}"}
    except Exception as e:
        print(f"发送邮件失败: {str(e)}")
        return {"status": "error", "message": f"发送邮件失败: {str(e)}"}

def main():
    try:
        # 1. 获取特斯拉股票数据
        print("开始获取特斯拉股票数据...")
        tesla_data = get_tesla_data()
        print(f"获取数据成功: {tesla_data}")
        
        # 2. 分析买入策略
        print("开始分析买入策略...")
        analysis_result = analyze_buy_strategy(tesla_data)
        print(f"分析完成: {analysis_result}")
        
        # 3. 发送电子邮件报告
        print("开始发送电子邮件报告...")
        email_result = send_email_report(tesla_data, analysis_result)
        print(email_result["message"])
        
        return {
            "status": "success",
            "stock_data": tesla_data,
            "analysis_result": analysis_result,
            "email_result": email_result
        }
    except Exception as e:
        print(f"执行过程中发生错误: {str(e)}")
        # 如果发生错误，尝试发送错误报告邮件
        try:
            sender_email = os.environ.get("EMAIL_FROM")
            sender_password = os.environ.get("EMAIL_PASSWORD")
            receiver_email = os.environ.get("EMAIL_TO")
            
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = receiver_email
            msg['Subject'] = f"特斯拉股票分析 - 错误报告 - {datetime.now().strftime('%Y-%m-%d')}"
            
            error_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    .error {{ color: red; font-weight: bold; }}
                </style>
            </head>
            <body>
                <h2>特斯拉股票分析 - 错误报告</h2>
                <p class="error">执行脚本时发生错误:</p>
                <p>{str(e)}</p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(error_content, 'html'))
            
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
            print("错误报告邮件已发送")
        except Exception as email_error:
            print(f"发送错误报告邮件失败: {str(email_error)}")
        
        return {
            "status": "error",
            "error": str(e)
        }

if __name__ == "__main__":
    result = main()
    print(f"执行结果: {result['status']}")
