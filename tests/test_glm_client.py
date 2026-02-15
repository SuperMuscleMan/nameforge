"""
GLMClient 单元测试
"""

import pytest
import json
from unittest.mock import Mock, patch
from src.api.glm_client import GLMClient


@pytest.fixture
def glm_client():
    """创建GLMClient实例"""
    with patch.dict("os.environ", {"GLM_API_KEY": "test_key"}):
        return GLMClient(api_key="test_key")


class TestGLMClient:
    """GLMClient 测试类"""

    def test_init_with_api_key(self):
        """测试使用API Key初始化"""
        client = GLMClient(api_key="test_key")
        assert client.api_key == "test_key"
        assert client.model == "glm-4-flash"

    def test_init_from_env(self):
        """测试从环境变量初始化"""
        with patch.dict("os.environ", {"GLM_API_KEY": "env_key"}):
            client = GLMClient()
            assert client.api_key == "env_key"

    def test_init_missing_api_key(self):
        """测试API Key缺失时抛出异常"""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError):
                GLMClient()

    def test_get_token_usage(self, glm_client):
        """测试获取Token使用统计"""
        usage = glm_client.get_token_usage()

        assert isinstance(usage, dict)
        assert "input" in usage
        assert "output" in usage
        assert "total" in usage

    @patch("src.api.glm_client.requests.post")
    def test_call_api_success(self, mock_post, glm_client):
        """测试API调用成功"""
        # Mock HTTP响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '["昵称1", "昵称2"]'}}],
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

        # 调用API
        result = glm_client.generate("生成昵称")

        assert result["error"] is None
        assert '["昵称1", "昵称2"]' in result["content"]
        assert result["tokens"]["input"] == 100
        assert result["tokens"]["output"] == 50

    @patch("src.api.glm_client.requests.post")
    def test_call_api_network_error(self, mock_post, glm_client):
        """测试网络错误"""
        mock_post.side_effect = Exception("网络连接失败")

        result = glm_client.generate("生成昵称")

        assert result["error"] is not None
        assert result["content"] is None

    @patch("src.api.glm_client.requests.post")
    def test_call_api_retry_logic(self, mock_post, glm_client):
        """测试重试机制"""
        # 前两次失败，第三次成功
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '["昵称"]'}}],
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

        mock_post.side_effect = [
            Exception("First failure"),
            Exception("Second failure"),
            mock_response,
        ]

        with patch("src.api.glm_client.time.sleep"):
            result = glm_client.generate("生成昵称")

        # 应该最终成功
        assert result["error"] is None
        assert result["content"] == '["昵称"]'
        # 应该被调用了3次
        assert mock_post.call_count == 3

    @patch("src.api.glm_client.requests.post")
    def test_call_api_malformed_response(self, mock_post, glm_client):
        """测试畸形API响应"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [],  # 空的choices
        }
        mock_response.text = json.dumps(mock_response.json.return_value)
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        result = glm_client.generate("生成昵称")

        assert result["error"] is not None
        assert result["content"] is None

    def test_token_usage_accumulation(self):
        """测试Token使用累计"""
        with patch.dict("os.environ", {"GLM_API_KEY": "test_key"}):
            client = GLMClient()

        # 手动增加Token
        client.token_usage["input"] = 100
        client.token_usage["output"] = 50
        client.token_usage["total"] = 150

        usage = client.get_token_usage()
        assert usage["input"] == 100
        assert usage["output"] == 50
        assert usage["total"] == 150

    @patch("src.api.glm_client.requests.post")
    def test_call_api_with_params(self, mock_post, glm_client):
        """测试带参数的API调用"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '["昵称"]'}}],
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

        result = glm_client.generate(
            "生成昵称",
            temperature=0.9,
            top_p=0.95,
            max_tokens=4096,
        )

        assert result["error"] is None

        # 验证请求参数
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        assert payload["temperature"] == 0.9
        assert payload["top_p"] == 0.95
        assert payload["max_tokens"] == 4096
