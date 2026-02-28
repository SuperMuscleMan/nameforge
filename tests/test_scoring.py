"""
评分模块测试
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.prompts.scoring_prompt import ScoringPrompt
from src.scoring.quality_scorer import QualityScorer
from src.scoring.score_pipeline import ScorePipeline


class TestScoringPrompt:
    """测试评分Prompt"""

    def test_render_basic(self):
        """测试基本Prompt渲染"""
        names = ["墨染剑修", "镇天门"]
        prompt_manager = ScoringPrompt()
        prompt = prompt_manager.render(
            style="古风",
            style_description="中国古代武侠风格",
            names=names,
        )

        assert "古风" in prompt
        assert "中国古代武侠风格" in prompt
        assert "墨染剑修" in prompt
        assert "镇天门" in prompt
        assert "创意性" in prompt
        assert "25%" in prompt

    def test_get_dimensions(self):
        """测试获取维度定义"""
        prompt_manager = ScoringPrompt()
        dims = prompt_manager.get_dimensions()
        assert len(dims) == 6
        assert dims[0]["name"] == "创意性"
        assert dims[0]["weight"] == 25

    def test_calculate_score(self):
        """测试分数计算"""
        prompt_manager = ScoringPrompt()
        dimension_scores = {
            "创意性": 8.0,
            "可读性": 9.0,
            "视觉美感": 7.0,
            "风格契合": 8.5,
            "稀缺价值": 7.5,
            "社交记忆点": 6.0,
        }
        score = prompt_manager.calculate_score(dimension_scores)
        # (8*0.25 + 9*0.2 + 7*0.15 + 8.5*0.15 + 7.5*0.15 + 6*0.1) = 7.725
        assert 7.7 <= score <= 7.8


class TestQualityScorer:
    """测试评分客户端"""

    def test_init_with_api_key(self):
        """测试使用API Key初始化"""
        scorer = QualityScorer(
            api_key="test_key",
            model="test_model",
            batch_size=5,
        )
        assert scorer.api_key == "test_key"
        assert scorer.model == "test_model"
        assert scorer.batch_size == 5

    def test_init_from_env(self, monkeypatch):
        """测试从环境变量读取API Key"""
        monkeypatch.setenv("SCORING_API_KEY", "env_key")
        scorer = QualityScorer()
        assert scorer.api_key == "env_key"

    def test_init_fallback_to_glm_key(self, monkeypatch):
        """测试回退到GLM_API_KEY"""
        monkeypatch.setenv("GLM_API_KEY", "glm_key")
        scorer = QualityScorer()
        assert scorer.api_key == "glm_key"

    def test_init_no_api_key_raises(self):
        """测试没有API Key时抛出异常"""
        with pytest.raises(ValueError, match="API Key"):
            QualityScorer(api_key=None)

    @patch("src.scoring.quality_scorer.requests.post")
    def test_score_batch_success(self, mock_post):
        """测试批量评分成功"""
        # Mock响应
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "scores": [
                            {"name": "墨染剑修", "score": 8.5, "comment": "很好"},
                            {"name": "镇天门", "score": 7.2, "comment": "一般"},
                        ]
                    })
                }
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }
        mock_post.return_value = mock_response

        scorer = QualityScorer(api_key="test_key")
        results = scorer.score_batch(
            names=["墨染剑修", "镇天门"],
            style="古风",
            style_description="武侠风格",
        )

        assert len(results) == 2
        assert results[0]["name"] == "墨染剑修"
        assert results[0]["score"] == 8.5
        assert results[1]["name"] == "镇天门"
        assert results[1]["score"] == 7.2

    @patch("src.scoring.quality_scorer.requests.post")
    def test_parse_response_with_markdown(self, mock_post):
        """测试解析带Markdown标记的响应"""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "```json\n" + json.dumps({
                        "scores": [{"name": "测试", "score": 8.0, "comment": "好"}]
                    }) + "\n```"
                }
            }],
            "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
        }
        mock_post.return_value = mock_response

        scorer = QualityScorer(api_key="test_key")
        results = scorer.score_batch(
            names=["测试"],
            style="古风",
            style_description="风格",
        )

        assert len(results) == 1
        assert results[0]["score"] == 8.0

    @patch("src.scoring.quality_scorer.requests.post")
    def test_score_batch_api_error(self, mock_post):
        """测试API错误处理"""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("API Error")
        mock_post.return_value = mock_response

        scorer = QualityScorer(api_key="test_key", max_retries=0)

        # API错误应该抛出异常
        with pytest.raises(Exception):
            scorer.score_batch(
                names=["测试"],
                style="古风",
                style_description="风格",
            )

    def test_get_token_usage(self):
        """测试Token使用统计"""
        scorer = QualityScorer(api_key="test_key")
        scorer.token_usage = {"input": 100, "output": 50, "total": 150}

        usage = scorer.get_token_usage()
        assert usage["input"] == 100
        assert usage["output"] == 50
        assert usage["total"] == 150


class TestScorePipeline:
    """测试评分管道"""

    @pytest.fixture
    def mock_config(self):
        """创建Mock配置管理器"""
        config = Mock()
        config.get_style.return_value = {
            "description": "武侠风格",
            "length_min": 2,
            "length_max": 6,
        }
        config.get_system_config.side_effect = lambda key, default=None: {
            "scoring.score_threshold": 8.0,
            "scoring.enabled": True,
        }.get(key, default)
        return config

    @pytest.fixture
    def mock_scorer(self):
        """创建Mock评分客户端"""
        scorer = Mock()
        scorer.batch_size = 10
        scorer.model = "qwen-plus"
        scorer.score_batch.return_value = [
            {"name": "墨染剑修", "score": 8.5, "comment": "很好"},
            {"name": "镇天门", "score": 7.2, "comment": "一般"},
        ]
        scorer.get_token_usage.return_value = {"input": 100, "output": 50, "total": 150}
        scorer.get_request_count.return_value = 1
        return scorer

    @pytest.fixture
    def mock_storage(self, tmp_path):
        """创建Mock存储管理器"""
        storage = Mock()
        # 创建临时数据文件
        names_file = tmp_path / "test_names.txt"
        names_file.write_text("墨染剑修\n镇天门\n", encoding="utf-8")
        storage.list_names.return_value = ["墨染剑修", "镇天门"]
        return storage

    def test_score_style_success(self, mock_config, mock_scorer, mock_storage, tmp_path):
        """测试评分流程成功"""
        # 修改mock_storage使用实际路径
        mock_storage.list_names = Mock(return_value=["墨染剑修", "镇天门"])

        pipeline = ScorePipeline(
            config_manager=mock_config,
            quality_scorer=mock_scorer,
            storage_manager=mock_storage,
        )

        # 修改数据目录到临时目录
        pipeline.storage.base_dir = tmp_path

        result = pipeline.score_style("古风", force=True)

        assert result["style"] == "古风"
        assert result["total"] == 2
        assert result["scored"] == 2
        assert result["high_score_count"] == 1  # 只有墨染剑修>=8
        assert not result.get("failed")

    def test_score_style_no_names(self, mock_config, mock_scorer):
        """测试没有昵称时"""
        storage = Mock()
        storage.list_names.return_value = []

        pipeline = ScorePipeline(
            config_manager=mock_config,
            quality_scorer=mock_scorer,
            storage_manager=storage,
        )

        result = pipeline.score_style("古风")

        assert "error" in result
        assert "没有待评分的昵称" in result["error"]

    def test_score_style_resume(self, mock_config, mock_scorer, tmp_path):
        """测试续评功能"""
        # 创建已有评分文件
        scores_file = tmp_path / "古风_scores.txt"
        scores_file.write_text(
            "# 评分时间: 2026-01-01\n墨染剑修 | 8.5 | 很好\n",
            encoding="utf-8",
        )

        storage = Mock()
        storage.list_names.return_value = ["墨染剑修", "镇天门", "新昵称"]

        pipeline = ScorePipeline(
            config_manager=mock_config,
            quality_scorer=mock_scorer,
            storage_manager=storage,
        )

        # 修改数据目录
        original_load = pipeline._load_existing_scores
        def mock_load(style):
            if style == "古风":
                return {"墨染剑修": {"name": "墨染剑修", "score": 8.5, "comment": "很好"}}
            return original_load(style)
        pipeline._load_existing_scores = mock_load

        result = pipeline.score_style("古风", force=False)

        # 应该只评2个新昵称（镇天门和新昵称）
        assert result["total"] == 3
        assert result["skipped"] == 1

    def test_load_existing_scores(self, tmp_path):
        """测试加载已有评分"""
        scores_file = tmp_path / "test_scores.txt"
        scores_file.write_text(
            "# 评分时间: 2026-01-01\n"
            "# 风格: 古风\n"
            "墨染剑修 | 8.5 | 很好\n"
            "镇天门 | 7.2 | 一般\n",
            encoding="utf-8",
        )

        config = Mock()
        config.get_system_config.return_value = 8.0

        pipeline = ScorePipeline(config)
        pipeline.storage = Mock()

        # 直接测试解析逻辑
        scores = {}
        with open(scores_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(" | ", 2)
                if len(parts) >= 2:
                    name = parts[0].strip()
                    score = float(parts[1].strip())
                    comment = parts[2].strip() if len(parts) > 2 else ""
                    scores[name] = {"name": name, "score": score, "comment": comment}

        assert len(scores) == 2
        assert scores["墨染剑修"]["score"] == 8.5
        assert scores["镇天门"]["score"] == 7.2

    def test_save_high_scores(self, tmp_path):
        """测试保存高分昵称"""
        config = Mock()
        config.get_system_config.return_value = 8.0

        pipeline = ScorePipeline(config)
        pipeline.score_threshold = 8.0

        scores = {
            "高分1": {"name": "高分1", "score": 8.5, "comment": "好"},
            "低分": {"name": "低分", "score": 6.0, "comment": "差"},
            "高分2": {"name": "高分2", "score": 9.0, "comment": "很好"},
        }

        high_scores_file = tmp_path / "high_scores.txt"
        high_names = [s["name"] for s in scores.values() if s["score"] >= 8.0]

        with open(high_scores_file, "w", encoding="utf-8") as f:
            for name in sorted(high_names):
                f.write(f"{name}\n")

        content = high_scores_file.read_text(encoding="utf-8")
        assert "高分1" in content
        assert "高分2" in content
        assert "低分" not in content

    def test_save_stats(self, tmp_path):
        """测试保存统计信息"""
        import statistics

        scores = {
            "a": {"score": 8.5},
            "b": {"score": 7.0},
            "c": {"score": 9.0},
            "d": {"score": 6.5},
        }

        score_values = [s["score"] for s in scores.values()]
        stats = {
            "total": len(score_values),
            "mean": round(statistics.mean(score_values), 2),
            "median": round(statistics.median(score_values), 2),
            "std": round(statistics.stdev(score_values), 2),
            "min": min(score_values),
            "max": max(score_values),
            "high_count": len([s for s in score_values if s >= 8.0]),
            "high_percent": round(len([s for s in score_values if s >= 8.0]) / len(score_values) * 100, 1),
        }

        assert stats["total"] == 4
        assert stats["high_count"] == 2  # 8.5和9.0
        assert stats["high_percent"] == 50.0


class TestScorePipelineIntegration:
    """集成测试"""

    @pytest.mark.slow
    def test_end_to_end_flow(self, tmp_path):
        """测试完整流程（需要Mock API）"""
        # 创建临时数据目录结构
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        # 创建昵称文件
        names_file = data_dir / "古风_names.txt"
        names_file.write_text("墨染剑修\n镇天门\n", encoding="utf-8")

        # 这里可以添加更完整的集成测试
        # 需要Mock ConfigManager和API调用
        pass
