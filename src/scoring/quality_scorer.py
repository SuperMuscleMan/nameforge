"""
质量评分客户端
用于调用大模型对昵称进行批量评分
"""

import json
import logging
import os
import time
from typing import Dict, Any, List, Optional
import requests

from src.config.config_manager import ConfigManager
from src.prompts.scoring_prompt import ScoringPrompt

logger = logging.getLogger("rand_names")


class QualityScorer:
    """质量评分客户端，支持批量评分和重试机制"""

    def __init__(
        self,
        config_manager: ConfigManager = None,
        api_key: Optional[str] = None,
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        model: str = "qwen-plus",
        timeout: int = 120,
        max_retries: int = 3,
        retry_wait_base: int = 5,
        batch_size: int = 10,
    ):
        """
        初始化评分客户端

        Args:
            config_manager: 配置管理器（优先从配置读取）
            api_key: API Key（如果为None，从环境变量SCORING_API_KEY或GLM_API_KEY读取）
            base_url: API 端点地址
            model: 使用的模型名称
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            retry_wait_base: 重试等待基数（秒）
            batch_size: 批量评分数量
        """
        # 保存config_manager供后续使用
        self.config_manager = config_manager

        # 优先从config_manager读取配置
        if config_manager:
            self.api_key = (
                config_manager.get_system_config("api.scoring.api_key")
                or api_key
                or os.getenv("SCORING_API_KEY")
                or os.getenv("GLM_API_KEY")
            )
            self.model = config_manager.get_system_config("api.scoring.model") or model
            self.base_url = config_manager.get_system_config("api.scoring.base_url") or base_url
            self.timeout = config_manager.get_system_config("api.scoring.timeout", timeout)
            self.max_retries = config_manager.get_system_config("api.scoring.max_retries", max_retries)
            self.retry_wait_base = config_manager.get_system_config("api.scoring.retry_wait_base", retry_wait_base)
            self.batch_size = config_manager.get_system_config("api.scoring.batch_size", batch_size)
            self.max_tokens = config_manager.get_system_config("api.scoring.max_tokens", 8192)
        else:
            self.api_key = api_key or os.getenv("SCORING_API_KEY") or os.getenv("GLM_API_KEY")
            self.model = model
            self.base_url = base_url
            self.timeout = timeout
            self.max_retries = max_retries
            self.retry_wait_base = retry_wait_base
            self.batch_size = batch_size
            self.max_tokens = 8192

        if not self.api_key:
            raise ValueError("API Key 未设置，请设置 SCORING_API_KEY 或 GLM_API_KEY 环境变量")

        # 统计信息
        self.token_usage = {"input": 0, "output": 0, "total": 0}
        self.request_count = 0

        logger.info(f"QualityScorer 已初始化，使用模型: {self.model}, batch_size: {self.batch_size}")

    def score_batch(
        self,
        names: List[str],
        style: str,
        style_description: str,
    ) -> List[Dict[str, Any]]:
        """
        批量评分

        Args:
            names: 待评分昵称列表
            style: 风格名称
            style_description: 风格描述

        Returns:
            评分结果列表，每个元素包含name, score, comment

        Raises:
            Exception: 如果API调用或解析失败
        """
        if not names:
            return []

        # 渲染Prompt（使用配置管理器）
        prompt_manager = ScoringPrompt(self.config_manager)
        prompt = prompt_manager.render(style, style_description, names)

        # 调用API
        response = self._call_api_with_retry(prompt)

        if response.get("error"):
            raise Exception(f"API调用失败: {response['error']}")

        # 解析响应
        content = response.get("content", "")
        if not content:
            raise Exception("API返回内容为空")

        # 解析JSON
        try:
            result = self._parse_response(content, names)
            return result
        except Exception as e:
            logger.error(f"解析评分结果失败: {e}")
            logger.error(f"原始响应: {content[:1000]}")
            raise

    def _call_api_with_retry(self, prompt: str) -> Dict[str, Any]:
        """
        调用API，带指数退避重试

        Args:
            prompt: Prompt文本

        Returns:
            API响应结果
        """
        last_error = None

        for attempt in range(self.max_retries + 1):
            logger.debug(f"调用评分API (第{attempt + 1}次尝试)")
            response = self._call_api(prompt)
            self.request_count += 1

            # 检查是否成功
            if not response.get("error"):
                return response

            # 有错误，记录并准备重试
            last_error = response["error"]
            logger.warning(f"评分API调用失败 (第{attempt + 1}次): {last_error}")

            if attempt < self.max_retries:
                wait_time = self.retry_wait_base * (2 ** attempt)
                logger.info(f"将在 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                logger.error(f"已达到最大重试次数 ({self.max_retries})，放弃该请求")

        return {
            "content": None,
            "tokens": {"input": 0, "output": 0, "total": 0},
            "error": str(last_error),
        }

    def _call_api(self, prompt: str) -> Dict[str, Any]:
        """
        执行单次API调用

        Args:
            prompt: Prompt文本

        Returns:
            API响应结果
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是一名专业的游戏昵称质量评估专家。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,  # 评分需要更稳定的输出
            "top_p": 0.9,
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        response = requests.post(
            self.base_url,
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )

        # 处理HTTP错误
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            return {
                "content": None,
                "tokens": {"input": 0, "output": 0, "total": 0},
                "error": str(e),
                "status_code": getattr(response, "status_code", None),
            }

        # 解析JSON
        try:
            response_data = response.json()
        except (ValueError, json.JSONDecodeError) as e:
            return {
                "content": None,
                "tokens": {"input": 0, "output": 0, "total": 0},
                "error": f"JSON解析失败: {e}",
                "response_text": getattr(response, "text", "")[:2000],
            }

        # 检查API错误
        if "error" in response_data:
            return {
                "content": None,
                "tokens": {"input": 0, "output": 0, "total": 0},
                "error": f"API错误: {response_data['error']}",
            }

        # 提取内容
        try:
            content = response_data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            return {
                "content": None,
                "tokens": {"input": 0, "output": 0, "total": 0},
                "error": f"无法解析响应结构: {e}",
            }

        # 提取Token使用信息
        usage = response_data.get("usage", {})
        tokens = {
            "input": usage.get("prompt_tokens", 0),
            "output": usage.get("completion_tokens", 0),
            "total": usage.get("total_tokens", 0),
        }

        # 更新累计统计
        self.token_usage["input"] += tokens["input"]
        self.token_usage["output"] += tokens["output"]
        self.token_usage["total"] += tokens["total"]

        logger.debug(
            "评分API调用成功，消耗Token: input=%s, output=%s, total=%s",
            tokens["input"],
            tokens["output"],
            tokens["total"],
        )

        return {
            "content": content,
            "tokens": tokens,
            "error": None,
        }

    def _parse_response(self, content: str, expected_names: List[str]) -> List[Dict[str, Any]]:
        """
        解析API响应内容

        Args:
            content: API返回的文本内容
            expected_names: 期望评分的昵称列表（用于校验）

        Returns:
            评分结果列表

        Raises:
            Exception: 如果解析失败或结果不匹配
        """
        # 清理内容（移除可能的markdown代码块标记）
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # 解析JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise Exception(f"JSON解析失败: {e}")

        if not isinstance(data, dict) or "scores" not in data:
            raise Exception("响应格式错误，缺少'scores'字段")

        scores = data["scores"]
        if not isinstance(scores, list):
            raise Exception("'scores'字段必须是列表")

        # 校验结果
        if len(scores) != len(expected_names):
            logger.warning(f"评分结果数量不匹配: 期望{len(expected_names)}个，实际{len(scores)}个")

        # 规范化结果
        results = []
        for item in scores:
            if not isinstance(item, dict):
                continue
            name = item.get("name", "").strip()
            score = item.get("score", 0.0)
            comment = item.get("comment", "").strip()

            # 确保score是数字
            try:
                score = float(score)
            except (TypeError, ValueError):
                score = 0.0

            # 限制分数范围
            score = max(0.0, min(10.0, score))

            results.append({
                "name": name,
                "score": round(score, 1),
                "comment": comment,
            })

        return results

    def get_token_usage(self) -> Dict[str, int]:
        """获取累计Token使用统计"""
        return self.token_usage.copy()

    def get_request_count(self) -> int:
        """获取API调用次数"""
        return self.request_count
