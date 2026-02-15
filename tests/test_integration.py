"""
集成测试
完整的端到端流程测试
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from src.config.config_manager import ConfigManager
from src.prompts.prompt_manager import PromptManager
from src.api.glm_client import GLMClient
from src.storage.storage_manager import StorageManager
from src.pipeline.generation_pipeline import GenerationPipeline
import yaml


@pytest.fixture
def integration_env():
    """为集成测试创建完整环境"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # 创建config目录和文件
        config_dir = tmpdir / "config"
        config_dir.mkdir()

        # 创建config.yaml
        config_data = {
            "system": {"log_level": "DEBUG"},
            "api": {"provider": "glm", "timeout": 30},
        }
        with open(config_dir / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        # 创建styles.yaml
        styles_data = {
            "prompts": {
                "default_template": "生成{count}个{style_description}的昵称，长度{min_len}-{max_len}，字符集{charset}。避免重复：{recent_names}",
                "style_templates": {
                    "古风": "生成{count}个古代诗词风格的昵称。长度{min_len}-{max_len}，字符集{charset}。避免重复：{recent_names}",
                },
            },
            "styles": {
                "古风": {
                    "description": "古代诗词文化风格",
                    "length_min": 2,
                    "length_max": 6,
                    "charset": "中文",
                    "prompt_template": "古风",
                    "enabled": True,
                },
            },
        }
        with open(config_dir / "styles.yaml", "w", encoding="utf-8") as f:
            yaml.dump(styles_data, f)

        # 创建data目录
        data_dir = tmpdir / "data"
        data_dir.mkdir()

        yield {
            "config_dir": str(config_dir),
            "data_dir": str(data_dir),
            "tmpdir": tmpdir,
        }


@pytest.fixture
def pipeline_with_mocked_api(integration_env):
    """创建带Mock API的Pipeline"""
    with patch.dict("os.environ", {"GLM_API_KEY": "test_key"}):
        config_manager = ConfigManager(config_dir=integration_env["config_dir"])
        prompt_manager = PromptManager(config_manager)
        glm_client = GLMClient(api_key="test_key")
        storage_manager = StorageManager(base_dir=integration_env["data_dir"])

        pipeline = GenerationPipeline(
            glm_client=glm_client,
            config_manager=config_manager,
            prompt_manager=prompt_manager,
            storage=storage_manager,
        )

        yield pipeline, integration_env


class TestIntegration:
    """集成测试类"""

    @patch("src.api.glm_client.requests.post")
    def test_end_to_end_generation(self, mock_post, pipeline_with_mocked_api):
        """测试完整的生成流程"""
        pipeline, env = pipeline_with_mocked_api

        # Mock API响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            ["雪月风", "林溪烟", "竹海清音", "古月长庚", "诗意烟雨"]
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
        }
        mock_response.text = json.dumps(mock_response.json.return_value)
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        # 执行生成
        result = pipeline.generate_for_style("古风", count=5)

        # 验证结果
        assert result["stats"]["generated"] == 5
        assert result["stats"]["valid"] == 5
        assert len(result["valid_names"]) == 5

        # 验证文件被创建
        output_file = Path(env["data_dir"]) / "古风_names.txt"
        assert output_file.exists()

        # 验证内容
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "雪月风" in content
            assert "林溪烟" in content

        # 验证元数据被记录
        metadata_file = Path(env["data_dir"]) / "古风_metadata.txt"
        assert metadata_file.exists()

    @patch("src.api.glm_client.requests.post")
    def test_generation_with_invalid_json(self, mock_post, pipeline_with_mocked_api):
        """测试API返回无效JSON时的处理"""
        pipeline, env = pipeline_with_mocked_api

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "这不是有效的JSON"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }
        mock_response.text = json.dumps(mock_response.json.return_value)
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        result = pipeline.generate_for_style("古风", count=5)

        # 应该返回0个有效昵称
        assert result["stats"]["valid"] == 0
        assert len(result["valid_names"]) == 0

    @patch("src.api.glm_client.requests.post")
    def test_generation_with_mixed_valid_invalid(self, mock_post, pipeline_with_mocked_api):
        """测试混合有效和无效数据"""
        pipeline, env = pipeline_with_mocked_api

        mock_response = Mock()
        # 返回混合的数据
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            ["有效1", "  有效2  ", "", "有效3很长很长的昵称超过最大长度了", "有效4"]
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }
        mock_response.text = json.dumps(mock_response.json.return_value)
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        result = pipeline.generate_for_style("古风", count=6)

        # 应该有3个有效（去掉空字符串和超长的）
        assert result["stats"]["valid"] == 3
        assert "有效1" in result["valid_names"]
        assert "有效2" in result["valid_names"]  # 空白应该被删除

    @patch("src.api.glm_client.requests.post")
    def test_generation_nonexistent_style(self, mock_post, pipeline_with_mocked_api):
        """测试生成不存在的风格"""
        pipeline, env = pipeline_with_mocked_api

        result = pipeline.generate_for_style("不存在的风格", count=5)

        # 应该返回错误
        assert "error" in result["stats"]

    @patch("src.api.glm_client.requests.post")
    def test_multiple_generation_same_style(self, mock_post, pipeline_with_mocked_api):
        """测试连续生成同一风格"""
        pipeline, env = pipeline_with_mocked_api

        # 第一次生成
        mock_response1 = Mock()
        mock_response1.json.return_value = {
            "choices": [{"message": {"content": json.dumps(["昵称1", "昵称2", "昵称3"])}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }
        mock_response1.text = json.dumps(mock_response1.json.return_value)
        mock_response1.status_code = 200
        mock_response1.headers = {}
        mock_response1.raise_for_status = Mock()

        # 第二次生成
        mock_response2 = Mock()
        mock_response2.json.return_value = {
            "choices": [{"message": {"content": json.dumps(["昵称4", "昵称5", "昵称6"])}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }
        mock_response2.text = json.dumps(mock_response2.json.return_value)
        mock_response2.status_code = 200
        mock_response2.headers = {}
        mock_response2.raise_for_status = Mock()

        mock_post.side_effect = [mock_response1, mock_response2]

        # 执行两次生成
        result1 = pipeline.generate_for_style("古风", count=3)
        result2 = pipeline.generate_for_style("古风", count=3)

        # 验证两次都成功
        assert result1["stats"]["valid"] == 3
        assert result2["stats"]["valid"] == 3

        # 验证文件中有6条数据
        output_file = Path(env["data_dir"]) / "古风_names.txt"
        with open(output_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 6

    def test_config_dynamic_reload(self, pipeline_with_mocked_api):
        """测试配置动态加载"""
        pipeline, env = pipeline_with_mocked_api

        # 获取原始的Prompt
        original_template = pipeline.prompt_manager.get_prompt_template("古风")

        # 修改styles.yaml文件
        styles_path = Path(env["config_dir"]) / "styles.yaml"
        new_styles_data = {
            "prompts": {
                "default_template": "新的默认模板",
                "style_templates": {
                    "古风": "修改后的古风模板{count}",
                },
            },
            "styles": {
                "古风": {
                    "description": "修改后的描述",
                    "length_min": 2,
                    "length_max": 6,
                    "charset": "中文",
                    "prompt_template": "古风",
                    "enabled": True,
                },
            },
        }

        with open(styles_path, "w", encoding="utf-8") as f:
            yaml.dump(new_styles_data, f)

        # 手动触发配置检查和重载
        pipeline.config_manager.check_and_reload()

        # 验证新的Prompt被加载
        new_template = pipeline.prompt_manager.get_prompt_template("古风")
        assert new_template != original_template
        assert "修改后的古风模板" in new_template
