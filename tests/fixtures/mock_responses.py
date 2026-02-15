"""
Mock响应和测试数据
"""

# Mock GLM API 响应
MOCK_GLM_RESPONSE_SUCCESS = {
    "content": '["雪月风", "林溪烟", "竹海清音", "古月长庚", "诗意烟雨"]',
    "tokens": {"input": 100, "output": 50, "total": 150},
    "error": None,
}

MOCK_GLM_RESPONSE_INVALID_JSON = {
    "content": "这不是有效的JSON [不符合格式",
    "tokens": {"input": 100, "output": 50, "total": 150},
    "error": None,
}

MOCK_GLM_RESPONSE_ERROR = {
    "content": None,
    "tokens": {"input": 0, "output": 0, "total": 0},
    "error": "API调用失败: 网络错误",
}

# 测试用的配置文件内容
TEST_CONFIG_YAML = """
system:
  log_level: DEBUG
  log_file: logs/test.log

api:
  provider: glm
  timeout: 30
  max_retries: 3
"""

TEST_STYLES_YAML = """
prompts:
  default_template: |
    生成{count}个{charset}的{style_description}昵称
    长度{min_len}-{max_len}字符
    避免重复：{recent_names}

styles:
  测试风格:
    description: "测试用的风格"
    length_min: 2
    length_max: 6
    charset: "中文"
    enabled: true
"""

# 有效的昵称列表
VALID_NAMES = ["雪月风", "林溪烟", "竹海清音", "古月长庚", "诗意烟雨"]

# 示例样式配置
TEST_STYLE_CONFIG = {
    "description": "古代诗词文化风格",
    "length_min": 2,
    "length_max": 6,
    "charset": "中文",
    "prompt_template": "古风",
    "enabled": True,
}
