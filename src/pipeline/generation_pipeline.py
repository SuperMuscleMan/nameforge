"""
生成管道
整合所有模块，实现完整的昵称生成流程
V2版本：集成WordRootManager和NicknameGenerator的词根模板方案
"""

import json
import logging
from typing import Dict, Any, List, Optional
from src.api.glm_client import GLMClient
from src.config.config_manager import ConfigManager
from src.prompts.prompt_manager import PromptManager
from src.storage.storage_manager import StorageManager
from src.roots.word_root_manager import WordRootManager
from src.generator.nickname_generator import NicknameGenerator
from pathlib import Path

logger = logging.getLogger("rand_names")


class GenerationPipeline:
    """完整的生成流程编排

    V2版本支持两种生成模式：
    1. V1模式：直接调用API生成昵称（保留兼容性）
    2. V2模式：词根模板方案，AI生成词根 + 离线模板组合
    """

    def __init__(
        self,
        glm_client: GLMClient,
        config_manager: ConfigManager,
        prompt_manager: PromptManager,
        storage: StorageManager,
        use_v2: bool = True,
    ):
        """
        初始化生成管道

        Args:
            glm_client: GLM API客户端
            config_manager: 配置管理器
            prompt_manager: Prompt管理器
            storage: 存储管理器
            use_v2: 是否使用V2词根模板方案
        """
        self.glm_client = glm_client
        self.config_manager = config_manager
        self.prompt_manager = prompt_manager
        self.storage = storage
        self.use_v2 = use_v2

        # V2模式：初始化词根管理器和昵称生成器
        if use_v2:
            self.root_manager = WordRootManager(glm_client, config_manager)
            self.nickname_generator = NicknameGenerator(config_manager)
            logger.info("GenerationPipeline 已初始化 (V2词根模板模式)")
        else:
            logger.info("GenerationPipeline 已初始化 (V1直接生成模式)")

    def generate_for_style(self, style_name: str, count: int = 100) -> Dict[str, Any]:
        """
        为某个风格生成昵称

        V2模式流程:
        1. 获取词根（如不存在则生成）
        2. 使用模板组合生成昵称
        3. 存储结果

        V1模式流程（保留兼容性）:
        1. 获取配置
        2. 准备Prompt
        3. 调用API
        4. 处理结果（解析 → 验证）
        5. 存储持久化

        Args:
            style_name: 风格名称
            count: 生成数量

        Returns:
            {
                'valid_names': [...],  # 有效昵称
                'invalid': [...],      # 无效昵称
                'stats': {
                    'generated': int,
                    'valid': int,
                    'invalid_format': int,
                    ...
                }
            }
        """
        if self.use_v2:
            return self._generate_v2(style_name, count)
        else:
            return self._generate_v1(style_name, count)

    def _generate_v2(self, style_name: str, count: int) -> Dict[str, Any]:
        """
        V2版本生成流程：词根模板方案

        Args:
            style_name: 风格名称
            count: 生成数量

        Returns:
            生成结果字典
        """
        logger.info(f"[{style_name}] 开始V2生成流程，目标数量: {count}")

        # 1. 获取风格配置
        style_config = self.config_manager.get_style(style_name)
        if not style_config:
            logger.error(f"[{style_name}] 风格不存在")
            return {
                "valid_names": [],
                "invalid": [],
                "stats": {"error": f"风格 {style_name} 不存在"},
            }

        # 2. 验证风格配置
        if not self.config_manager.validate_style(style_name):
            logger.error(f"[{style_name}] 风格配置无效")
            return {
                "valid_names": [],
                "invalid": [],
                "stats": {"error": f"风格 {style_name} 配置无效"},
            }

        try:
            # 3. 获取词根（如不存在则生成）
            roots = self.root_manager.get_roots(style_name)

            # 4. 获取已存在的昵称（用于去重）
            existing_names = set(self.storage.list_names(style_name, limit=-1))
            logger.debug(f"[{style_name}] 已存在 {len(existing_names)} 个昵称，将用于去重")

            # 5. 使用模板组合生成昵称
            names = self.nickname_generator.generate(style_name, roots, count, existing_names)

            # 6. 存储结果
            if names:
                self.storage.append_names(style_name, names)
                stats = {
                    "generated": len(names),
                    "valid": len(names),
                    "invalid_format": 0,
                    "mode": "v2_word_roots",
                }
                self.storage.write_metadata(style_name, stats)
            else:
                stats = {
                    "generated": 0,
                    "valid": 0,
                    "invalid_format": 0,
                    "mode": "v2_word_roots",
                }

            logger.info(
                f"[{style_name}] V2生成完成 "
                f"生成={stats['generated']}, 有效={stats['valid']}"
            )

            return {
                "valid_names": names,
                "invalid": [],
                "stats": stats,
            }

        except Exception as e:
            logger.error(f"[{style_name}] V2生成流程失败: {e}")
            return {
                "valid_names": [],
                "invalid": [],
                "stats": {"error": f"V2生成失败: {e}"},
            }

    def _generate_v1(self, style_name: str, count: int) -> Dict[str, Any]:
        """
        V1版本生成流程：直接API调用（保留兼容性）

        Args:
            style_name: 风格名称
            count: 生成数量

        Returns:
            生成结果字典
        """
        logger.info(f"[{style_name}] 开始V1生成流程，目标数量: {count}")

        # 1. 获取风格配置
        style_config = self.config_manager.get_style(style_name)
        if not style_config:
            logger.error(f"[{style_name}] 风格不存在")
            return {
                "valid_names": [],
                "invalid": [],
                "stats": {"error": f"风格 {style_name} 不存在"},
            }

        # 2. 验证风格配置
        if not self.config_manager.validate_style(style_name):
            logger.error(f"[{style_name}] 风格配置无效")
            return {
                "valid_names": [],
                "invalid": [],
                "stats": {"error": f"风格 {style_name} 配置无效"},
            }

        # 3. 获取最近生成的昵称（用于Prompt中避免重复）
        recent_names = self.storage.list_names(style_name, limit=100)

        # 4. 渲染Prompt
        try:
            prompt = self.prompt_manager.render_prompt(
                style_name=style_name,
                style_description=style_config["description"],
                min_len=style_config["length_min"],
                max_len=style_config["length_max"],
                charset=style_config["charset"],
                count=count,
                recent_names=recent_names,
            )
            logger.debug(f"[{style_name}] Prompt已渲染，长度: {len(prompt)}字符")
        except Exception as e:
            logger.error(f"[{style_name}] Prompt渲染失败: {e}")
            return {
                "valid_names": [],
                "invalid": [],
                "stats": {"error": f"Prompt渲染失败: {e}"},
            }

        # 5. 调用API
        logger.info(f"[{style_name}] 调用GLM API...")
        response = self.glm_client.generate(prompt)

        if response.get("error"):
            logger.error(f"[{style_name}] API调用失败: {response['error']}")
            return {
                "valid_names": [],
                "invalid": [],
                "stats": {"error": f"API调用失败: {response['error']}"},
            }

        # 6. 处理响应
        results = self._process_response(response, style_name, style_config)

        # 7. 存储到文件
        if results["valid_names"]:
            self.storage.append_names(style_name, results["valid_names"])
            results["stats"]["mode"] = "v1_direct_api"
            self.storage.write_metadata(style_name, results["stats"])

        # 8. 输出统计
        stats = results["stats"]
        logger.info(
            f"[{style_name}] V1本轮完成 "
            f"生成={stats['generated']}, "
            f"有效={stats['valid']}, "
            f"无效={stats['invalid_format']}"
        )

        return results

    def _process_response(
        self, response: Dict[str, Any], style_name: str, style_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        结果处理管道：解析 → 验证

        阶段1中暂不实现敏感词过滤和Redis去重

        Args:
            response: API响应
            style_name: 风格名称
            style_config: 风格配置

        Returns:
            {
                'valid_names': [...],
                'invalid': [...],
                'stats': {...}
            }
        """
        stats = {
            "generated": 0,
            "valid": 0,
            "invalid_format": 0,
        }

        # 1. 解析JSON
        try:
            content = response.get("content", "")
            if not content:
                logger.error(f"[{style_name}] API返回内容为空")
                return {"valid_names": [], "invalid": [], "stats": stats}

            # 尝试解析JSON
            names = json.loads(content)
            if not isinstance(names, list):
                names = [names]

            logger.debug(f"[{style_name}] 成功解析JSON，包含{len(names)}条昵称")
        except json.JSONDecodeError as e:
            logger.error(f"[{style_name}] JSON解析失败: {e}")
            logger.debug(f"原始内容预览: {content[:200]}")

            # 将原始响应写入日志文件，便于离线排查
            try:
                logs_dir = Path("logs")
                logs_dir.mkdir(exist_ok=True)
                fname = logs_dir / f"last_api_response_{style_name}.log"
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(str(content)[:10000])
                logger.error(f"[{style_name}] 已将原始响应保存到 {fname}")
            except Exception as ex:
                logger.error(f"无法写入原始响应日志: {ex}")

            # 记录HTTP层面的metadata（如果有）
            status = response.get("status_code")
            headers = response.get("response_headers")
            if status or headers:
                logger.debug(f"[{style_name}] response status={status} headers={headers}")

            return {
                "valid_names": [],
                "invalid": [content],
                "stats": {**stats, "invalid_format": 1},
            }

        stats["generated"] = len(names)

        valid_names = []
        invalid_names = []

        # 2. 逐条验证
        for name in names:
            # 2.1 格式验证
            if not isinstance(name, str) or not name.strip():
                invalid_names.append(name)
                stats["invalid_format"] += 1
                continue

            name = name.strip()

            # 2.2 长度和字符集检验
            if not self._validate_format(name, style_config):
                invalid_names.append(name)
                stats["invalid_format"] += 1
                continue

            # 通过所有检验
            valid_names.append(name)
            stats["valid"] += 1

        logger.debug(
            f"[{style_name}] 验证完成: 有效={stats['valid']}, 无效={stats['invalid_format']}"
        )

        return {
            "valid_names": valid_names,
            "invalid": invalid_names,
            "stats": stats,
        }

    def regenerate_roots(self, style_name: str) -> Dict[str, List[str]]:
        """重新生成指定风格的词根

        Args:
            style_name: 风格名称

        Returns:
            新生成的词根字典
        """
        if not self.use_v2:
            logger.warning("V1模式不支持词根重新生成")
            return {}

        logger.info(f"[{style_name}] 开始重新生成词根...")
        roots = self.root_manager.regenerate_roots(style_name)
        logger.info(f"[{style_name}] 词根重新生成完成，共 {len(roots)} 个类别")
        return roots

    def _validate_format(self, name: str, style_config: Dict[str, Any]) -> bool:
        """
        验证昵称格式（长度和字符集）

        Args:
            name: 昵称文本
            style_config: 风格配置

        Returns:
            是否符合格式要求
        """
        # 长度检验
        min_len = style_config.get("length_min", 2)
        max_len = style_config.get("length_max", 6)

        if not (min_len <= len(name) <= max_len):
            return False

        # 字符集验证（简化版，可后续扩展）
        # charset = style_config.get('charset', '中文')
        # 当前暂不实现复杂的字符集检验

        return True
