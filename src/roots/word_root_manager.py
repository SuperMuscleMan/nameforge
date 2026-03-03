"""
词根管理模块
负责词根的生成、存储和加载
"""

import json
import logging
import time
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

        # 2. 检查文件是否存在并加载
        existing_roots = self._load_roots_from_file(style_name)

        # 3. 获取类别配置以检查数量是否满足
        categories_config = self.config_manager.get_word_root_categories(style_name)
        if not categories_config:
            logger.warning(f"[{style_name}] 未找到词根类别配置，使用默认配置")
            categories_config = [{"name": "默认", "description": "通用词根", "examples": ["词", "根"], "count_per_category": 25}]

        # 4. 检查是否需要生成或补充词根
        need_generate = False
        if existing_roots is None:
            logger.info(f"[{style_name}] 词根文件不存在，开始生成词根...")
            existing_roots = {}
            need_generate = True
        else:
            # 检查每个类别的词根数量是否满足要求
            insufficient_categories = self._check_roots_sufficient(existing_roots, categories_config)
            if insufficient_categories:
                logger.info(f"[{style_name}] 发现 {len(insufficient_categories)} 个类别词根不足，需要补充")
                need_generate = True

        if need_generate:
            # 5. 逐个类别生成词根（支持增量补充）
            roots = self._generate_roots_by_category(style_name, categories_config, existing_roots)

            # 6. 保存到文件
            self._save_roots_to_file(style_name, roots)

            # 7. 更新缓存
            self.roots_cache[style_name] = roots
            return roots
        else:
            logger.info(f"[{style_name}] 从文件加载词根成功")
            self.roots_cache[style_name] = existing_roots
            return existing_roots

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

    def _check_roots_sufficient(self, existing_roots: Dict[str, List[Dict]], categories_config: List[Dict]) -> List[Dict]:
        """
        检查哪些类别的词根数量不足

        Args:
            existing_roots: 已存在的词根字典
            categories_config: 类别配置列表

        Returns:
            数量不足的类别配置列表
        """
        insufficient = []
        for category in categories_config:
            category_name = category["name"]
            required_count = category.get("count_per_category", 25)
            existing_count = len(existing_roots.get(category_name, []))

            if existing_count < required_count:
                insufficient.append({
                    "category": category,
                    "existing_count": existing_count,
                    "required_count": required_count,
                    "need_count": required_count - existing_count
                })
                logger.debug(f"[{category_name}] 词根不足: {existing_count}/{required_count}")

        return insufficient

    def _generate_roots_by_category(
        self,
        style_name: str,
        categories_config: List[Dict],
        existing_roots: Optional[Dict[str, List[Dict]]] = None
    ) -> Dict[str, List[Dict]]:
        """
        逐个类别生成词根

        流程:
        1. 检查每个类别的词根数量
        2. 数量不足的类别逐个调用API生成
        3. 每成功生成一个类别后立即存盘（防止中断丢失）
        4. 如某类别生成失败，中断流程但保留已生成的词根
        5. 类别间有配置的调用间隔

        Args:
            style_name: 风格名称
            categories_config: 类别配置列表
            existing_roots: 已存在的词根（用于增量补充），如为None则从头生成

        Returns:
            词根字典，格式为 {类别名: [{"word": "词根", "tags": ["标签"]}, ...]}
        """
        # 获取API调用间隔配置（默认3秒）
        api_interval = self.config_manager.get_system_config("api.category_interval_seconds", 3)

        # 初始化结果（基于现有词根或空字典）
        roots = existing_roots.copy() if existing_roots else {}

        # 检查哪些类别需要生成/补充
        insufficient_categories = self._check_roots_sufficient(roots, categories_config)

        if not insufficient_categories:
            logger.info(f"[{style_name}] 所有类别词根数量已满足要求")
            return roots

        logger.info(f"[{style_name}] 需要生成/补充 {len(insufficient_categories)} 个类别的词根")

        # 获取标签配置
        tag_config = self.config_manager.get_style_tags(style_name)
        available_tags = tag_config.get("available", [])

        # 逐个类别生成
        for idx, item in enumerate(insufficient_categories):
            category = item["category"]
            category_name = category["name"]
            need_count = item["need_count"]
            existing_count = item["existing_count"]

            logger.info(f"[{style_name}] 生成类别 '{category_name}' 的词根 ({idx+1}/{len(insufficient_categories)}): 需补充 {need_count} 个")

            try:
                # 构建单个类别的Prompt（使用配置文件）
                prompt = self._build_single_category_prompt_from_config(
                    style_name, category, need_count, available_tags
                )

                # 打印Prompt用于debug
                logger.debug(f"[{style_name}] 类别 '{category_name}' 的Prompt:\n{prompt}\n{'='*50}")

                # 调用API生成
                response = self.glm_client.generate(prompt)

                if response.get("error"):
                    logger.error(f"[{style_name}] 生成类别 '{category_name}' 词根失败: {response['error']}")
                    # 中断流程，但保留已生成的词根（已在前面的类别中保存）
                    raise RuntimeError(f"生成类别 '{category_name}' 词根失败: {response['error']}")

                # 解析响应
                category_roots = self._parse_category_response(
                    style_name, category_name, response, need_count, category.get("examples", [])
                )

                # 合并到现有词根（追加模式）
                if category_name not in roots:
                    roots[category_name] = []
                roots[category_name].extend(category_roots)

                logger.info(f"[{style_name}] 类别 '{category_name}' 成功生成 {len(category_roots)} 个词根，现有 {len(roots[category_name])} 个")

                # 立即保存到文件（防止中断丢失）
                self._save_roots_to_file(style_name, roots)
                logger.debug(f"[{style_name}] 类别 '{category_name}' 词根已保存到文件")

                # 类别间调用间隔（最后一个类别不需要等待）
                if idx < len(insufficient_categories) - 1:
                    logger.debug(f"等待 {api_interval} 秒后继续生成下一个类别...")
                    time.sleep(api_interval)

            except Exception as e:
                logger.error(f"[{style_name}] 生成类别 '{category_name}' 词根时发生异常: {e}")
                # 中断流程，但保留已生成的词根（已在前面的类别中保存）
                raise RuntimeError(f"生成类别 '{category_name}' 词根失败: {e}") from e

        return roots

    def _parse_category_response(
        self,
        style_name: str,
        category_name: str,
        response: Dict,
        expected_count: int,
        examples: List[str]
    ) -> List[Dict]:
        """
        解析单个类别的API响应

        Args:
            style_name: 风格名称
            category_name: 类别名称
            response: API响应
            expected_count: 期望的词根数量
            examples: 示例词根（用于fallback）

        Returns:
            解析后的词根列表
        """
        processed_roots = []

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

            if not isinstance(parsed_roots, list):
                logger.warning(f"[{style_name}] 类别 '{category_name}' 返回格式错误，期望JSON数组")
                # 尝试从字典中提取
                if isinstance(parsed_roots, dict) and category_name in parsed_roots:
                    parsed_roots = parsed_roots[category_name]
                else:
                    parsed_roots = []

            # 处理词根格式
            for root_item in parsed_roots:
                if isinstance(root_item, str):
                    processed_roots.append({"word": root_item, "tags": []})
                elif isinstance(root_item, dict) and "word" in root_item:
                    if "tags" not in root_item:
                        root_item["tags"] = []
                    processed_roots.append(root_item)
                else:
                    logger.warning(f"[{style_name}] 词根格式错误，跳过: {root_item}")

        except json.JSONDecodeError as e:
            logger.error(f"[{style_name}] 解析类别 '{category_name}' 词根失败: {e}")
            logger.debug(f"原始响应: {response.get('content', '')[:200]}")

        # 确保词根数量（补充示例）
        if len(processed_roots) < expected_count:
            logger.warning(f"[{style_name}] 类别 '{category_name}' 返回词根不足 ({len(processed_roots)}/{expected_count})，补充示例")
            while len(processed_roots) < expected_count and examples:
                example_word = examples[len(processed_roots) % len(examples)]
                processed_roots.append({"word": example_word, "tags": []})

        return processed_roots[:expected_count]  # 只返回需要的数量

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

    def _build_single_category_prompt_from_config(
        self, style_name: str, category: Dict, count: int, available_tags: List[str]
    ) -> str:
        """
        从配置文件构建单个类别词根生成的Prompt

        Args:
            style_name: 风格名称
            category: 类别配置
            count: 需要生成的词根数量
            available_tags: 可用标签列表

        Returns:
            Prompt文本
        """
        category_name = category["name"]
        category_description = category["description"]
        examples = category.get("examples", [])
        examples_str = ", ".join(examples[:10]) if examples else "无"

        # 构建标签说明和示例输出
        if available_tags:
            tags_str = "、".join(available_tags)
            tags_instruction = f"""可选标签：{tags_str}
为每个词根添加1-2个最匹配的标签。"""
            # 构建返回格式示例（带标签）
            example_output = json.dumps([
                {"word": examples[0] if examples else "示例1", "tags": [available_tags[0]] if available_tags else []},
                {"word": examples[1] if len(examples) > 1 else "示例2", "tags": [available_tags[0]] if available_tags else []},
            ], ensure_ascii=False, indent=2)
        else:
            tags_instruction = ""
            # 无标签配置的返回格式
            example_output = json.dumps(examples[:3] if examples else ["示例1", "示例2", "示例3"], ensure_ascii=False, indent=2)

        # 从配置读取模板
        template = self.config_manager.get_prompt_config(
            "single_category_word_root",
            "template",
            default=self._get_default_single_category_template()
        )

        # 渲染模板
        prompt = template.format(
            style_name=style_name,
            category_name=category_name,
            category_description=category_description,
            count=count,
            examples_str=examples_str,
            tags_instruction=tags_instruction,
            example_output=example_output
        )

        return prompt

    def _get_default_single_category_template(self) -> str:
        """获取默认单个类别词根生成模板（当配置文件不存在时使用）"""
        return """请为{style_name}风格生成{count}个高质量的'{category_name}'类别词根。

类别描述：{category_description}
参考示例：{examples_str}

{tags_instruction}

要求：
1. 必须符合{style_name}风格特征，体现{category_description}
2. 避免生僻字，常用字优先
3. 适合与其他词根组合成昵称
4. 词根长度1-4字为宜，鼓励使用双字词组增加多样性
5. 高质量、有美感、无攻击性、无敏感词
6. 词根之间要有明显差异，避免意思过于相近
7. 双字词根优先选择有画面感、有情感的词汇

返回JSON数组格式，仅返回词根列表，无其他文字。

格式示例：
{example_output}
"""

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
                    {"word":  "示例1", "tags": ["标签示例1"]},
                    {"word":  "示例2", "tags": ["标签示例1", "标签示例2"]},
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
