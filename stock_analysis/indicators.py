"""技术指标计算模块"""

import pandas as pd
import numpy as np

def calculate_moving_averages(df, windows=[50, 200]):
    """计算移动平均线"""
    result = df.copy()
    for window in windows:
        result[f'ma{window}'] = result['close'].rolling(window=window).mean()
    return result

def calculate_rsi(df, window=14):
    """计算相对强弱指数(RSI)"""
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()
    
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df

def calculate_macd(df, fast=12, slow=26, signal=9):
    """计算MACD指标"""
    exp_fast = df['close'].ewm(span=fast, adjust=False).mean()
    exp_slow = df['close'].ewm(span=slow, adjust=False).mean()
    df['macd'] = exp_fast - exp_slow
    df['signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['signal']
    return df

def calculate_bollinger_bands(df, window=20, num_std=2):
    """计算布林带"""
    df['ma20'] = df['close'].rolling(window=window).mean()
    std20 = df['close'].rolling(window=window).std()
    df['upper_band'] = df['ma20'] + (std20 * num_std)
    df['lower_band'] = df['ma20'] - (std20 * num_std)
    return df

def calculate_all_indicators(df):
    """计算所有技术指标"""
    df = calculate_moving_averages(df)
    df = calculate_rsi(df)
    df = calculate_macd(df)
    df = calculate_bollinger_bands(df)
    return df

def process_stock_data(stock_data):
    """处理股票数据，添加技术指标"""
    df = stock_data["df"].copy()
    df = calculate_all_indicators(df)
    
    # 获取最新数据点的指标值
    latest_date = df.index[-1]
    ma50 = df.loc[latest_date, 'ma50']
    ma200 = df.loc[latest_date, 'ma200']
    rsi = df.loc[latest_date, 'rsi']
    
    # 更新股票数据
    result = stock_data.copy()
    result["df"] = df
    result["ma50"] = round(ma50, 2)
    result["ma200"] = round(ma200, 2)
    result["rsi"] = round(rsi, 2)
    
    return result
