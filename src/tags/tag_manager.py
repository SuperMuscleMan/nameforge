"""
标签管理器
负责标签的验证和兼容性检查
"""

import logging
from typing import List, Set

from src.config.config_manager import ConfigManager

logger = logging.getLogger("rand_names")


class TagManager:
    """
    标签管理器
    负责标签的验证和兼容性检查
    """

    def __init__(self, config_manager: ConfigManager):
        """
        初始化标签管理器

        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        logger.info("TagManager 已初始化")

    def check_tag_compatibility(
        self, tags1: List[str], tags2: List[str], style_name: str
    ) -> bool:
        """
        检查两组标签是否兼容（无冲突）

        Args:
            tags1: 第一组标签
            tags2: 第二组标签
            style_name: 风格名称

        Returns:
            是否兼容（True表示无冲突）
        """
        # 获取标签配置
        tag_config = self.config_manager.get_style_tags(style_name)
        conflicts = tag_config.get("conflicts", [])

        # 合并所有标签
        all_tags = set(tags1 + tags2)

        # 检查冲突规则
        for conflict_pair in conflicts:
            if len(conflict_pair) >= 2:
                tag_a, tag_b = conflict_pair[0], conflict_pair[1]
                if tag_a in all_tags and tag_b in all_tags:
                    logger.debug(
                        f"[{style_name}] 标签冲突: {tag_a} 与 {tag_b} 不能同时出现"
                    )
                    return False

        return True

    def validate_tags(self, tags: List[str], style_name: str) -> bool:
        """
        验证标签是否在允许范围内

        Args:
            tags: 标签列表
            style_name: 风格名称

        Returns:
            是否全部有效
        """
        # 获取标签配置
        tag_config = self.config_manager.get_style_tags(style_name)
        available = tag_config.get("available", [])

        # 如果没有配置可用标签，则不进行验证
        if not available:
            return True

        # 检查所有标签是否在可用范围内
        for tag in tags:
            if tag not in available:
                logger.warning(f"[{style_name}] 标签 '{tag}' 不在可用范围内")
                return False

        return True

    def get_available_tags(self, style_name: str) -> List[str]:
        """
        获取指定风格的可用标签列表

        Args:
            style_name: 风格名称

        Returns:
            可用标签列表
        """
        tag_config = self.config_manager.get_style_tags(style_name)
        return tag_config.get("available", [])

    def get_conflicts(self, style_name: str) -> List[List[str]]:
        """
        获取指定风格的标签冲突规则

        Args:
            style_name: 风格名称

        Returns:
            冲突规则列表
        """
        tag_config = self.config_manager.get_style_tags(style_name)
        return tag_config.get("conflicts", [])

    def has_tag_system(self, style_name: str) -> bool:
        """
        检查指定风格是否启用了标签系统

        Args:
            style_name: 风格名称

        Returns:
            是否启用标签系统
        """
        tag_config = self.config_manager.get_style_tags(style_name)
        available = tag_config.get("available", [])
        return len(available) > 0
