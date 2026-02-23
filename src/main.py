"""
主应用入口
游戏昵称生成系统 Phase 1
"""

import sys
import logging
import argparse
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logging_config import setup_logging
from src.config.config_manager import ConfigManager
from src.prompts.prompt_manager import PromptManager
from src.api.glm_client import GLMClient
from src.storage.storage_manager import StorageManager
from src.pipeline.generation_pipeline import GenerationPipeline

# 初始化日志
logger = setup_logging("logs/app.log", level="DEBUG")
logger = logging.getLogger("rand_names")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="游戏昵称生成系统")
    parser.add_argument(
        "--regenerate-roots",
        action="store_true",
        help="重新生成词根",
    )
    parser.add_argument(
        "--style",
        type=str,
        help="指定风格（覆盖配置文件中的设置）",
    )
    parser.add_argument(
        "--count",
        type=int,
        help="指定生成数量（覆盖配置文件中的设置）",
    )
    return parser.parse_args()


def main():
    """主程序入口"""
    # 解析命令行参数
    args = parse_args()

    logger.info("=" * 60)
    logger.info("游戏昵称生成系统 - Phase 1 启动")
    logger.info("=" * 60)
    logger.debug("正在加载配置...")

    try:
        # 1. 初始化所有模块
        logger.info("正在初始化系统模块...")

        config_manager = ConfigManager(config_dir="config")
        prompt_manager = PromptManager(config_manager)
        glm_client = GLMClient(config_manager=config_manager)
        storage_manager = StorageManager(base_dir="data")

        # 2. 创建生成管道
        pipeline = GenerationPipeline(
            glm_client=glm_client,
            config_manager=config_manager,
            prompt_manager=prompt_manager,
            storage=storage_manager,
        )

        logger.info("所有模块初始化完成")

        # 确定目标风格
        if args.style:
            target_styles = [args.style]
        else:
            target_styles = [config_manager.get_generation_config("style")]

        # 处理重新生成词根命令
        if args.regenerate_roots:
            for style in target_styles:
                pipeline.regenerate_roots(style)
            print("词根重新生成完成")
            return 0

        # 3. 运行生成流程
        style_name = target_styles[0]
        count = args.count if args.count else config_manager.get_generation_config("count")
        logger.info(f"开始为风格 '{style_name}' 生成昵称...")

        result = pipeline.generate_for_style(style_name, count=count)

        # 4. 输出结果
        if result.get("stats", {}).get("error"):
            logger.error(f"生成失败: {result['stats']['error']}")
            return 1

        stats = result["stats"]
        logger.info("")
        logger.info("=" * 60)
        logger.info("生成完成")
        logger.info("=" * 60)
        logger.info(f"风格: {style_name}")
        logger.info(f"生成数量: {stats.get('generated', 0)}")
        logger.info(f"有效数量: {stats.get('valid', 0)}")
        logger.info(f"无效数量: {stats.get('invalid_format', 0)}")
        logger.info(f"有效昵称示例: {result['valid_names'][:5]}")
        logger.info(f"数据存储位置: data/{style_name}_names.txt")

        # 5. 获取Token统计
        token_usage = glm_client.get_token_usage()
        logger.info(f"Token使用统计:")
        logger.info(f"  - 输入: {token_usage['input']}")
        logger.info(f"  - 输出: {token_usage['output']}")
        logger.info(f"  - 总计: {token_usage['total']}")

        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error(f"发生异常: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
