"""
词根管理模块
负责词根的生成、存储和加载
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from src.api.glm_client import GLMClient
from src.config.config_manager import ConfigManager

logger = logging.getLogger("rand_names")


class WordRootManager:
    """
    管理词根的生成、存储和加载
    """

    def __init__(self, glm_client: GLMClient, config_manager: ConfigManager, data_dir: str = "data"):
        """
        初始化词根管理器

        Args:
            glm_client: GLM API客户端
            config_manager: 配置管理器
            data_dir: 词根文件存储目录
        """
        self.glm_client = glm_client
        self.config_manager = config_manager
        self.data_dir = Path(data_dir)
        self.roots_cache = {}  # 内存缓存

        # 确保数据目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)

        logger.info("WordRootManager 已初始化")

    def get_roots(self, style_name: str) -> Dict[str, List[str]]:
        """
        获取指定风格的词根

        流程:
        1. 检查内存缓存
        2. 检查文件是否存在
        3. 如不存在，调用AI生成
        4. 返回词根字典 {类别: [词根列表]}

        Args:
            style_name: 风格名称

        Returns:
            词根字典 {类别名: [词根列表]}
        """
        # 1. 检查内存缓存
        if style_name in self.roots_cache:
            logger.debug(f"[{style_name}] 从内存缓存获取词根")
            return self.roots_cache[style_name]

        # 2. 检查文件是否存在
        roots = self._load_roots_from_file(style_name)
        if roots is not None: # todo 需要判断词根数量是否满足要求，不满足则需要补充，思考下实现方案
            logger.info(f"[{style_name}] 从文件加载词根成功")
            self.roots_cache[style_name] = roots
            return roots

        # 3. 如不存在，调用AI生成
        logger.info(f"[{style_name}] 词根文件不存在，开始生成词根...")
        roots = self._generate_roots(style_name)

        # 4. 保存到文件
        self._save_roots_to_file(style_name, roots)

        # 5. 更新缓存
        self.roots_cache[style_name] = roots

        return roots

    def _load_roots_from_file(self, style_name: str) -> Optional[Dict[str, List[str]]]:
        """
        从YAML文件加载词根

        Args:
            style_name: 风格名称

        Returns:
            词根字典，如文件不存在则返回None
        """
        file_path = self.data_dir / f"{style_name}_roots.yaml"

        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            categories = data.get("categories", {})
            logger.debug(f"[{style_name}] 从文件加载了 {len(categories)} 个词根类别")
            return categories

        except Exception as e:
            logger.error(f"[{style_name}] 加载词根文件失败: {e}")
            return None

    def _generate_roots(self, style_name: str) -> Dict[str, List[str]]:
        """
        调用AI一次性生成所有类别的词根

        单次API调用获取所有类别词根，返回格式为JSON对象

        Args:
            style_name: 风格名称

        Returns:
            词根字典 {类别名: [词根列表]}
        """
        # 获取词根配置
        word_roots_config = self.config_manager.get_word_roots_config()
        categories_config = word_roots_config.get("categories", {}).get(style_name, [])
        count_per_category = word_roots_config.get("count_per_category", 100)

        if not categories_config:
            logger.warning(f"[{style_name}] 未找到词根类别配置，使用默认配置")
            categories_config = [{"name": "默认", "description": "通用词根", "examples": ["词", "根"]}]

        # 构建一次性生成所有类别的Prompt
        prompt = self._build_batch_generation_prompt(style_name, categories_config, count_per_category)

        logger.info(f"[{style_name}] 开始一次性生成所有类别的词根...")

        # 调用API生成
        response = self.glm_client.generate(prompt)

        roots = {}

        if response.get("error"):
            logger.error(f"[{style_name}] 生成词根失败: {response['error']}")
            # 使用示例作为回退
            for category in categories_config:
                category_name = category["name"]
                roots[category_name] = category.get("examples", [])[:count_per_category]
            return roots

        # 解析JSON响应
        try:
            content = response.get("content", "")
            # 清理可能的markdown代码块
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            parsed_roots = json.loads(content)

            if not isinstance(parsed_roots, dict):
                logger.warning(f"[{style_name}] 返回格式错误，期望JSON对象，使用示例")
                for category in categories_config:
                    category_name = category["name"]
                    roots[category_name] = category.get("examples", [])[:count_per_category]
                return roots

            # 处理每个类别的词根
            for category in categories_config:
                category_name = category["name"]
                category_roots = parsed_roots.get(category_name, [])

                if not isinstance(category_roots, list):
                    logger.warning(f"[{style_name}] 类别 '{category_name}' 返回格式错误，使用示例")
                    category_roots = category.get("examples", [])

                # 确保词根数量
                if len(category_roots) < count_per_category:
                    # 补充示例词根
                    examples = category.get("examples", [])
                    while len(category_roots) < count_per_category and examples:
                        category_roots.append(examples[len(category_roots) % len(examples)])

                roots[category_name] = category_roots
                logger.info(f"[{style_name}] 类别 '{category_name}' 生成了 {len(category_roots)} 个词根")

        except json.JSONDecodeError as e:
            logger.error(f"[{style_name}] 解析词根失败: {e}")
            logger.debug(f"原始响应: {response.get('content', '')[:200]}")
            # 使用示例作为回退
            for category in categories_config:
                category_name = category["name"]
                roots[category_name] = category.get("examples", [])[:count_per_category]

        return roots

    def _save_roots_to_file(self, style_name: str, roots: Dict[str, List[str]]) -> None:
        """
        保存词根到YAML文件

        Args:
            style_name: 风格名称
            roots: 词根字典
        """
        file_path = self.data_dir / f"{style_name}_roots.yaml"

        # 计算总词根数
        total_count = sum(len(roots_list) for roots_list in roots.values())

        data = {
            "metadata": {
                "style": style_name,
                "generated_at": datetime.now().isoformat(),
                "total_count": total_count,
            },
            "categories": roots,
        }

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True, sort_keys=False)
            logger.info(f"[{style_name}] 词根已保存到文件: {file_path}")
        except Exception as e:
            logger.error(f"[{style_name}] 保存词根文件失败: {e}")
            raise

    def _build_generation_prompt(
        self, style_name: str, category: Dict, count: int
    ) -> str:
        """
        构建词根生成Prompt（单个类别，保留用于兼容性）

        Args:
            style_name: 风格名称
            category: 类别配置
            count: 需要生成的词根数量

        Returns:
            Prompt文本
        """
        category_name = category["name"]
        description = category["description"]
        examples = category.get("examples", [])
        examples_str = ", ".join(examples) if examples else "无"

        prompt = f"""请为{style_name}风格生成{count}个高质量的'{category_name}'类别词根。

