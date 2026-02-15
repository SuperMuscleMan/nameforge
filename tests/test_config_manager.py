"""
ConfigManager 单元测试
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from src.config.config_manager import ConfigManager


@pytest.fixture
def temp_config_dir():
    """创建临时配置目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建config.yaml
        config_data = {
            "system": {"log_level": "DEBUG"},
            "api": {"provider": "glm", "timeout": 30},
        }
        config_path = Path(tmpdir) / "config.yaml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        # 创建styles.yaml
        styles_data = {
            "prompts": {
                "default_template": "生成{count}个{style_description}昵称",
            },
            "styles": {
                "古风": {
                    "description": "古代风格",
                    "length_min": 2,
                    "length_max": 6,
                    "charset": "中文",
                    "enabled": True,
                },
                "二次元": {
                    "description": "二次元风格",
                    "length_min": 3,
                    "length_max": 8,
                    "charset": "中文",
                    "enabled": False,
                },
            },
        }
        styles_path = Path(tmpdir) / "styles.yaml"
        with open(styles_path, "w", encoding="utf-8") as f:
            yaml.dump(styles_data, f)

        yield tmpdir


class TestConfigManager:
    """ConfigManager 测试类"""

    def test_init_valid_config(self, temp_config_dir):
        """测试正常初始化"""
        config = ConfigManager(config_dir=temp_config_dir)
        assert config.styles is not None
        assert config.system_config is not None

    def test_load_styles(self, temp_config_dir):
        """测试加载风格配置"""
        config = ConfigManager(config_dir=temp_config_dir)
        styles = config.styles

        assert "古风" in styles
        assert "二次元" in styles
        assert styles["古风"]["description"] == "古代风格"

    def test_get_style(self, temp_config_dir):
        """测试获取单个风格"""
        config = ConfigManager(config_dir=temp_config_dir)
        style = config.get_style("古风")

        assert style is not None
        assert style["length_min"] == 2
        assert style["charset"] == "中文"

    def test_get_nonexistent_style(self, temp_config_dir):
        """测试获取不存在的风格"""
        config = ConfigManager(config_dir=temp_config_dir)
        style = config.get_style("不存在的风格")

        assert style is None

    def test_list_styles(self, temp_config_dir):
        """测试列出启用的风格"""
        config = ConfigManager(config_dir=temp_config_dir)
        enabled_styles = config.list_styles()

        assert "古风" in enabled_styles
        assert "二次元" not in enabled_styles  # 被禁用

    def test_get_system_config(self, temp_config_dir):
        """测试获取系统配置"""
        config = ConfigManager(config_dir=temp_config_dir)

        # 简单键
        log_level = config.get_system_config("system.log_level")
        assert log_level == "DEBUG"

        # 嵌套键
        timeout = config.get_system_config("api.timeout")
        assert timeout == 30

    def test_get_system_config_with_default(self, temp_config_dir):
        """测试获取系统配置（带默认值）"""
        config = ConfigManager(config_dir=temp_config_dir)

        value = config.get_system_config("不存在.的.键", default="default_value")
        assert value == "default_value"

    def test_get_prompt_templates(self, temp_config_dir):
        """测试获取所有Prompt模板"""
        config = ConfigManager(config_dir=temp_config_dir)
        templates = config.get_prompt_templates()

        assert "default_template" in templates

    def test_get_default_prompt_template(self, temp_config_dir):
        """测试获取默认Prompt模板"""
        config = ConfigManager(config_dir=temp_config_dir)
        template = config.get_default_prompt_template()

        assert template is not None
        assert "{count}" in template

    def test_validate_style_valid(self, temp_config_dir):
        """测试验证有效的风格"""
        config = ConfigManager(config_dir=temp_config_dir)
        is_valid = config.validate_style("古风")

        assert is_valid is True

    def test_validate_style_invalid(self, temp_config_dir):
        """测试验证无效的风格"""
        config = ConfigManager(config_dir=temp_config_dir)
        is_valid = config.validate_style("不存在的风格")

        assert is_valid is False

    def test_check_and_reload_no_change(self, temp_config_dir):
        """测试无文件变化时不重新加载"""
        config = ConfigManager(config_dir=temp_config_dir)
        original_styles = config.styles.copy()

        changed = config.check_and_reload()
        assert changed is False
        assert config.styles == original_styles

    def test_init_missing_config_dir(self):
        """测试初始化时配置目录不存在"""
        with pytest.raises(FileNotFoundError):
            ConfigManager(config_dir="/nonexistent/path")
