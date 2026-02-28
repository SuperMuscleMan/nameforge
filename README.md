# NameForge

🎮 **AI驱动的游戏昵称生成器** —— 用极低的API成本生成海量高质量游戏昵称

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## 项目简介

NameForge 是一个基于大语言模型的CLI昵称生成工具，采用创新的**词根模板组合方案**（AI生成词根 + 离线模板组合），仅需3-9次API调用即可生成50万+独特昵称，完美解决传统方案API成本高、重复率不可控的问题。

## 核心特性

- 🚀 **高效低成本**：3-9次API调用 → 50万+昵称（传统方案需数千次）
- 🎨 **9种内置风格**：古风、二次元、赛博朋克、史诗魔幻、暗黑亡灵、东方武侠、机械科幻、萌趣奇幻、热血竞技
- 🧩 **词根模板系统**：AI生成高质量词根，通过模板离线组合，保证语义通顺
- ⭐ **昵称质量评分**：6维度加权评分，自动筛选高分昵称（≥8分）
- ✅ **智能过滤**：长度检查、重复字过滤、禁用组合检测
- 🔄 **自动去重**：对比已有昵称，避免重复
- ⚙️ **高度可配置**：YAML配置支持自定义风格、词根类别、组合规则、Prompt模板

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置API密钥

```bash
export GLM_API_KEY='your_api_key'
```

### 生成昵称

```bash
# 使用默认配置生成
python src/main.py

# 指定风格和数量
python src/main.py --style 古风 --count 100

# 重新生成词根（词根质量不佳时使用）
python src/main.py --regenerate-roots --style 古风
```

### 评分昵称

```bash
# 评分指定风格
python src/main.py --score --style 古风

# 评分所有风格
python src/main.py --score-all

# 强制重新评分（覆盖已有评分）
python src/main.py --score --style 古风 --force
```

**评分输出文件**：
- `data/{style}_scores.txt` - 全部评分结果（昵称 | 分数 | 评语）
- `data/{style}_high_scores.txt` - 高分昵称列表（≥8.0分）
- `data/{style}_score_stats.txt` - 统计信息（平均分、中位数、高分占比等）

### 无需API密钥运行Demo

```bash
python demo.py
```

## 项目架构

```
src/
├── api/              # GLMClient - API客户端（指数退避重试）
├── config/           # ConfigManager - YAML配置热重载
├── generator/        # NicknameGenerator - 词根模板组合生成
├── pipeline/         # GenerationPipeline - 完整生成流程
├── prompts/          # PromptManager - Jinja2模板渲染
│   └── scoring_prompt.py  # 评分Prompt管理
├── roots/            # WordRootManager - 词根生成与存储
├── scoring/          # 质量评分模块
│   ├── quality_scorer.py   # 评分客户端
│   └── score_pipeline.py   # 评分流程管道
└── storage/          # StorageManager - 文件持久化
```

## 配置说明

### 风格配置 (`config/styles.yaml`)

```yaml
# 定义词根类别
word_roots:
  categories:
    古风:
      - name: "意象"
        description: "自然意象词"
        examples: ["云", "月", "风", "雪"]

# 定义组合模板
templates:
  古风:
    - "{意象}{建筑}"      # 云轩、月阁
    - "{意象}之{意象}"    # 云之月

# 定义过滤规则
filters:
  forbid_duplicate_chars: true
```

### Prompt配置 (`config/prompts.yaml`)

```yaml
prompts:
  # 词根生成Prompt
  word_root_generation:
    system_role: "专业的游戏昵称设计专家"
    template: |
      请为{style_name}风格生成词根...
  
  # 评分Prompt
  scoring:
    system_role: "专业的游戏昵称质量评估专家"
    template: |
      请对以下【{style}】风格的昵称进行质量评分...
    dimensions:
      - name: 创意性
        weight: 25
        description: 脑洞大小、独特性、避雷雷同
      # ... 其他维度
```

### 评分配置 (`config/config.yaml`)

```yaml
# 评分专用API配置（与生成API独立）
api:
  scoring:
    provider: glm
    api_key: ${SCORING_API_KEY}
    model: qwen-plus
    batch_size: 10  # 批量评分数量

# 评分配置
scoring:
  enabled: true
  score_threshold: 8.0  # 高分阈值
```

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_integration.py -v
pytest tests/test_scoring.py -v
```

## 生成示例

| 风格 | 示例昵称 |
|------|---------|
| 古风 | 若尘镇星(9.6)、锢灵鹿角(9.5)、苍筤引雷(9.4) |
| 二次元 | 软萌草莓酱、星空姬、猫咪喵 |
| 赛博朋克 | Cyber-Shadow、Neo_Void |
| 史诗魔幻 | 巨龙兽人、圣剑要塞、魔晶城堡 |
| 暗黑亡灵 | 亡灵吸血、冥河骷髅、暗影幽灵 |
| 东方武侠 | 刺客暴击、剑意盟主、烽烟游侠 |
| 机械科幻 | 机甲-X、能量护盾、无人机_激光 |
| 萌趣奇幻 | 软萌小史莱姆、小兽人酱、泡泡啾 |
| 热血竞技 | 攻城王者、暴击冲锋、战神无双 |

**评分示例**（古风风格，340个昵称）：
- 平均分：8.12
- 高分（≥8.0）：197个（57.9%）
- 最高分：9.6（若尘镇星）

## 技术亮点

- **模块化管道架构**：配置管理 → 词根生成 → 模板组合 → 过滤去重 → 存储
- **企业级特性**：配置热重载、指数退避重试、Mock测试、日志轮转
- **V2词根模板方案**：解决LLM上下文限制和重复生成问题
- **质量评分系统**：6维度加权评分，支持批量评分和续评
- **中断保护**：评分支持Ctrl+C中断，已评分结果实时保存
- **可配置Prompt**：所有Prompt模板支持YAML配置自定义

## 项目阶段

- ✅ **Phase 1**：配置管理、API客户端、文件存储、测试
- ✅ **Phase 2**：词根模板生成、昵称生成器、去重机制
- ✅ **Phase 2.5**：质量评分系统、Prompt配置化
- 🚧 **Phase 3**：Redis去重、敏感词过滤、任务调度（计划中）
- 📋 **Phase 4**：质量验证、监控、生产部署（计划中）

## 许可证

MIT License
