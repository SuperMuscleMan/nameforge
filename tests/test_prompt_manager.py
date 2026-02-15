"""
PromptManager 单元测试
"""

import pytest
from unittest.mock import Mock
from src.prompts.prompt_manager import PromptManager


@pytest.fixture
def mock_config_manager():
    """创建Mock ConfigManager"""
    mock = Mock()
    mock.get_prompt_templates.return_value = {
        "default_template": "生成{count}个{style_description}的昵称，长度{min_len}-{max_len}，字符集{charset}。避免：{recent_names}",
    }
    return mock


@pytest.fixture
def prompt_manager(mock_config_manager):
    """创建PromptManager实例"""
    return PromptManager(mock_config_manager)


class TestPromptManager:
    """PromptManager 测试类"""

    def test_get_prompt_template_style_specific(self, prompt_manager):
        """测试获取模板"""
        template = prompt_manager.get_prompt_template("古风")

        assert template is not None
        assert "生成{count}个" in template

    def test_get_prompt_template_default(self, prompt_manager):
        """测试获取默认模板"""
        template = prompt_manager.get_prompt_template("未知风格")

        assert template is not None
        assert "生成{count}个" in template

    def test_render_prompt_basic(self, prompt_manager):
        """测试基础Prompt渲染"""
        prompt = prompt_manager.render_prompt(
            style_name="古风",
            style_description="古代诗词特征",
            min_len=2,
            max_len=6,
            charset="中文",
            count=100,
        )

        assert "{" not in prompt  # 所有占位符都应该被替换
        assert "古代诗词特征" in prompt
        assert "100" in prompt
        assert "中文" in prompt

    def test_render_prompt_with_recent_names(self, prompt_manager):
        """测试带最近数据的Prompt渲染"""
        recent = ["昵称1", "昵称2", "昵称3"]
        prompt = prompt_manager.render_prompt(
            style_name="古风",
            style_description="诗意古风",
            min_len=2,
            max_len=6,
            charset="中文",
            count=50,
            recent_names=recent,
        )

        assert "昵称1" in prompt
        assert "昵称2" in prompt

    def test_render_prompt_empty_recent_names(self, prompt_manager):
        """测试空的最近数据"""
        prompt = prompt_manager.render_prompt(
            style_name="二次元",
            style_description="二次元特征",
            min_len=3,
            max_len=8,
            charset="中文+假名",
            count=100,
            recent_names=None,
        )

        assert "（无）" in prompt

    def test_render_prompt_many_recent_names(self, prompt_manager):
        """测试较多的最近数据"""
        recent = [f"昵称_{i}" for i in range(50)]
        prompt = prompt_manager.render_prompt(
            style_name="古风",
            style_description="诗意",
            min_len=2,
            max_len=6,
            charset="中文",
            count=100,
            recent_names=recent,
        )

        # 应该包含前20个和数量信息
        assert "昵称_0" in prompt
        assert "共50条" in prompt

    def test_render_prompt_invalid_style_name(self, prompt_manager):
        """测试无效的风格名称"""
        with pytest.raises(ValueError):
            prompt_manager.render_prompt(
                style_name="",
                style_description="描述",
                min_len=2,
                max_len=6,
                charset="中文",
                count=100,
            )

    def test_render_prompt_invalid_length(self, prompt_manager):
        """测试无效的长度参数"""
        with pytest.raises(ValueError):
            prompt_manager.render_prompt(
                style_name="古风",
                style_description="描述",
                min_len=-1,
                max_len=6,
                charset="中文",
                count=100,
            )

        with pytest.raises(ValueError):
            prompt_manager.render_prompt(
                style_name="古风",
                style_description="描述",
                min_len=6,
                max_len=2,
                charset="中文",
                count=100,
            )

    def test_render_prompt_invalid_count(self, prompt_manager):
        """测试无效的生成数量"""
        with pytest.raises(ValueError):
            prompt_manager.render_prompt(
                style_name="古风",
                style_description="描述",
                min_len=2,
                max_len=6,
                charset="中文",
                count=-1,
            )

    def test_format_recent_names_empty(self, prompt_manager):
        """测试格式化空的最近名单"""
        formatted = prompt_manager._format_recent_names(None)
        assert formatted == "（无）"

        formatted = prompt_manager._format_recent_names([])
        assert formatted == "（无）"

    def test_format_recent_names_small(self, prompt_manager):
        """测试格式化少量最近名单"""
        names = ["A", "B", "C"]
        formatted = prompt_manager._format_recent_names(names)

        assert "A" in formatted
        assert "B" in formatted
        assert "C" in formatted
        assert "、" in formatted

    def test_format_recent_names_many(self, prompt_manager):
        """测试格式化大量最近名单"""
        names = [f"name_{i}" for i in range(50)]
        formatted = prompt_manager._format_recent_names(names)

        assert "共50条" in formatted
