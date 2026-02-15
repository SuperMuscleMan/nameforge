"""
GLM API 客户端
支持串行调用、重试、Token监控
"""

import json
import logging
import os
import time
from queue import Queue
from threading import Thread
from typing import Dict, Any, Optional
import requests

from src.config.config_manager import ConfigManager

logger = logging.getLogger("rand_names")


class GLMClient:
    """GLM API 客户端，支持串行调用和重试机制"""

    def __init__(
        self,
        config_manager: ConfigManager = None,
        api_key: Optional[str] = None,
        org_id: Optional[str] = None,
        base_url: str = "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        model: str = "glm-4-flash",
        timeout: int = 30,
        max_retries: int = 3,
        retry_wait_base: int = 2,
    ):
        self.api_key=config_manager.get_system_config("api.glm.api_key")
        model=config_manager.get_system_config("api.glm.model")
        timeout=config_manager.get_system_config("api.timeout", 30)
        base_url=config_manager.get_system_config("api.glm.base_url")
        """
        初始化GLM客户端

        Args:
            api_key: API Key（如果为None，从环境变量GLM_API_KEY读取）
            org_id: 组织ID（可选）
            base_url: API 端点地址
            model: 使用的模型名称
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            retry_wait_base: 重试等待基数（秒），实际等待为 base * (2^n)
        """
        if not self.api_key:
           self.api_key = api_key or os.getenv("GLM_API_KEY")
        if not self.api_key:
            raise ValueError("API Key 未设置，请设置 GLM_API_KEY 环境变量或传入参数")

        self.org_id = org_id or os.getenv("GLM_ORG_ID")
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_wait_base = retry_wait_base

        # 队列和统计信息
        self.request_queue = Queue()
        self.token_usage = {"input": 0, "output": 0, "total": 0}
        self._stop_worker = False

        # 启动单线程处理队列
        self.worker_thread = Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()

        logger.info(f"GLMClient 已初始化，使用模型: {self.model}")

    def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        同步调用API（实际异步在后台处理）

        Args:
            prompt: Prompt文本
            **kwargs: 其他参数（如temperature等）

        Returns:
            {'content': ..., 'tokens': {...}, 'error': ...}
        """
        # 简化版：直接调用，不使用队列
        # （完整版应使用队列实现真正的串行调用）
        return self._call_api_with_retry(prompt, **kwargs)

    def _process_queue(self):
        """后台线程处理队列，保证串行调用"""
        while not self._stop_worker:
            try:
                if not self.request_queue.empty():
                    request = self.request_queue.get(timeout=1)
                    # 处理请求
                    request["future"].set_result(
                        self._call_api_with_retry(request["prompt"], **request.get("kwargs", {}))
                    )
                else:
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"队列处理异常: {e}")

    def _call_api_with_retry(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        实际API调用 + 指数退避重试

        重试策略：
        - 第1次失败：等待2秒后重试
        - 第2次失败：等待4秒后重试
        - 第3次失败：等待8秒后重试

        Args:
            prompt: Prompt文本
            **kwargs: 其他参数

        Returns:
            API响应结果
        """
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(f"调用GLM API (第{attempt + 1}次尝试)")
                response = self._call_api(prompt, **kwargs)
                return response
            except Exception as e:
                last_error = e
                logger.warning(f"GLM API 调用失败 (第{attempt + 1}次): {e}")

                # 计算等待时间（指数退避）
                if attempt < self.max_retries:
                    wait_time = self.retry_wait_base * (2 ** attempt)
                    logger.info(f"将在 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"已达到最大重试次数 ({self.max_retries})，放弃该请求")

        # 最终失败
        return {
            "content": None,
            "tokens": {"input": 0, "output": 0, "total": 0},
            "error": str(last_error),
        }

    def _call_api(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        执行单次API调用（不含重试）

        Args:
            prompt: Prompt文本
            **kwargs: 其他参数

        Returns:
            API响应结果

        Raises:
            Exception: 如果API调用失败
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if self.org_id:
            headers["openai-organization"] = self.org_id

        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": prompt},
                         {"role": "user", "content": "请根据上述要求生成高质量昵称列表。"}],
            "temperature": kwargs.get("temperature", 0.9),
            "top_p": kwargs.get("top_p", 0.9),
            "max_tokens": kwargs.get("max_tokens", 65536),
            "extra_body":[{"enable_thinking": True}]
        }

        response = requests.post(
            self.base_url,
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )

        # 尝试处理HTTP错误并记录有用的调试信息
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            logger.error(
                "HTTP error during GLM API call: %s status=%s text=%s",
                e,
                getattr(response, "status_code", None),
                getattr(response, "text", "")[:1000],
            )
            return {
                "content": None,
                "tokens": {"input": 0, "output": 0, "total": 0},
                "error": str(e),
                "status_code": getattr(response, "status_code", None),
                "response_text": getattr(response, "text", "")[:2000],
                "response_headers": dict(getattr(response, "headers", {})),
            }

        # 解析JSON，若失败则记录原始响应便于离线排查
        try:
            response_data = response.json()
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(
                "Failed to decode JSON from GLM API response: %s; status=%s; text_preview=%s",
                e,
                getattr(response, "status_code", None),
                getattr(response, "text", "")[:1000],
            )
            logger.debug("response.headers=%s payload_preview=%s", dict(getattr(response, "headers", {})), repr(payload)[:500])
            return {
                "content": None,
                "tokens": {"input": 0, "output": 0, "total": 0},
                "error": str(e),
                "status_code": getattr(response, "status_code", None),
                "response_text": getattr(response, "text", "")[:20000],
                "response_headers": dict(getattr(response, "headers", {})),
            }

        # 解析响应
        if "error" in response_data:
            raise Exception(f"API错误: {response_data['error']}")

        # 提取内容和token信息
        try:
            content = response_data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            logger.error("无法解析API响应结构: %s; response_preview=%s", e, str(response_data)[:1000])
            return {
                "content": None,
                "tokens": {"input": 0, "output": 0, "total": 0},
                "error": f"无法解析API响应: {e}",
                "status_code": getattr(response, "status_code", None),
                "response_text": str(response_data)[:2000],
                "response_headers": dict(getattr(response, "headers", {})),
            }

        # 提取Token使用信息
        usage = response_data.get("usage", {})
        tokens = {
            "input": usage.get("prompt_tokens", 0),
            "output": usage.get("completion_tokens", 0),
            "total": usage.get("total_tokens", 0),
        }

        # 更新累计Token统计
        self.token_usage["input"] += tokens["input"]
        self.token_usage["output"] += tokens["output"]
        self.token_usage["total"] += tokens["total"]

        logger.debug(
            "API 调用成功，消耗Token: input=%s, output=%s, total=%s",
            tokens["input"],
            tokens["output"],
            tokens["total"],
        )

        return {
            "content": content,
            "tokens": tokens,
            "error": None,
            "status_code": getattr(response, "status_code", None),
            "response_text_preview": getattr(response, "text", "")[:1000],
            "response_headers": dict(getattr(response, "headers", {})),
        }

    def get_token_usage(self) -> Dict[str, int]:
        """
        获取累计Token使用统计

        Returns:
            Token使用统计字典
        """
        return self.token_usage.copy()

    def stop(self):
        """停止工作线程"""
        self._stop_worker = True
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5)
