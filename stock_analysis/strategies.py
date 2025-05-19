"""买入策略分析模块"""

import logging

logger = logging.getLogger(__name__)

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
