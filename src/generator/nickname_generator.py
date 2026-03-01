"""
昵称生成模块
基于词根和模板生成昵称，支持标签匹配
"""

import logging
import random
import re
from itertools import product
from typing import Dict, List, Optional, Set, Tuple

from src.config.config_manager import ConfigManager
from src.tags.tag_manager import TagManager

logger = logging.getLogger("rand_names")


class NicknameGenerator:
    """
    基于词根和模板生成昵称
    """

    def __init__(self, config_manager: ConfigManager):
        """
        初始化昵称生成器

        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.tag_manager = TagManager(config_manager)
        logger.info("NicknameGenerator 已初始化")

    def generate(
        self,
        style_name: str,
        roots: Dict[str, List[Dict]],  # 修改类型：List[Dict] 而不是 List[str]
        count: int,
        existing_names: Optional[Set[str]] = None,  # 新增参数：已存在的昵称集合
    ) -> List[str]:
        """
        生成指定数量的昵称

        流程:
        1. 获取模板列表
        2. 生成所有可能的组合（笛卡尔积）
        3. 应用过滤规则（包括标签兼容性检查）
        4. 去重
        5. 排除已存在的昵称
        6. 随机采样指定数量

        Args:
            style_name: 风格名称
            roots: 词根字典，格式为 {类别: [{"word": "词根", "tags": ["标签"]}, ...]}
            count: 需要生成的数量
            existing_names: 已存在的昵称集合（用于去重）

        Returns:
            昵称列表
        """
        logger.info(f"[{style_name}] 开始生成昵称，目标数量: {count}")

        # 1. 获取模板列表
        templates = self._get_templates(style_name)
        if not templates:
            logger.error(f"[{style_name}] 未找到模板配置")
            return []

        logger.debug(f"[{style_name}] 使用 {len(templates)} 个模板")

        # 2. 获取风格配置和过滤配置
        style_config = self.config_manager.get_style(style_name) or {}
        style_filters = self.config_manager.get_style_filters(style_name)

        # 3. 生成所有候选昵称
        all_candidates: List[Tuple[str, List[str]]] = []  # [(昵称, [标签]), ...]

        for template in templates:
            candidates = self._apply_template(template, roots, style_name)
            all_candidates.extend(candidates)
            logger.debug(f"[{style_name}] 模板 '{template}' 生成 {len(candidates)} 个候选")

        logger.info(f"[{style_name}] 模板组合共生成 {len(all_candidates)} 个候选昵称")

        # 4. 应用过滤规则（包括标签兼容性检查）
        filtered_candidates = self._apply_filters(
            all_candidates, style_config, style_filters, style_name
        )

        logger.info(f"[{style_name}] 过滤后剩余 {len(filtered_candidates)} 个候选")

        # 5. 去重
        unique_candidates = list(set(filtered_candidates))
        logger.info(f"[{style_name}] 去重后剩余 {len(unique_candidates)} 个唯一昵称")

        # 6. 排除已存在的昵称（文件中已有的）
        if existing_names:
            unique_candidates = [name for name in unique_candidates if name not in existing_names]
            logger.info(f"[{style_name}] 排除已存在昵称后剩余 {len(unique_candidates)} 个")

        # 8. 随机采样
        if len(unique_candidates) <= count:
            result = unique_candidates
            logger.info(f"[{style_name}] 候选数量不足，返回全部 {len(result)} 个")
        else:
            result = random.sample(unique_candidates, count)
            logger.info(f"[{style_name}] 随机采样 {count} 个昵称")

        return result

    def _get_templates(self, style_name: str) -> List[str]:
        """
        获取指定风格的模板列表

        Args:
            style_name: 风格名称

        Returns:
            模板列表
        """
        templates = self.config_manager.get_word_root_templates(style_name)

        if not templates:
            # 使用默认模板
            templates = ["{A}{B}"]
            logger.warning(f"[{style_name}] 未找到模板，使用默认模板")

        return templates

    def _apply_template(self, template: str, roots: Dict[str, List[Dict]], style_name: str) -> List[Tuple[str, List[str]]]:
        """
        应用单个模板生成候选昵称

        支持标签约束语法：{类别:标签}
        例如: template="{modifier:暖色调}{subject:治愈}"

        Args:
            template: 模板字符串
            roots: 词根字典，格式为 {类别: [{"word": "词根", "tags": ["标签"]}, ...]}
            style_name: 风格名称

        Returns:
            候选昵称列表，格式为 [(昵称, [所有标签]), ...]
        """
        # 解析模板中的类别和标签约束
        # 格式：{类别} 或 {类别:标签}
        pattern = r'\{(\w+)(?::(\w+))?\}'
        matches = re.findall(pattern, template)

        if not matches:
            # 模板中没有占位符，直接返回模板本身
            return [(template, [])]

        # 提取类别和约束
        categories = []
        constraints = {}
        for category, tag_constraint in matches:
            categories.append(category)
            if tag_constraint:
                constraints[category] = tag_constraint

        # 检查所有类别是否都有对应的词根
        for category in categories:
            if category not in roots:
                logger.warning(f"模板中的类别 '{category}' 未找到对应词根")
                return []

        # 根据标签约束过滤词根
        filtered_roots = {}
        for category in categories:
            root_list = roots[category]

            if category in constraints:
                # 有标签约束：只选择包含该标签的词根
                tag_constraint = constraints[category]
                filtered = [r for r in root_list if tag_constraint in r.get("tags", [])]
                if not filtered:
                    logger.warning(
                        f"[{style_name}] 类别 '{category}' 中没有包含标签 '{tag_constraint}' 的词根"
                    )
                    return []
                filtered_roots[category] = filtered
            else:
                # 无约束：使用所有词根
                filtered_roots[category] = root_list

        # 获取每个类别的词根列表（只提取word字段）
        root_lists = []
        for category in categories:
            root_lists.append(filtered_roots[category])

        # 笛卡尔积生成所有组合
        combinations = product(*root_lists)

        # 替换模板生成昵称，并收集所有标签
        results = []
        for combo in combinations:
            # 生成昵称
            name = template
            all_tags = []
            for i, category in enumerate(categories):
                root_dict = combo[i]
                word = root_dict["word"]
                tags = root_dict.get("tags", [])

                # 替换占位符（移除标签约束部分）
                if category in constraints:
                    name = name.replace(f"{{{category}:{constraints[category]}}}", word)
                else:
                    name = name.replace(f"{{{category}}}", word)

                # 收集标签
                all_tags.extend(tags)

            results.append((name, all_tags))

        return results

    def _apply_filters(
        self,
        candidates: List[Tuple[str, List[str]]],  # 修改类型：包含标签信息
        style_config: Dict,
        filters_config: Dict,
        style_name: str,
    ) -> List[str]:
        """
        应用过滤规则

        - 长度检查
        - 重复字检查
        - 禁用组合检查
        - 标签兼容性检查（新增）

        Args:
            candidates: 候选昵称列表，格式为 [(昵称, [标签]), ...]
            style_config: 风格配置
            filters_config: 过滤规则配置
            style_name: 风格名称

        Returns:
            过滤后的昵称列表
        """
        filtered = []

        # 获取过滤配置
        forbid_duplicate = filters_config.get("forbid_duplicate_chars", True)
        forbidden_combinations = filters_config.get("forbidden_combinations", [])

        # 获取长度限制
        min_len = style_config.get("length_min", 2)
        max_len = style_config.get("length_max", 6)

        # 检查是否启用标签系统
        has_tag_system = self.tag_manager.has_tag_system(style_name)

        for name, tags in candidates:
            # 1. 长度检查
            if not (min_len <= len(name) <= max_len):
                continue

            # 2. 重复字检查
            if forbid_duplicate and self._has_duplicate_chars(name):
                continue

            # 3. 禁用组合检查
            if self._is_forbidden_combination(name, forbidden_combinations):
                continue

            # 4. 标签兼容性检查（仅当启用标签系统时）
            if has_tag_system and tags:
                # 检查标签是否有冲突
                if not self._check_tag_compatibility_internal(tags, style_name):
                    continue

            filtered.append(name)

        return filtered

    def _check_tag_compatibility_internal(self, tags: List[str], style_name: str) -> bool:
        """
        内部方法：检查单个昵称的标签是否兼容

        Args:
            tags: 标签列表
            style_name: 风格名称

        Returns:
            是否兼容
        """
        if not tags:
            return True

        # 获取冲突规则
        conflicts = self.tag_manager.get_conflicts(style_name)
        tag_set = set(tags)

        # 检查冲突
        for conflict_pair in conflicts:
            if len(conflict_pair) >= 2:
                tag_a, tag_b = conflict_pair[0], conflict_pair[1]
                if tag_a in tag_set and tag_b in tag_set:
                    logger.debug(
                        f"[{style_name}] 标签冲突: {tag_a} 与 {tag_b} 不能同时出现"
                    )
                    return False

        return True

    def _has_duplicate_chars(self, name: str) -> bool:
        """
        检查是否有重复字（如"云云"、"月月"）

        检查相邻字符是否重复

        Args:
            name: 昵称

        Returns:
            是否有重复字
        """
        for i in range(len(name) - 1):
            if name[i] == name[i + 1]:
                return True
        return False

    def _is_forbidden_combination(
        self, name: str, forbidden_list: List[List[str]]
    ) -> bool:
        """
        检查是否是禁用组合

        Args:
            name: 昵称
            forbidden_list: 禁用组合列表

        Returns:
            是否是禁用组合
        """
        for forbidden in forbidden_list:
            # 将禁用组合拼接成字符串检查
            forbidden_str = "".join(forbidden)
            if forbidden_str in name:
                return True
        return False

    def estimate_combinations(
        self, style_name: str, roots: Dict[str, List[Dict]]
    ) -> Dict[str, int]:
        """
        估算各模板的组合数量

        Args:
            style_name: 风格名称
            roots: 词根字典，格式为 {类别: [{"word": "词根", "tags": ["标签"]}, ...]}

        Returns:
            各模板的理论组合数
        """
        templates = self._get_templates(style_name)
        estimates = {}

        for template in templates:
            # 提取类别（忽略标签约束）
            pattern = r'\{(\w+)(?::\w+)?\}'
            categories = re.findall(pattern, template)

            if not categories:
                estimates[template] = 1
                continue

            # 计算笛卡尔积数量
            total = 1
            for category in categories:
                if category in roots:
                    total *= len(roots[category])
                else:
                    total = 0
                    break

            estimates[template] = total

        return estimates
