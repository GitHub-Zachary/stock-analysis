"""数据获取和处理模块"""

import os
import pickle
import time
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

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
    """检测历史数据中异常价格变动"""
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
    """使用Alpha Vantage API获取股票的相关数据"""
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
    
    # 获取当前数据
    latest_date = df.index[-1]
    current_price = df.loc[latest_date, 'close']
    
    # 计算52周最高价和最低价
    one_year_ago = latest_date - timedelta(days=365)
    df_52_weeks = df[df.index >= one_year_ago]
    high_52_week = df_52_weeks['high'].max()
    low_52_week = df_52_weeks['low'].min()
    
    # 获取市盈率
    pe_ratio = float(data_overview.get("PERatio", 0))
    
    # 检测52周内是否有价格异常变动
    price_anomaly = detect_price_anomalies(df_52_weeks)
    
    # 返回原始DataFrame，后续会在indicators模块中添加技术指标
    return {
        "date": latest_date.strftime("%Y-%m-%d"),
        "current_price": round(current_price, 2),
        "high_52_week": round(high_52_week, 2),
        "low_52_week": round(low_52_week, 2),
        "pe_ratio": round(pe_ratio, 2),
        "price_anomaly": price_anomaly,
        "df": df
    }
