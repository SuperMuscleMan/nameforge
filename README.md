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
- ✅ **智能过滤**：长度检查、重复字过滤、禁用组合检测
- 🔄 **自动去重**：对比已有昵称，避免重复
- ⚙️ **高度可配置**：YAML配置支持自定义风格、词根类别、组合规则

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
├── roots/            # WordRootManager - 词根生成与存储
└── storage/          # StorageManager - 文件持久化
```

## 配置说明

编辑 `config/styles.yaml` 自定义风格：

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

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_integration.py -v
```

## 生成示例

| 风格 | 示例昵称 |
|------|---------|
| 古风 | 云轩、月阁、风之雪 |
| 二次元 | 软萌草莓酱、星空姬、猫咪喵 |
| 赛博朋克 | Cyber-Shadow、Neo_Void |
| 史诗魔幻 | 巨龙兽人、圣剑要塞、魔晶城堡 |
| 暗黑亡灵 | 亡灵吸血、冥河骷髅、暗影幽灵 |
| 东方武侠 | 刺客暴击、剑意盟主、烽烟游侠 |
| 机械科幻 | 机甲-X、能量护盾、无人机_激光 |
| 萌趣奇幻 | 软萌小史莱姆、小兽人酱、泡泡啾 |
| 热血竞技 | 攻城王者、暴击冲锋、战神无双 |

## 技术亮点

- **模块化管道架构**：配置管理 → 词根生成 → 模板组合 → 过滤去重 → 存储
- **企业级特性**：配置热重载、指数退避重试、Mock测试、日志轮转
- **V2词根模板方案**：解决LLM上下文限制和重复生成问题

## 项目阶段

- ✅ **Phase 1**：配置管理、API客户端、文件存储、测试
- ✅ **Phase 2**：词根模板生成、昵称生成器、去重机制
- 🚧 **Phase 3**：Redis去重、敏感词过滤、任务调度（计划中）
- 📋 **Phase 4**：质量验证、监控、生产部署（计划中）

## 许可证

MIT License
