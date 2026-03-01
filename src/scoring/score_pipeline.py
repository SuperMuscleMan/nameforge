"""
评分流程管道
协调整个评分流程：读取昵称、批量评分、输出结果
"""

import logging
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple

from src.config.config_manager import ConfigManager
from src.scoring.quality_scorer import QualityScorer
from src.storage.storage_manager import StorageManager

logger = logging.getLogger("rand_names")


class ScorePipeline:
    """评分流程管道"""

    def __init__(
        self,
        config_manager: ConfigManager,
        quality_scorer: Optional[QualityScorer] = None,
        storage_manager: Optional[StorageManager] = None,
    ):
        """
        初始化评分管道

        Args:
            config_manager: 配置管理器
            quality_scorer: 评分客户端（如为None则自动创建）
            storage_manager: 存储管理器（如为None则自动创建）
        """
        self.config_manager = config_manager
        self.quality_scorer = quality_scorer or QualityScorer(config_manager)
        self.storage = storage_manager or StorageManager(base_dir="data")

        # 读取评分配置
        self.score_threshold = config_manager.get_system_config("scoring.score_threshold", 8.0)

        logger.info("ScorePipeline 已初始化")

    def score_style(
        self,
        style_name: str,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        为指定风格的所有昵称进行评分

        Args:
            style_name: 风格名称
            force: 是否强制重新评分（覆盖已有评分）

        Returns:
            评分结果统计
        """
        logger.info(f"[{style_name}] 开始评分流程")

        # 1. 获取风格配置
        style_config = self.config_manager.get_style(style_name)
        if not style_config:
            logger.error(f"[{style_name}] 风格不存在")
            return {"error": f"风格 {style_name} 不存在", "scored": 0}

        style_description = style_config.get("description", "")

        # 2. 读取所有昵称
        all_names = self.storage.list_names(style_name, limit=-1)
        if not all_names:
            logger.warning(f"[{style_name}] 没有待评分的昵称")
            return {"error": "没有待评分的昵称", "scored": 0}

        logger.info(f"[{style_name}] 共有 {len(all_names)} 个昵称")

        # 3. 确定待评分昵称
        if force:
            # 强制重新评分：全部重新评分
            names_to_score = all_names
            existing_scores = {}
            logger.info(f"[{style_name}] 强制重新评分模式")
        else:
            # 续评模式：只评新增的
            existing_scores = self._load_existing_scores(style_name)
            names_to_score = [name for name in all_names if name not in existing_scores]
            logger.info(f"[{style_name}] 已评分 {len(existing_scores)} 个，待评分 {len(names_to_score)} 个")

        if not names_to_score:
            logger.info(f"[{style_name}] 没有需要新评分的昵称")
            return {
                "style": style_name,
                "total": len(all_names),
                "scored": 0,
                "skipped": len(all_names),
                "high_score_count": len([s for s in existing_scores.values() if s >= self.score_threshold]),
            }

        # 4. 批量评分（每批次实时保存）
        batch_size = self.quality_scorer.batch_size
        total_batches = (len(names_to_score) + batch_size - 1) // batch_size

        new_scores = {}  # name -> score_info
        failed = False
        interrupted = False

        try:
            for i in range(0, len(names_to_score), batch_size):
                batch = names_to_score[i:i + batch_size]
                batch_num = i // batch_size + 1

                logger.info(f"[{style_name}] 评分批次 {batch_num}/{total_batches}，数量: {len(batch)}")

                try:
                    results = self.quality_scorer.score_batch(
                        names=batch,
                        style=style_name,
                        style_description=style_description,
                    )

                    # 记录评分结果
                    batch_count = 0
                    for result in results:
                        name = result.get("name", "")
                        if name:
                            new_scores[name] = result
                            batch_count += 1

                    logger.info(f"[{style_name}] 批次 {batch_num} 完成，评分 {batch_count} 个")

                    # 实时保存：每批次完成后立即保存（方案2）
                    if new_scores:
                        current_all_scores = {**existing_scores, **new_scores}
                        self._save_scores(style_name, current_all_scores, force=force)
                        self._save_high_scores(style_name, current_all_scores)
                        # 统计文件最后生成，不在这里更新

                except Exception as e:
                    logger.error(f"[{style_name}] 批次 {batch_num} 评分失败: {e}")
                    failed = True
                    break

        except KeyboardInterrupt:
            logger.warning(f"[{style_name}] 用户中断评分")
            interrupted = True

        # 5. 合并评分结果
        all_scores = {**existing_scores, **new_scores}

        # 6. 最终保存统计信息
        if new_scores:
            self._save_stats(style_name, all_scores)

        # 7. 返回统计
        stats = {
            "style": style_name,
            "total": len(all_names),
            "scored": len(new_scores),
            "skipped": len(existing_scores) if not force else 0,
            "failed": failed,
            "interrupted": interrupted,
            "high_score_count": len([s for s in all_scores.values() if s.get("score", 0) >= self.score_threshold]),
        }

        if interrupted:
            stats["error"] = "用户中断评分，已保存已评分结果"
        elif failed:
            stats["error"] = "评分过程中断，部分结果已保存"

        logger.info(f"[{style_name}] 评分流程完成: {stats}")
        return stats

    def score_all_styles(
        self,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        为所有风格评分（顺序串行）

        Args:
            force: 是否强制重新评分

        Returns:
            各风格的评分结果
        """
        styles = self.config_manager.list_styles()
        if not styles:
            logger.warning("没有配置任何风格")
            return {"error": "没有配置任何风格"}

        logger.info(f"开始为 {len(styles)} 个风格评分: {styles}")

        results = {}
        for style_name in styles:
            try:
                result = self.score_style(style_name, force=force)
                results[style_name] = result

                if result.get("failed"):
                    logger.error(f"[{style_name}] 评分失败，停止后续风格评分")
                    break

            except Exception as e:
                logger.error(f"[{style_name}] 评分异常: {e}")
                results[style_name] = {"error": str(e)}
                break

        # 汇总统计
        total_scored = sum(r.get("scored", 0) for r in results.values())
        total_high = sum(r.get("high_score_count", 0) for r in results.values())

        logger.info(f"全部风格评分完成: 共评分 {total_scored} 个，高分 {total_high} 个")

        return {
            "styles": results,
            "total_scored": total_scored,
            "total_high_score": total_high,
        }

    def _load_existing_scores(self, style_name: str) -> Dict[str, Dict[str, Any]]:
        """
        加载已有评分结果

        Args:
            style_name: 风格名称

        Returns:
            name -> score_info 的字典
        """
        scores_file = Path(f"data/{style_name}_scores.txt")
        if not scores_file.exists():
            return {}

        scores = {}
        try:
            with open(scores_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # 跳过注释和空行
                    if not line or line.startswith("#"):
                        continue

                    # 解析格式: 昵称 | 分数
                    parts = line.split(" | ", 1)
                    if len(parts) >= 2:
                        name = parts[0].strip()
                        try:
                            score = float(parts[1].strip())
                        except ValueError:
                            continue

                        scores[name] = {
                            "name": name,
                            "score": score,
                            "comment": "",
                        }

            logger.debug(f"[{style_name}] 已加载 {len(scores)} 条已有评分")
        except Exception as e:
            logger.warning(f"[{style_name}] 加载已有评分失败: {e}")

        return scores

    def _save_scores(
        self,
        style_name: str,
        scores: Dict[str, Dict[str, Any]],
        force: bool = False,
    ) -> None:
        """
        保存评分结果到文件

        Args:
            style_name: 风格名称
            scores: 评分结果字典
            force: 是否覆盖已有文件
        """
        scores_file = Path(f"data/{style_name}_scores.txt")

        try:
            with open(scores_file, "w", encoding="utf-8") as f:
                # 写入头部信息
                f.write(f"# 评分时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 风格: {style_name}\n")
                f.write(f"# 评分模型: {self.quality_scorer.model}\n")
                f.write(f"# 总数量: {len(scores)}\n")
                f.write("#\n")

                # 按分数降序写入（格式：昵称 | 分数）
                sorted_scores = sorted(scores.values(), key=lambda x: x.get("score", 0), reverse=True)
                for item in sorted_scores:
                    name = item.get("name", "")
                    score = item.get("score", 0.0)
                    f.write(f"{name} | {score:.1f}\n")

            logger.info(f"[{style_name}] 评分结果已保存到 {scores_file}")
        except Exception as e:
            logger.error(f"[{style_name}] 保存评分结果失败: {e}")
            raise

    def _save_high_scores(
        self,
        style_name: str,
        scores: Dict[str, Dict[str, Any]],
    ) -> None:
        """
        保存高分昵称（只存昵称）

        Args:
            style_name: 风格名称
            scores: 评分结果字典
        """
        high_scores_file = Path(f"data/{style_name}_high_scores.txt")

        try:
            # 筛选高分昵称
            high_names = [
                item.get("name", "")
                for item in scores.values()
                if item.get("score", 0) >= self.score_threshold
            ]

            with open(high_scores_file, "w", encoding="utf-8") as f:
                for name in sorted(high_names):
                    f.write(f"{name}\n")

            logger.info(f"[{style_name}] 高分昵称({len(high_names)}个)已保存到 {high_scores_file}")
        except Exception as e:
            logger.error(f"[{style_name}] 保存高分昵称失败: {e}")
            raise

    def _save_stats(
        self,
        style_name: str,
        scores: Dict[str, Dict[str, Any]],
    ) -> None:
        """
        保存评分统计信息

        Args:
            style_name: 风格名称
            scores: 评分结果字典
        """
        stats_file = Path(f"data/{style_name}_score_stats.txt")

        try:
            score_values = [item.get("score", 0) for item in scores.values()]

            if not score_values:
                stats = {
                    "total": 0,
                    "mean": 0.0,
                    "median": 0.0,
                    "std": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "high_count": 0,
                    "high_percent": 0.0,
                }
            else:
                high_count = len([s for s in score_values if s >= self.score_threshold])
                stats = {
                    "total": len(score_values),
                    "mean": round(statistics.mean(score_values), 2),
                    "median": round(statistics.median(score_values), 2),
                    "std": round(statistics.stdev(score_values), 2) if len(score_values) > 1 else 0.0,
                    "min": round(min(score_values), 1),
                    "max": round(max(score_values), 1),
                    "high_count": high_count,
                    "high_percent": round(high_count / len(score_values) * 100, 1),
                }

            with open(stats_file, "w", encoding="utf-8") as f:
                f.write(f"评分时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"总数量: {stats['total']}\n")
                f.write(f"平均分: {stats['mean']}\n")
                f.write(f"中位数: {stats['median']}\n")
                f.write(f"标准差: {stats['std']}\n")
                f.write(f">={self.score_threshold}分数量: {stats['high_count']} ({stats['high_percent']}%)\n")
                f.write(f"最高分: {stats['max']}\n")
                f.write(f"最低分: {stats['min']}\n")

            logger.info(f"[{style_name}] 评分统计已保存到 {stats_file}")
        except Exception as e:
            logger.error(f"[{style_name}] 保存评分统计失败: {e}")
            raise

    def get_token_usage(self) -> Dict[str, int]:
        """获取Token使用统计"""
        return self.quality_scorer.get_token_usage()

    def get_request_count(self) -> int:
        """获取API调用次数"""
        return self.quality_scorer.get_request_count()
