"""可视化模块"""

import io
import base64
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

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
