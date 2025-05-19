#!/usr/bin/env python
"""股票分析系统主运行脚本"""

import os
import argparse
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from stock_analysis.utils import setup_logging, load_config
from stock_analysis.data import get_stock_data_with_cache
from stock_analysis.indicators import process_stock_data
from stock_analysis.strategies import analyze_buy_strategy
from stock_analysis.reporting import send_email_report, send_error_email

def main():
    """主程序入口"""
    # 设置日志
    logger = setup_logging()
    
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
            
            # 处理股票数据，计算技术指标
            stock_data = process_stock_data(stock_data)
            
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
        logging.getLogger(__name__).error(f"程序执行过程中发生未处理的异常: {str(e)}", exc_info=True)
        exit(1)
