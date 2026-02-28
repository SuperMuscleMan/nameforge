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
from src.scoring import QualityScorer, ScorePipeline

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
        "--score",
        action="store_true",
        help="评分模式：为已有昵称进行质量评分",
    )
    parser.add_argument(
        "--score-all",
        action="store_true",
        help="评分所有风格的昵称",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新评分（覆盖已有评分）",
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


def run_generation_mode(args, config_manager):
    """运行生成模式"""
    # 初始化生成模块
    prompt_manager = PromptManager(config_manager)
    glm_client = GLMClient(config_manager=config_manager)
    storage_manager = StorageManager(base_dir="data")

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

    # 运行生成流程
    style_name = target_styles[0]
    count = args.count if args.count else config_manager.get_generation_config("count")
    logger.info(f"开始为风格 '{style_name}' 生成昵称...")

    result = pipeline.generate_for_style(style_name, count=count)

    # 输出结果
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

    # 获取Token统计
    token_usage = glm_client.get_token_usage()
    logger.info(f"Token使用统计:")
    logger.info(f"  - 输入: {token_usage['input']}")
    logger.info(f"  - 输出: {token_usage['output']}")
    logger.info(f"  - 总计: {token_usage['total']}")

    logger.info("=" * 60)
    return 0


def run_scoring_mode(args, config_manager):
    """运行评分模式"""
    # 检查评分功能是否启用
    if not config_manager.get_system_config("scoring.enabled", True):
        logger.error("评分功能已在配置中禁用")
        return 1

    # 初始化评分模块
    scorer = QualityScorer(config_manager)
    storage_manager = StorageManager(base_dir="data")

    pipeline = ScorePipeline(
        config_manager=config_manager,
        quality_scorer=scorer,
        storage_manager=storage_manager,
    )

    logger.info("评分模块初始化完成")

    # 确定目标风格
    if args.score_all:
        # 评分所有风格
        logger.info("开始为所有风格评分...")
        result = pipeline.score_all_styles(force=args.force)

        # 输出汇总结果
        print("\n" + "=" * 60)
        print("全部风格评分完成")
        print("=" * 60)

        if "error" in result:
            print(f"错误: {result['error']}")
            return 1

        styles = result.get("styles", {})
        for style_name, style_result in styles.items():
            print(f"\n【{style_name}】")
            if "error" in style_result:
                print(f"  错误: {style_result['error']}")
            else:
                print(f"  总数量: {style_result.get('total', 0)}")
                print(f"  新评分: {style_result.get('scored', 0)}")
                print(f"  跳过: {style_result.get('skipped', 0)}")
                print(f"  高分(≥8): {style_result.get('high_score_count', 0)}")

        print(f"\n总计新评分: {result.get('total_scored', 0)}")
        print(f"总计高分: {result.get('total_high_score', 0)}")

    else:
        # 评分指定风格
        if args.style:
            style_name = args.style
        else:
            style_name = config_manager.get_generation_config("style")

        logger.info(f"开始为风格 '{style_name}' 评分...")
        result = pipeline.score_style(style_name, force=args.force)

        # 输出结果
        print("\n" + "=" * 60)
        print(f"【{style_name}】评分完成")
        print("=" * 60)

        if "error" in result:
            print(f"错误: {result['error']}")
            return 1

        print(f"总数量: {result.get('total', 0)}")
        print(f"新评分: {result.get('scored', 0)}")
        print(f"跳过(已评分): {result.get('skipped', 0)}")
        print(f"高分(≥8): {result.get('high_score_count', 0)}")

        if result.get("interrupted"):
            print("\n注意: 评分被用户中断，已保存已评分结果")
        elif result.get("failed"):
            print("\n警告: 评分过程中断，部分结果已保存")

    # 输出Token统计
    token_usage = pipeline.get_token_usage()
    request_count = pipeline.get_request_count()
    print(f"\nAPI调用统计:")
    print(f"  - 请求次数: {request_count}")
    print(f"  - 输入Token: {token_usage['input']}")
    print(f"  - 输出Token: {token_usage['output']}")
    print(f"  - 总计Token: {token_usage['total']}")

    # 输出文件位置
    if args.style or args.score_all:
        print(f"\n输出文件:")
        styles_to_show = config_manager.list_styles() if args.score_all else [args.style or config_manager.get_generation_config("style")]
        for style in styles_to_show:
            print(f"  - 全部评分: data/{style}_scores.txt")
            print(f"  - 高分昵称: data/{style}_high_scores.txt")
            print(f"  - 统计信息: data/{style}_score_stats.txt")

    print("\n" + "=" * 60)
    return 0


def main():
    """主程序入口"""
    # 解析命令行参数
    args = parse_args()

    logger.info("=" * 60)
    if args.score or args.score_all:
        logger.info("游戏昵称评分系统 - 启动")
    else:
        logger.info("游戏昵称生成系统 - Phase 1 启动")
    logger.info("=" * 60)
    logger.debug("正在加载配置...")

    try:
        # 初始化配置
        config_manager = ConfigManager(config_dir="config")

        # 根据模式运行
        if args.score or args.score_all:
            return run_scoring_mode(args, config_manager)
        else:
            return run_generation_mode(args, config_manager)

    except KeyboardInterrupt:
        logger.info("用户中断操作")
        print("\n操作已中断")
        return 130

    except Exception as e:
        logger.error(f"发生异常: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
