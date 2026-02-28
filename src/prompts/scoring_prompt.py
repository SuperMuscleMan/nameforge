"""
评分Prompt模板
用于昵称质量评分的Prompt生成
支持从配置文件读取
"""

from typing import List, Dict, Any, Optional


class ScoringPrompt:
    """评分Prompt管理器，支持从配置文件读取"""

    # 默认评分维度定义（当配置文件不存在时使用）
    DEFAULT_DIMENSIONS = [
        {"name": "创意性", "weight": 25, "desc": "脑洞大小、独特性、避雷雷同"},
        {"name": "可读性", "weight": 20, "desc": "易读程度、发音难易、避开生僻字"},
        {"name": "视觉美感", "weight": 15, "desc": "字形平衡、符号点缀的适度感"},
        {"name": "风格契合", "weight": 15, "desc": "与玩家人设或游戏背景的匹配度"},
        {"name": "稀缺价值", "weight": 15, "desc": "词汇的珍贵程度（如短词、古风词）"},
        {"name": "社交记忆点", "weight": 10, "desc": "是否好记、是否有梗、是否有传播力"},
    ]

    # 默认模板（当配置文件不存在时使用）
    DEFAULT_TEMPLATE = """你是一名专业的游戏昵称质量评估专家。请对以下【{style}】风格的昵称进行质量评分。

【风格说明】{style_description}

【评分维度与权重】
{dimensions_text}

【评分规则】
- 总分 = 各维度得分 × 权重，满分10分
- 保留1位小数
- 同时给出简评（30字以内，说明得分理由）

【待评分昵称】
{names_list}

【输出格式】
严格返回JSON，不要包含任何Markdown代码块和额外文字：
{{"scores": [{{"name": "昵称1", "score": 8.5, "comment": "简评内容"}}, ...]}}
"""

    def __init__(self, config_manager=None):
        """
        初始化评分Prompt管理器

        Args:
            config_manager: 配置管理器实例，如为None则使用默认配置
        """
        self.config_manager = config_manager

    def render(
        self,
        style: str,
        style_description: str,
        names: List[str],
    ) -> str:
        """
        渲染评分Prompt

        Args:
            style: 风格名称
            style_description: 风格描述
            names: 待评分昵称列表

        Returns:
            完整的Prompt文本
        """
        # 获取维度定义
        dimensions = self.get_dimensions()

        # 构建维度说明
        dimensions_text = "\n".join([
            f"{i+1}. {d['name']}({d['weight']}%)：{d.get('description', d.get('desc', ''))}"
            for i, d in enumerate(dimensions)
        ])

        # 构建昵称列表
        names_list = "\n".join([f"{i+1}. {name}" for i, name in enumerate(names)])

        # 从配置读取模板，使用默认模板作为回退
        template = self._get_template()

        # 渲染模板
        prompt = template.format(
            style=style,
            style_description=style_description,
            dimensions_text=dimensions_text,
            names_list=names_list
        )

        return prompt

    def _get_template(self) -> str:
        """获取评分Prompt模板"""
        if self.config_manager:
            template = self.config_manager.get_prompt_config("scoring", "template")
            if template:
                return template
        return self.DEFAULT_TEMPLATE

    def get_dimensions(self) -> List[Dict[str, Any]]:
        """
        获取评分维度定义
        优先从配置文件读取，使用默认配置作为回退
        """
        if self.config_manager:
            dimensions = self.config_manager.get_prompt_config("scoring", "dimensions")
            if dimensions:
                return dimensions
        return self.DEFAULT_DIMENSIONS.copy()

    def calculate_score(self, dimension_scores: Dict[str, float]) -> float:
        """
        根据维度得分计算总分

        Args:
            dimension_scores: 维度得分字典，如{"创意性": 8.5, "可读性": 9.0, ...}

        Returns:
            加权总分（保留1位小数）
        """
        dimensions = self.get_dimensions()
        total = 0.0
        for dim in dimensions:
            score = dimension_scores.get(dim["name"], 5.0)
            weight = dim.get("weight", 0)
            total += score * (weight / 100)
        return round(total, 1)


# 保持向后兼容的类方法
class ScoringPromptLegacy:
    """兼容旧版静态方法的评分Prompt（已弃用，请使用ScoringPrompt实例）"""

    @staticmethod
    def render(style: str, style_description: str, names: List[str]) -> str:
        """渲染评分Prompt（使用默认配置）"""
        prompt_manager = ScoringPrompt()
        return prompt_manager.render(style, style_description, names)

    @staticmethod
    def get_dimensions() -> List[Dict[str, Any]]:
        """获取评分维度定义（使用默认配置）"""
        prompt_manager = ScoringPrompt()
        return prompt_manager.get_dimensions()

    @staticmethod
    def calculate_score(dimension_scores: Dict[str, float]) -> float:
        """计算总分（使用默认配置）"""
        prompt_manager = ScoringPrompt()
        return prompt_manager.calculate_score(dimension_scores)
