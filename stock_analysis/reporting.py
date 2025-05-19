"""报告模块"""

import os
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from stock_analysis.visualization import create_price_chart

logger = logging.getLogger(__name__)

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
