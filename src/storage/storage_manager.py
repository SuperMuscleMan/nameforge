"""
存储管理系统
负责昵称数据的持久化和元数据记录
"""

import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger("rand_names")


class StorageManager:
    """管理文件输出、元数据记录、备份"""

    def __init__(self, base_dir: str = "data"):
        """
        初始化存储管理器

        Args:
            base_dir: 数据存储目录
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True, parents=True)

        logger.info(f"存储管理器已初始化，数据目录: {self.base_dir.absolute()}")

    def append_names(self, style: str, names: List[str]) -> int:
        """
        追加昵称到文件 {style}_names.txt
        - 增量写入（不覆盖）
        - 每行一个昵称

        Args:
            style: 风格名称
            names: 昵称列表

        Returns:
            实际写入的行数
        """
        if not names:
            logger.warning(f"[{style}] 没有昵称需要写入")
            return 0

        file_path = self.base_dir / f"{style}_names.txt"

        try:
            with open(file_path, "a", encoding="utf-8") as f:
                for name in names:
                    f.write(name.strip() + "\n")

            logger.info(f"[{style}] 已追加 {len(names)} 条昵称到 {file_path}")
            return len(names)
        except Exception as e:
            logger.error(f"[{style}] 写入文件失败: {e}")
            raise

    def write_metadata(self, style: str, stats: Dict[str, Any], timestamp: str = None) -> None:
        """
        写入元数据到独立文件

        格式: {生成时间} | 数量 | 去重率 | 敏感词过滤率

        Args:
            style: 风格名称
            stats: 统计信息字典
            timestamp: 时间戳（如果为None，使用当前时间）
        """
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        meta_file = self.base_dir / f"{style}_metadata.txt"

        # 计算各项比率
        generated = stats.get("generated", 0)
        valid = stats.get("valid", 0)
        filtered = stats.get("filtered_sensitive", 0)
        duplicated = stats.get("duplicated", 0)

        filter_rate = filtered / generated * 100 if generated > 0 else 0
        dedup_rate = duplicated / generated * 100 if generated > 0 else 0

        meta_line = (
            f"{timestamp} | "
            f"count={valid} | "
            f"filter_rate={filter_rate:.1f}% | "
            f"dedup_rate={dedup_rate:.1f}%\n"
        )

        try:
            with open(meta_file, "a", encoding="utf-8") as f:
                f.write(meta_line)

            logger.debug(f"[{style}] 已记录元数据")
        except Exception as e:
            logger.error(f"[{style}] 记录元数据失败: {e}")

    def export(self, style: str, output_path: str) -> bool:
        """
        导出昵称到指定位置

        Args:
            style: 风格名称
            output_path: 输出文件路径

        Returns:
            是否导出成功
        """
        source = self.base_dir / f"{style}_names.txt"
        if not source.exists():
            logger.warning(f"[{style}] 源文件不存在: {source}")
            return False

        try:
            import shutil

            shutil.copy(source, output_path)
            logger.info(f"[{style}] 已导出到 {output_path}")
            return True
        except Exception as e:
            logger.error(f"[{style}] 导出失败: {e}")
            return False

    def get_count(self, style: str) -> int:
        """
        获取某风格已生成的昵称总数

        Args:
            style: 风格名称

        Returns:
            昵称总数
        """
        file_path = self.base_dir / f"{style}_names.txt"
        if not file_path.exists():
            return 0

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                count = sum(1 for _ in f)
            logger.debug(f"[{style}] 已生成 {count} 条昵称")
            return count
        except Exception as e:
            logger.error(f"[{style}] 计数失败: {e}")
            return 0

    def list_names(self, style: str, limit: int = 100) -> List[str]:
        """
        读取某风格的昵称

        Args:
            style: 风格名称
            limit: 限制数量（-1表示全部）

        Returns:
            昵称列表
        """
        file_path = self.base_dir / f"{style}_names.txt"
        if not file_path.exists():
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            names = [line.strip() for line in lines if line.strip()]

            if limit > 0:
                names = names[-limit:]  # 返回最后limit条

            return names
        except Exception as e:
            logger.error(f"[{style}] 读取昵称失败: {e}")
            return []

    def clear(self, style: str) -> bool:
        """
        清空该风格的所有昵称（谨慎使用）

        Args:
            style: 风格名称

        Returns:
            是否清空成功
        """
        file_path = self.base_dir / f"{style}_names.txt"
        if not file_path.exists():
            logger.info(f"[{style}] 文件不存在，无需清空")
            return True

        try:
            file_path.unlink()
            logger.warning(f"[{style}] 已清空所有昵称")
            return True
        except Exception as e:
            logger.error(f"[{style}] 清空失败: {e}")
            return False
