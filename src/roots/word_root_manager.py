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

    def get_roots(self, style_name: str) -> Dict[str, List[Dict]]:
        """
        获取指定风格的词根

        流程:
        1. 检查内存缓存
        2. 检查文件是否存在
        3. 如不存在，调用AI生成
        4. 返回词根字典 {类别: [{"word": "词根", "tags": ["标签"]}, ...]}

        Args:
            style_name: 风格名称

        Returns:
            词根字典，格式为 {类别名: [{"word": "词根", "tags": ["标签1"]}, ...]}
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

    def _load_roots_from_file(self, style_name: str) -> Optional[Dict[str, List[Dict]]]:
        """
        从YAML文件加载词根

        支持新格式（带标签的字典）和旧格式（纯字符串）

        Args:
            style_name: 风格名称

        Returns:
            词根字典，格式为 {类别名: [{"word": "词根", "tags": ["标签1"]}, ...]}
            如文件不存在则返回None
        """
        file_path = self.data_dir / f"{style_name}_roots.yaml"

        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            categories = data.get("categories", {})

            # 处理词根格式：统一转换为字典格式
            processed_categories = {}
            for category_name, roots_list in categories.items():
                processed_roots = []
                for root_item in roots_list:
                    if isinstance(root_item, str):
                        # 旧格式：纯字符串
                        processed_roots.append({"word": root_item, "tags": []})
                    elif isinstance(root_item, dict) and "word" in root_item:
                        # 新格式：字典格式
                        if "tags" not in root_item:
                            root_item["tags"] = []
                        processed_roots.append(root_item)
                    else:
                        logger.warning(f"[{style_name}] 词根格式错误，跳过: {root_item}")

                processed_categories[category_name] = processed_roots

            logger.debug(f"[{style_name}] 从文件加载了 {len(processed_categories)} 个词根类别")
            return processed_categories

        except Exception as e:
            logger.error(f"[{style_name}] 加载词根文件失败: {e}")
            return None

    def _generate_roots(self, style_name: str) -> Dict[str, List[Dict]]:
        """
        调用AI一次性生成所有类别的词根

        单次API调用获取所有类别词根，返回格式为JSON对象

        Args:
            style_name: 风格名称

        Returns:
            词根字典，格式为 {类别名: [{"word": "词根", "tags": ["标签"]}, ...]}
        """
        # 获取词根配置（使用新结构）
        categories_config = self.config_manager.get_word_root_categories(style_name)

        if not categories_config:
            logger.warning(f"[{style_name}] 未找到词根类别配置，使用默认配置")
            categories_config = [{"name": "默认", "description": "通用词根", "examples": ["词", "根"], "count_per_category": 25}]

        # 计算每个类别的词根数量（从配置中读取，默认25）
        category_counts = {}
        for category in categories_config:
            category_name = category["name"]
            count = category.get("count_per_category", 25)
            category_counts[category_name] = count

        # 构建一次性生成所有类别的Prompt
        prompt = self._build_batch_generation_prompt(style_name, categories_config, 25)

        logger.info(f"[{style_name}] 开始一次性生成所有类别的词根...")

        # 调用API生成
        response = self.glm_client.generate(prompt)

        roots = {}

        if response.get("error"):
            logger.error(f"[{style_name}] 生成词根失败: {response['error']}")
            # 使用示例作为回退
            for category in categories_config:
                category_name = category["name"]
                count = category_counts.get(category_name, 25)
                examples = category.get("examples", [])[:count]
                # 转换为字典格式
                roots[category_name] = [{"word": ex, "tags": []} for ex in examples]
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
                    count = category_counts.get(category_name, 25)
                    examples = category.get("examples", [])[:count]
                    roots[category_name] = [{"word": ex, "tags": []} for ex in examples]
                return roots

            # 处理每个类别的词根
            for category in categories_config:
                category_name = category["name"]
                count = category_counts.get(category_name, 25)
                category_roots = parsed_roots.get(category_name, [])

                if not isinstance(category_roots, list):
                    logger.warning(f"[{style_name}] 类别 '{category_name}' 返回格式错误，使用示例")
                    category_roots = category.get("examples", [])

                # 处理词根格式：支持字符串或字典格式
                processed_roots = []
                for root_item in category_roots:
                    if isinstance(root_item, str):
                        # 旧格式：纯字符串，转换为字典格式
                        processed_roots.append({"word": root_item, "tags": []})
                    elif isinstance(root_item, dict) and "word" in root_item:
                        # 新格式：字典格式，保持不变
                        # 确保tags字段存在
                        if "tags" not in root_item:
                            root_item["tags"] = []
                        processed_roots.append(root_item)
                    else:
                        logger.warning(f"[{style_name}] 词根格式错误，跳过: {root_item}")

                # 确保词根数量
                if len(processed_roots) < count:
                    # 补充示例词根
                    examples = category.get("examples", [])
                    while len(processed_roots) < count and examples:
                        example_word = examples[len(processed_roots) % len(examples)]
                        processed_roots.append({"word": example_word, "tags": []})

                roots[category_name] = processed_roots
                logger.info(f"[{style_name}] 类别 '{category_name}' 生成了 {len(processed_roots)} 个词根")

        except json.JSONDecodeError as e:
            logger.error(f"[{style_name}] 解析词根失败: {e}")
            logger.debug(f"原始响应: {response.get('content', '')[:200]}")
            # 使用示例作为回退
            for category in categories_config:
                category_name = category["name"]
                count = category_counts.get(category_name, 25)
                examples = category.get("examples", [])[:count]
                roots[category_name] = [{"word": ex, "tags": []} for ex in examples]

        return roots

    def _save_roots_to_file(self, style_name: str, roots: Dict[str, List[Dict]]) -> None:
        """
        保存词根到YAML文件

        Args:
            style_name: 风格名称
            roots: 词根字典，格式为 {类别名: [{"word": "词根", "tags": ["标签"]}, ...]}
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
        self, style_name: str, categories: List[Dict], default_count: int
    ) -> str:
        """
        构建批量词根生成Prompt（一次性生成所有类别）
        支持从配置文件读取模板，并添加标签要求

        Args:
            style_name: 风格名称
            categories: 类别配置列表
            default_count: 默认每个类别需要生成的词根数量（当类别未指定时使用）

        Returns:
            Prompt文本
        """
        # 构建类别描述（每个类别可以有自己的count_per_category）
        categories_desc = []
        for category in categories:
            category_name = category["name"]
            description = category["description"]
            examples = category.get("examples", [])
            examples_str = ", ".join(examples[:5]) if examples else "无"
            count = category.get("count_per_category", default_count)
            categories_desc.append(
                f"- {category_name}: {description}（{count}个），参考示例：{examples_str}"
            )

        categories_desc_str = "\n".join(categories_desc)

        # 获取标签配置
        tag_config = self.config_manager.get_style_tags(style_name)
        available_tags = tag_config.get("available", [])
        available_tags_str = "、".join(available_tags) if available_tags else "无"

        # 构建返回格式示例（带标签）
        example_output = {}
        for category in categories:
            category_name = category["name"]
            examples = category.get("examples", [])
            if available_tags:
                # 如果有标签配置，示例中包含标签
                example_output[category_name] = [
                    {"word": examples[0] if examples else "示例1", "tags": [available_tags[0]]},
                    {"word": examples[1] if len(examples) > 1 else "示例2", "tags": [available_tags[0]]},
                ]
            else:
                # 如果没有标签配置，使用旧格式
                example_output[category_name] = examples[:3] if examples else ["示例1", "示例2", "示例3"]

        example_json = json.dumps(example_output, ensure_ascii=False, indent=2)

        # 从配置读取模板，使用默认模板作为回退
        template = self.config_manager.get_prompt_config(
            "word_root_generation",
            "template",
            default=self._get_default_word_root_template()
        )

        # 渲染模板
        prompt = template.format(
            style_name=style_name,
            categories_desc=categories_desc_str,
            available_tags=available_tags_str,
            example_json=example_json
        )

        return prompt

    def _get_default_word_root_template(self) -> str:
        """获取默认词根生成模板（当配置文件不存在时使用）"""
        return """请为{style_name}风格生成词根，包含以下类别：

{categories_desc}

要求：
1. 尽量按照每个类别指定的数量生成优质词根，避免生成劣质不符合风格的词根充数
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

    def regenerate_roots(self, style_name: str) -> Dict[str, List[Dict]]:
        """
        重新生成指定风格的词根

        Args:
            style_name: 风格名称

        Returns:
            新生成的词根字典，格式为 {类别名: [{"word": "词根", "tags": ["标签"]}, ...]}
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
