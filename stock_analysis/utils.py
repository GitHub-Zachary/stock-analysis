"""工具函数模块"""

import os
import logging
import yaml
from datetime import datetime

# 设置日志
def setup_logging():
    """设置日志系统"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f"stock_tracker_{datetime.now().strftime('%Y%m%d')}.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("stock_analysis")

def load_config(config_file="config.yaml"):
    """加载配置文件"""
    logger = logging.getLogger(__name__)
    
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
