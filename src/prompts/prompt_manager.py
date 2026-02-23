"""
Prompt管理系统
支持模板化和风格自定义
"""

import logging
from typing import Optional, List
from src.config.config_manager import ConfigManager

logger = logging.getLogger("rand_names")


class PromptManager:
    """管理Prompt模板，支持风格自定义和模板渲染"""

    def __init__(self, config_manager: ConfigManager):
        """
        初始化Prompt管理器

        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager

    def get_prompt_template(self, style_name: str) -> str:
        """
        获取Prompt模板
        优先返回风格特定模板，如不存在则返回默认模板

        Args:
            style_name: 风格名称

        Returns:
            Prompt模板文本
        """
        templates = self.config_manager.get_prompt_templates()

        # 首先尝试获取风格特定模板
        style_templates = templates.get("style_templates", {})
        if style_name in style_templates:
            logger.debug(f"使用风格特定模板: {style_name}")
            return style_templates[style_name]

        # 返回默认模板
        default = templates.get("default_template", "")
        logger.debug(f"使用默认模板: {style_name}")
        return default

    def render_prompt(
        self,
        style_name: str,
        style_description: str,
        min_len: int,
        max_len: int,
        charset: str,
        count: int,
        recent_names: Optional[List[str]] = None,
    ) -> str:
        """
        渲染Prompt：用实际值替换占位符

        支持的占位符：
        - {style_description}: 风格文本描述
        - {min_len}/{max_len}: 长度范围
        - {charset}: 字符集
        - {count}: 生成数量
        - {recent_names}: 最近昵称（避免重复）

        Args:
            style_name: 风格名称
            style_description: 风格描述
            min_len: 最小长度
            max_len: 最大长度
            charset: 字符集
            count: 生成数量
            recent_names: 最近的昵称列表（用于避免重复）

        Returns:
            完整的Prompt文本

        Raises:
            ValueError: 如果风格不存在或必要参数缺失
        """
        # 验证参数
        if not style_name:
            raise ValueError("风格名称不能为空")
        if min_len <= 0 or max_len <= 0:
            raise ValueError("长度参数必须为正数")
        if max_len < min_len:
            raise ValueError("最大长度不能小于最小长度")
        if count <= 0:
            raise ValueError("生成数量必须为正数")

        # 获取模板
        template = self.get_prompt_template(style_name)
        if not template:
            raise ValueError(f"无法获取风格 {style_name} 的Prompt模板")

        # 格式化最近昵称
        recent_names_str = self._format_recent_names(recent_names)

        # 替换占位符
        prompt = template.format(
            style_description=style_description,
            min_len=min_len,
            max_len=max_len,
            charset=charset,
            count=count,
            recent_names=recent_names_str,
        )

        logger.debug(
            f"成功渲染Prompt [风格={style_name}, 数量={count}, "
            f"长度={min_len}-{max_len}]"
        )
        return prompt

    def _format_recent_names(self, recent_names: Optional[List[str]]) -> str:
        """
        格式化最近昵称列表为文本

        Args:
            recent_names: 昵称列表

        Returns:
            格式化后的文本
        """
        if not recent_names:
            return "（无）"

        # 限制显示数量
        max_display = 20
        names_to_display = recent_names[:max_display]

        formatted = "、".join(names_to_display)
        if len(recent_names) > max_display:
            formatted += f"等（共{len(recent_names)}条）"

        return formatted
