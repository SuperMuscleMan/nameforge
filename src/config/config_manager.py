"""
配置管理系统
支持动态加载和热更新
"""

import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import threading
import logging

logger = logging.getLogger("rand_names")


class ConfigManager:
    """负责加载和管理配置文件，支持运行时动态加载"""

    def __init__(self, config_dir: str = "config"):
        """
        初始化配置管理器

        Args:
            config_dir: 配置文件目录
        """
        self.config_dir = Path(config_dir)
        self.styles = {}
        self.system_config = {}
        self.prompts = {}
        self.generation = {}
        self._last_modified = {}
        self._lock = threading.RLock()

        # 验证配置目录存在
        if not self.config_dir.exists():
            raise FileNotFoundError(f"配置目录不存在: {self.config_dir}")

        # 加载所有配置
        self.load_all()

    def load_all(self):
        """一次性加载所有配置"""
        self.load_system_config()
        self.load_styles()
        self.load_prompts()

    def load_system_config(self):
        """加载系统配置"""
        config_path = self.config_dir / "config.yaml"

        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
                # 简单的环境变量替换
                content = self._replace_env_vars(content)
                self.system_config = yaml.safe_load(content) or {}

            mtime = config_path.stat().st_mtime
            self._last_modified["system_config"] = mtime

            logger.info(f"成功加载系统配置: {config_path}")
        except Exception as e:
            logger.error(f"加载系统配置失败: {e}")
            raise

    def load_styles(self):
        """加载风格配置"""
        styles_path = self.config_dir / "styles.yaml"

        if not styles_path.exists():
            raise FileNotFoundError(f"风格配置文件不存在: {styles_path}")

        try:
            with open(styles_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            # 分别存储styles、prompts、word_roots和filters
            self.styles = data.get("styles", {})
            self.prompts = data.get("prompts", {})
            self.generation = data.get("generation", {})
            self.word_roots = data.get("word_roots", {})
            self.filters = data.get("filters", {})

            mtime = styles_path.stat().st_mtime
            self._last_modified["styles"] = mtime

            logger.info(
                f"成功加载风格配置: {styles_path}, "
                f"包含{len(self.styles)}个风格"
            )
        except Exception as e:
            logger.error(f"加载风格配置失败: {e}")
            raise

    def load_prompts(self):
        """加载Prompt配置"""
        prompts_path = self.config_dir / "prompts.yaml"

        if not prompts_path.exists():
            logger.warning(f"Prompt配置文件不存在: {prompts_path}，使用默认Prompt")
            self.prompts_config = {}
            return

        try:
            with open(prompts_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            self.prompts_config = data.get("prompts", {})

            mtime = prompts_path.stat().st_mtime
            self._last_modified["prompts"] = mtime

            logger.info(
                f"成功加载Prompt配置: {prompts_path}, "
                f"包含{len(self.prompts_config)}个Prompt模板"
            )
        except Exception as e:
            logger.error(f"加载Prompt配置失败: {e}")
            self.prompts_config = {}

    def check_and_reload(self) -> bool:
        """
        定期检查配置文件变化
        - 高效：仅检查mtime，不重复加载
        - 返回：是否有变化

        Returns:
            bool: 是否进行了重新加载
        """
        with self._lock:
            changed = False

            # 检查styles.yaml
            styles_path = self.config_dir / "styles.yaml"
            if styles_path.exists():
                current_mtime = styles_path.stat().st_mtime
                last_mtime = self._last_modified.get("styles", 0)
                if current_mtime > last_mtime:
                    logger.info("检测到styles.yaml变化，重新加载...")
                    self.load_styles()
                    changed = True

            # 检查config.yaml
            config_path = self.config_dir / "config.yaml"
            if config_path.exists():
                current_mtime = config_path.stat().st_mtime
                last_mtime = self._last_modified.get("system_config", 0)
                if current_mtime > last_mtime:
                    logger.info("检测到config.yaml变化，重新加载...")
                    self.load_system_config()
                    changed = True

            # 检查prompts.yaml
            prompts_path = self.config_dir / "prompts.yaml"
            if prompts_path.exists():
                current_mtime = prompts_path.stat().st_mtime
                last_mtime = self._last_modified.get("prompts", 0)
                if current_mtime > last_mtime:
                    logger.info("检测到prompts.yaml变化，重新加载...")
                    self.load_prompts()
                    changed = True

            return changed

    def get_style(self, style_name: str) -> Optional[Dict[str, Any]]:
        """
        获取某风格配置，自动触发reload检查

        Args:
            style_name: 风格名称

        Returns:
            风格配置字典，如果不存在则返回None
        """
        self.check_and_reload()
        return self.styles.get(style_name)

    def list_styles(self) -> list:
        """
        列出所有启用的风格

        Returns:
            风格名称列表
        """
        self.check_and_reload()
        return [
            name
            for name, config in self.styles.items()
            if config.get("enabled", True)
        ]

    def get_generation_config(self, key: str, default: Any = None) -> Any:
        """
        获取生成配置值

        Args:
            key: 配置键（支持点号分隔，如 'api.glm.api_key'）
            default: 默认值

        Returns:
            配置值
        """
        self.check_and_reload()
        keys = key.split(".")
        value = self.generation

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

        return value if value is not None else default


    def get_system_config(self, key: str, default: Any = None) -> Any:
        """
        获取系统配置值

        Args:
            key: 配置键（支持点号分隔，如 'api.glm.api_key'）
            default: 默认值

        Returns:
            配置值
        """
        self.check_and_reload()
        keys = key.split(".")
        value = self.system_config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

        return value if value is not None else default

    def get_prompt_templates(self) -> Dict[str, str]:
        """
        获取所有Prompt模板（兼容V1，从styles.yaml读取）

        Returns:
            模板字典
        """
        self.check_and_reload()
        return self.prompts

    def get_default_prompt_template(self) -> str:
        """
        获取默认Prompt模板（兼容V1，从styles.yaml读取）

        Returns:
            默认模板文本
        """
        self.check_and_reload()
        return self.prompts.get("default_template", "")

    def get_prompt_config(self, prompt_type: str, key: str = None, default: Any = None) -> Any:
        """
        获取Prompt配置（从prompts.yaml读取）

        Args:
            prompt_type: Prompt类型，如 'word_root_generation', 'scoring', 'nickname_generation'
            key: 配置键（支持点号分隔，如 'dimensions'）
            default: 默认值

        Returns:
            Prompt配置值
        """
        self.check_and_reload()

        prompt_config = self.prompts_config.get(prompt_type, {})

        if key is None:
            return prompt_config

        # 支持点号分隔的键
        keys = key.split(".")
        value = prompt_config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

        return value if value is not None else default

    def _replace_env_vars(self, content: str) -> str:
        """
        替换配置文件中的环境变量
        支持格式: ${VAR_NAME}

        Args:
            content: 配置文件内容

        Returns:
            替换后的内容
        """
        import re

        def replace_func(match):
            var_name = match.group(1)
            return os.getenv(var_name, match.group(0))

        return re.sub(r"\$\{([^}]+)\}", replace_func, content)

    def validate_style(self, style_name: str) -> bool:
        """
        验证风格配置是否有效

        Args:
            style_name: 风格名称

        Returns:
            是否有效
        """
        style = self.get_style(style_name)
        if not style:
            return False

        required_keys = ["description", "length_min", "length_max", "charset"]
        return all(key in style for key in required_keys)

    def get_word_roots_config(self) -> Dict[str, Any]:
        """
        获取词根配置

        Returns:
            词根配置字典
        """
        self.check_and_reload()
        return self.word_roots

    def get_word_root_categories(self, style_name: str) -> List[Dict[str, Any]]:
        """
        获取指定风格的词根类别配置

        优先从新结构（styles.{style_name}.categories）读取
        如果不存在，则从旧结构（word_roots.categories.{style_name}）读取

        Args:
            style_name: 风格名称

        Returns:
            词根类别列表
        """
        self.check_and_reload()

        # 优先从新结构读取
        style = self.get_style(style_name)
        if style and "categories" in style:
            return style.get("categories", [])

        # 回退到旧结构
        return self.word_roots.get("categories", {}).get(style_name, [])

    def get_word_root_templates(self, style_name: str) -> List[str]:
        """
        获取指定风格的词根组合模板

        优先从新结构（styles.{style_name}.templates）读取
        如果不存在，则从旧结构（word_roots.templates.{style_name}）读取

        Args:
            style_name: 风格名称

        Returns:
            模板列表
        """
        self.check_and_reload()

        # 优先从新结构读取
        style = self.get_style(style_name)
        if style and "templates" in style:
            return style.get("templates", [])

        # 回退到旧结构
        return self.word_roots.get("templates", {}).get(style_name, [])

    def get_filters_config(self) -> Dict[str, Any]:
        """
        获取过滤规则配置

        Returns:
            过滤规则配置字典
        """
        self.check_and_reload()
        return self.filters

    def get_style_tags(self, style_name: str) -> Dict[str, Any]:
        """
        获取指定风格的标签配置

        Args:
            style_name: 风格名称

        Returns:
            标签配置字典，包含 'available' 和 'conflicts' 键
            如果风格不存在或未配置标签，返回空配置
        """
        self.check_and_reload()
        style = self.get_style(style_name)
        if not style:
            return {"available": [], "conflicts": []}

        return style.get("tags", {"available": [], "conflicts": []})

    def get_style_filters(self, style_name: str) -> Dict[str, Any]:
        """
        获取指定风格的过滤规则

        优先从新结构（styles.{style_name}.filters）读取
        如果不存在，则从旧结构（filters.{style_name}）读取

        Args:
            style_name: 风格名称

        Returns:
            过滤规则字典
        """
        self.check_and_reload()

        # 优先从新结构读取
        style = self.get_style(style_name)
        if style and "filters" in style:
            return style.get("filters", {})

        # 回退到旧结构
        global_filters = self.filters
        style_filters = {
            "forbid_duplicate_chars": global_filters.get("forbid_duplicate_chars", True),
            "forbidden_combinations": global_filters.get("forbidden_combinations", {}).get(style_name, [])
        }
        return style_filters

