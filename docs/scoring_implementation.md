# 昵称质量评分功能实现方案

## 1. 需求概述

为已生成的昵称进行质量评分，通过调用大模型批量评分，支持续评、高分筛选等功能。

## 2. 核心设计决策

| 项目 | 决策 |
|------|------|
| 评分API | 独立配置，与生成API区分 |
| 并发控制 | 单线程串行，队列保证 |
| 批量大小 | 可配置，默认10个/批次 |
| 评分维度 | 6维度加权评分（见下文） |
| 续评策略 | 只评新增，跳过已评分昵称 |
| 失败处理 | 终止整个流程 |
| 多风格处理 | 顺序串行，单次请求只含一种风格 |

## 3. 评分维度

| 维度 | 权重 | 说明 |
|------|------|------|
| 创意性 | 25% | 脑洞大小、独特性、避雷雷同 |
| 可读性 | 20% | 易读程度、发音难易、避开生僻字 |
| 视觉美感 | 15% | 字形平衡、符号点缀的适度感 |
| 风格契合 | 15% | 与玩家人设或游戏背景的匹配度 |
| 稀缺价值 | 15% | 词汇的珍贵程度（如短词、古风词） |
| 社交记忆点 | 10% | 是否好记、是否有梗、是否有传播力 |

总分 = Σ(维度得分 × 权重)，满分10分，保留1位小数

## 4. 配置文件扩展

### 4.1 config/config.yaml 新增

```yaml
# 评分专用API配置（与生成API独立）
api:
  # 原有生成用API配置
  glm:
    api_key: ${GLM_API_KEY}
    model: qwen-flash
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
    max_tokens: 32768
    timeout: 900
    max_retries: 1
    retry_wait_base: 10
  
  # 新增评分专用API配置
  scoring:
    provider: glm
    api_key: ${SCORING_API_KEY}  # 默认回退到GLM_API_KEY
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
    model: qwen-plus
    max_tokens: 8192
    timeout: 120
    max_retries: 3
    retry_wait_base: 5
    batch_size: 10

# 评分配置
scoring:
  enabled: true
  score_threshold: 8.0  # 高分阈值
```

## 5. 输出文件格式

### 5.1 {style}_scores.txt - 全部评分结果
```
# 评分时间: 2026-02-27 10:30:00
# 风格: 古风
# 评分模型: qwen-plus
墨染剑修 | 8.5 | 创意独特，古风韵味浓厚
镇天门 | 7.2 | 防务感强，但略显直白
```

### 5.2 {style}_high_scores.txt - 高分筛选结果（>=8.0）
```
墨染剑修
霜华客
剑师令
```

### 5.3 {style}_score_stats.txt - 统计信息
```
评分时间: 2026-02-27 10:30:00
总数量: 1000
平均分: 6.8
中位数: 7.0
标准差: 1.2
>=8分数量: 150 (15.0%)
最高分: 9.2
最低分: 3.5
```

## 6. 命令行接口

```bash
# 评分指定风格
python score_names.py --style 古风

# 评分所有风格
python score_names.py --all

# 指定配置文件
python score_names.py --style 古风 --config config/config.yaml

# 强制重新评分（覆盖已有评分）
python score_names.py --style 古风 --force

# 从断点续评（默认行为）
python score_names.py --style 古风 --resume
```

## 7. 代码结构

```
src/
  scoring/
    __init__.py
    quality_scorer.py      # 评分客户端
    score_pipeline.py      # 评分流程编排
  prompts/
    scoring_prompt.py      # 评分Prompt模板
score_names.py             # 入口脚本
```

## 8. 核心类设计

### 8.1 QualityScorer
- 初始化时读取scoring专用API配置
- 复用GLMClient的队列+重试机制
- 提供`score_batch(names, style, style_desc)`方法
- 返回解析后的评分结果列表

### 8.2 ScorePipeline
- 协调整个评分流程
- 管理输入/输出文件
- 处理续评逻辑（对比names.txt和scores.txt）
- 统计信息计算和输出
- 高分筛选和输出

## 9. Prompt模板

```
你是一名专业的游戏昵称质量评估专家。请对以下【{style}】风格的昵称进行质量评分。

【风格说明】{style_description}

【评分维度与权重】
1. 创意性(25%)：脑洞大小、独特性、避雷雷同
2. 可读性(20%)：易读程度、发音难易、避开生僻字
3. 视觉美感(15%)：字形平衡、符号点缀的适度感
4. 风格契合(15%)：与玩家人设或游戏背景的匹配度
5. 稀缺价值(15%)：词汇的珍贵程度（如短词、古风词）
6. 社交记忆点(10%)：是否好记、是否有梗、是否有传播力

【评分规则】
- 总分 = 各维度得分 × 权重，满分10分
- 保留1位小数
- 同时给出简评（30字以内）

【待评分昵称】
{names_list}

【输出格式】
严格返回JSON，不要包含任何Markdown代码块：
{{
  "scores": [
    {{"name": "昵称1", "score": 8.5, "comment": "简评内容"}},
    ...
  ]
}}
```

## 10. 续评逻辑

1. 读取`{style}_names.txt`获取全部昵称列表
2. 读取`{style}_scores.txt`获取已评分昵称集合
3. 计算差集得到待评分昵称列表
4. 按batch_size分批评分
5. 追加写入scores.txt
6. 更新high_scores.txt和stats.txt

## 11. 错误处理

- API调用失败：指数退避重试（按scoring配置）
- 解析失败：记录错误日志，终止流程
- 任何批次失败：终止整个评分流程，保留已评分结果

## 12. 实现步骤

1. 更新config.yaml添加scoring配置
2. 创建src/scoring/quality_scorer.py
3. 创建src/scoring/score_pipeline.py
4. 创建src/prompts/scoring_prompt.py
5. 创建score_names.py入口脚本
6. 编写测试用例
