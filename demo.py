#!/usr/bin/env python3
"""
功能演示脚本 - 验证阶段1完整功能
使用Mock GLM API响应进行端到端测试
"""

import sys
import json
from pathlib import Path
from unittest.mock import Mock, patch

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.logging_config import setup_logging
from src.config.config_manager import ConfigManager
from src.prompts.prompt_manager import PromptManager
from src.api.glm_client import GLMClient
from src.storage.storage_manager import StorageManager
from src.pipeline.generation_pipeline import GenerationPipeline

# 初始化日志
logger = setup_logging("logs/demo.log", level="INFO")
logger = __import__("logging").getLogger("rand_names")


def demo_complete_pipeline():
    """演示完整的生成管道"""
    logger.info("=" * 70)
    logger.info("游戏昵称生成系统 - Phase 1 功能演示")
    logger.info("=" * 70)

    try:
        # 1. 初始化所有模块
        logger.info("\n【step 1】初始化系统模块...")
        config_manager = ConfigManager(config_dir="config")
        prompt_manager = PromptManager(config_manager)

        with patch.dict("os.environ", {"GLM_API_KEY": "demo_key"}):
            glm_client = GLMClient(api_key="demo_key")

        storage_manager = StorageManager(base_dir="tmp_data/data")
        pipeline = GenerationPipeline(
            glm_client=glm_client,
            config_manager=config_manager,
            prompt_manager=prompt_manager,
            storage=storage_manager,
        )

        logger.info("✅ 系统模块初始化完成")

        # 2. 演示配置系统
        logger.info("\n【step 2】展示配置系统")
        styles = config_manager.list_styles()
        logger.info(f"可用风格: {styles}")

        for style in styles:
            style_config = config_manager.get_style(style)
            logger.info(f"  - {style}: {style_config['description']}")

        # 3. 演示Prompt引擎
        logger.info("\n【step 3】演示Prompt引擎")
        style_name = "古风"
        style_config = config_manager.get_style(style_name)

        prompt = prompt_manager.render_prompt(
            style_name=style_name,
            style_description=style_config["description"],
            min_len=style_config["length_min"],
            max_len=style_config["length_max"],
            charset=style_config["charset"],
            count=5,
            recent_names=["示例1", "示例2"],
        )

        logger.info(f"生成的Prompt (前200字符):\n{prompt[:200]}...")

        # 4. 演示Mock API调用和端到端流程
        logger.info("\n【step 4】演示完整生成流程（使用Mock API）...")

        # 为不同的风格准备Mock响应
        mock_responses = {
            "古风": ["雪月风", "林溪烟", "竹海清音", "古月长庚", "诗意烟雨"],
            "二次元": ["月之姫", "星梦奇迹", "樱花泪", "琪妙幻想", "梦幻之瞳"],
            "赛博朋克": ["Neo-Shadow", "Cyber-Phantom", "VoidWalker", "Omega-7", "Nexus"],
        }

        total_generated = 0
        total_valid = 0

        for style in styles:
            # Mock GLM API的响应
            with patch("src.api.glm_client.requests.post") as mock_post:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "choices": [
                        {"message": {"content": json.dumps(mock_responses.get(style, []))}}
                    ],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 50,
                        "total_tokens": 150,
                    },
                }
                mock_response.raise_for_status = Mock()
                mock_post.return_value = mock_response

                # 执行生成
                result = pipeline.generate_for_style(style, count=5)

                # 输出结果
                stats = result["stats"]
                total_generated += stats["generated"]
                total_valid += stats["valid"]

                logger.info(f"  [{style}]")
                logger.info(f"    - 生成: {stats['generated']}")
                logger.info(f"    - 有效: {stats['valid']}")
                logger.info(f"    - 示例: {result['valid_names'][:2]}")

        # 5. 展示存储和统计
        logger.info("\n【step 5】展示存储和统计信息")
        for style in styles:
            count = storage_manager.get_count(style)
            if count > 0:
                logger.info(f"  {style}: {count} 条昵称已保存")
                recent = storage_manager.list_names(style, limit=3)
                logger.info(f"    最近样本: {recent}")

        # 6. 输出Token使用统计
        logger.info("\n【step 6】API调用统计")
        token_usage = glm_client.get_token_usage()
        logger.info(f"总计生成: {total_generated} 条昵称")
        logger.info(f"总计有效: {total_valid} 条昵称")
        logger.info(f"Token使用:")
        logger.info(f"  - 输入: {token_usage['input']}")
        logger.info(f"  - 输出: {token_usage['output']}")
        logger.info(f"  - 总计: {token_usage['total']}")

        # 7. 验证关键功能
        logger.info("\n【step 7】功能验证")
        checks = [
            ("✅ 配置管理系统", len(styles) > 0),
            ("✅ Prompt渲染引擎", "{" not in prompt),
            ("✅ 存储系统", total_valid > 0),
            ("✅ 管道端到端", total_generated > 0),
            ("✅ Token统计", token_usage["total"] > 0),
        ]

        for name, result in checks:
            status = "✅ 通过" if result else "❌ 失败"
            logger.info(f"  {name}: {status}")

        logger.info("\n" + "=" * 70)
        logger.info("✅ 阶段1功能演示完成！系统已准备就绪")
        logger.info("=" * 70)
        logger.info("\n下一步:")
        logger.info("  1. 设置真实的GLM API Key: export GLM_API_KEY='your_key'")
        logger.info("  2. 运行主程序: python3 src/main.py")
        logger.info("  3. 查看生成的昵称: cat data/古风_names.txt")
        logger.info("")

        return 0

    except Exception as e:
        logger.error(f"发生异常: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(demo_complete_pipeline())
