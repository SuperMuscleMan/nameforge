"""
日志配置系统
"""

import logging
import logging.handlers
from pathlib import Path


def setup_logging(log_file: str = "logs/app.log", level: str = "DEBUG") -> logging.Logger:
    """
    配置日志系统

    Args:
        log_file: 日志文件路径
        level: 日志级别

    Returns:
        Logger实例
    """
    # 创建日志目录
    log_dir = Path(log_file).parent
    log_dir.mkdir(exist_ok=True, parents=True)

    logger = logging.getLogger("rand_names")
    logger.setLevel(getattr(logging, level))

    # 移除已有的处理器，避免重复
    logger.handlers = []

    # 文件处理器（日志轮转）
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    file_handler.setLevel(getattr(logging, level))

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, level))

    # 格式化器
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