要求：
1. 必须符合{style_name}风格特征，体现{description}
2. 避免生僻字，常用字优先
3. 适合与其他词根组合成昵称
4. 词根长度1-3字为宜
5. 高质量、有美感、无攻击性、无敏感词、无明显重复
6. 参考示例：{examples_str}

返回JSON数组格式，仅返回词根列表，无其他文字。
例如：["词根1", "词根2", "词根3", ...]
"""
        return prompt

    def _build_batch_generation_prompt(
        self, style_name: str, categories: List[Dict], count: int
    ) -> str:
        """
        构建批量词根生成Prompt（一次性生成所有类别）

        Args:
            style_name: 风格名称
            categories: 类别配置列表
            count: 每个类别需要生成的词根数量

        Returns:
            Prompt文本
        """
        # 构建类别描述
        categories_desc = []
        for category in categories:
            category_name = category["name"]
            description = category["description"]
            examples = category.get("examples", [])
            examples_str = ", ".join(examples[:5]) if examples else "无"
            categories_desc.append(
                f"- {category_name}: {description}（{count}个），参考示例：{examples_str}"
            )

        categories_desc_str = "\n".join(categories_desc)

        # 构建返回格式示例
        example_output = {}
        for category in categories:
            category_name = category["name"]
            examples = category.get("examples", [])
            example_output[category_name] = examples[:3] if examples else ["示例1", "示例2", "示例3"]

        example_json = json.dumps(example_output, ensure_ascii=False, indent=2)

        prompt = f"""请为{style_name}风格生成词根，包含以下类别：

{categories_desc_str}

要求：
1. 每个类别生成{count}个高质量词根
2. 必须符合{style_name}风格特征
3. 避免生僻字，常用字优先
4. 适合与其他词根组合成昵称
5. 词根长度1-4字为宜，鼓励使用双字词组增加多样性
6. 高质量、有美感、无攻击性、无敏感词
7. 避免不同类别之间出现重复词根
8. 同一类别内词根不重复
9. 词根之间要有明显差异，避免意思过于相近
10. 双字词根优先选择有画面感、有情感的词汇

返回JSON格式（仅返回JSON对象，无其他文字）：
{example_json}
"""
        return prompt

    def clear_cache(self, style_name: Optional[str] = None) -> None:
        """
        清除词根缓存

        Args:
            style_name: 风格名称，如为None则清除所有缓存
        """
        if style_name:
            if style_name in self.roots_cache:
                del self.roots_cache[style_name]
                logger.info(f"[{style_name}] 词根缓存已清除")
        else:
            self.roots_cache.clear()
            logger.info("所有词根缓存已清除")

    def regenerate_roots(self, style_name: str) -> Dict[str, List[str]]:
        """
        重新生成指定风格的词根

        Args:
            style_name: 风格名称

        Returns:
            新生成的词根字典
        """
        # 清除缓存
        self.clear_cache(style_name)

        # 删除旧文件
        file_path = self.data_dir / f"{style_name}_roots.yaml"
        if file_path.exists():
            file_path.unlink()
            logger.info(f"[{style_name}] 旧词根文件已删除")

        # 重新生成
        return self.get_roots(style_name)
