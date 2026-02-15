# 游戏昵称持续生成系统 - 完整设计文档

**版本**: 1.0  
**日期**: 2026年2月14日  
**状态**: 设计阶段  

---

## 目录

1. [项目概述](#项目概述)
2. [需求分析](#需求分析)
3. [系统架构](#系统架构)
4. [技术栈选型](#技术栈选型)
5. [核心模块设计](#核心模块设计)
6. [配置系统设计](#配置系统设计)
7. [工作流程](#工作流程)
8. [数据流与去重机制](#数据流与去重机制)
9. [质量保证](#质量保证)
10. [部署与运维](#部署与运维)
11. [扩展性](#扩展性)
12. [风险与缓解](#风险与缓解)
13. [实现时间线](#实现时间线)

---

## 项目概述

### 项目名称
游戏昵称持续生成系统 (Game Name Generator System)

### 核心目标
构建一个**自动化、持续流式的昵称生成平台**，通过LLM API（智谱GLM）生成大量独特、符合风格的游戏用户昵称，支持动态风格定义和高精度去重。

### 关键指标
- **生成规模**: 持续型，每小时生成 ~10,000 条昵称，最终积累 50+ 万条
- **去重精度**: <1% 重复率（使用Redis + 数据库双层验证）
- **可配置性**: 支持运行时动态加载配置，无需重启应用
- **API约束**: 单个免费API Key，不支持并发，需要串行调用

### 适用场景
- 游戏开发（为大量用户自动分配独特昵称）
- 用户注册系统（推荐昵称列表）
- 内容生成（小说人物名、游戏怪物名等）

---

## 需求分析

### 功能需求

#### 1. 昵称生成
- **输入**: 游戏风格（古风、二次元、赛博朋克等）的文本描述
- **处理**: 通过智谱GLM LLM API 生成符合风格的昵称
- **输出**: JSON格式的昵称列表

#### 2. 去重机制
- **精度要求**: 高精度去重 (<1% 重复）
- **实现层次**:
  - 内存层：Redis Set（快速查询 O(1)）
  - 数据库层：持久化存储，后期可扩展至PostgreSQL
  - 算法层：Prompt中注入最近生成昵称，主动避免重复

#### 3. 敏感词过滤
- **来源**: 开源敏感词库 (如 better-profanity 汉化版或中文专业库)
- **处理策略**: 过滤、替换或标记（可配置）
- **支持扩展**: 用户可在配置文件中追加自定义敏感词

#### 4. 风格管理
- **定义方式**: 自由文本描述（由LLM理解风格特征）
- **参数配置**: 长度、字符集、字符集范围等可配置
- **动态加载**: 支持运行时添加或修改风格，无需重启应用

#### 5. 持续生成
- **调度策略**: 按时间间隔触发（如每小时），调用任务调度器
- **串行处理**: 遵守单API Key无并发限制，使用队列串行调用
- **错误恢复**: 失败任务自动重试，支持中断后继续

#### 6. 持久化存储
- **热存储**: Redis （快速去重检测）
- **冷存储**: 按风格分类的文本文件 `{风格}_names.txt`
- **追踪信息**: 文件头含生成时间、去重率、敏感词过滤率等元数据

### 非功能需求

#### 性能
- API 调用响应时间 < 30s
- Redis 去重查询 < 5ms
- 单次生成 10,000 条估时 2-5 分钟（取决于API吞吐量）

#### 可靠性
- API 调用失败自动重试 (最多3次，指数退避)
- Redis 不可用时降级为内存 Set
- 应用崩溃时支持中断恢复（记录断点）

#### 可维护性
- 所有配置外部化（YAML文件）
- 支持热加载（无需重启生效）
- 清晰的日志和监控
- 代码结构模块化，职责明确

#### 扩展性
- 易于添加新风格
- 易于更换LLM厂商（API 抽象层）
- 易于替换去重存储（适配器模式）
- 易于集成更多敏感词源

---

## 系统架构

### 总体架构图

```
┌──────────────────────────────────────────────────────────┐
│                   任务调度层 (APScheduler)                  │
│                 每小时触发一次生成任务                       │
└────────────────────┬─────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│                   配置管理层                               │
│  - styles.yaml（风格定义）                                 │
│  - config.yaml（系统配置）                                 │
│  - 支持运行时动态加载                                       │
└────────────────────┬─────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│                  任务队列与编排                             │
│  - 生成任务队列                                             │
│  - 参数优化（Batch size、超时控制）                         │
└────────────────────┬─────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│              API 调用层（串行）                             │
│  - GLM Client（单线程 + 队列）                             │
│  - Prompt 注入与渲染                                       │
│  - 错误重试（指数退避）                                     │
│  - Token 使用监控                                         │
└────────────────────┬─────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│              生成结果处理管道                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ JSON解析 │→ │敏感词过滤 │→ │ Redis检测 │→ │格式验证  │ │
│  │& 格式化   │  │(开源库)   │  │(去重)     │  │(长度、  │ │
│  │          │  │          │  │          │  │字符集)   │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
└────────────────────┬─────────────────────────────────────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
    ┌────▼──┐   ┌───▼────┐  ┌──▼──────┐
    │ Redis │   │ 日志   │  │文本输出  │
    │ 去重  │   │ 统计   │  │持久化   │
    │ 存储  │   │ 监控   │  │         │
    └───────┘   └────────┘  └─────────┘
```

### 核心处理流程

```
触发条件
   ↓
加载配置（动态检测变化）
   ↓
遍历所有风格
   ↓
[对每个风格]
   ├─ 获取最近100条昵称（用于Prompt中避免重复）
   ├─ 渲染Prompt（从配置化模板）
   ├─ 调用GLM API（串行，失败重试）
   ├─ 解析JSON响应
   ├─ 敏感词过滤
   ├─ Redis去重检测 + 插入
   ├─ 长度/字符集验证
   ├─ 写入文本文件
   └─ 记录统计信息
   ↓
汇总指标（总成功率、去重率、过滤率）
   ↓
日志输出 + 监控告警
```

---

## 技术栈选型

| 组件 | 选型 | 理由 |
|------|------|------|
| **编程语言** | Python 3.10+ | 成熟稳定，第三方库丰富，快速开发 |
| **LLM API** | 智谱 GLM | 用户指定，免费额度足够，支持Batch API |
| **任务调度** | APScheduler | 轻量级，支持Cron、interval等多种触发模式 |
| **任务队列** | 自实现 Queue | 规模小，API调用串行，无需复杂MQ |
| **缓存存储** | Redis | O(1)去重查询，支持分布式扩展 |
| **降级存储** | 本地内存Set | Redis宕机时自动降级 |
| **持久化** | 纯文本 (.txt) | 简单可靠，便于查阅和导入 |
| **敏感词库** | 开源库 | 低成本，社区维护 |
| **配置管理** | YAML | 人类可读，支持嵌套结构 |
| **日志** | Python logging | 标准库，轻量级 |
| **监控** | 自实现统计 | 当前规模足够，后期可接Prometheus |
| **容器化** | Docker Compose | 方便本地开发和单机部署 |

---

## 核心模块设计

### 1. API 客户端层 (`src/api/glm_client.py`)

**职责**: 封装GLM API调用，处理重试、限流、Token监控

```python
class GLMClient:
    def __init__(self, api_key: str, org_id: str = None):
        """初始化GLM客户端"""
        self.api_key = api_key
        self.org_id = org_id
        self.request_queue = Queue()  # 串行队列
        self.worker_thread = Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()
    
    def generate(self, prompt: str, model: str = 'glm-4-flash') -> dict:
        """
        同步调用（实际异步处理）
        - 将请求加入队列
        - 等待响应
        - 三次重试机制
        """
        pass
    
    def _process_queue(self):
        """后台线程处理队列，保证串行调用"""
        pass
    
    def _call_api_with_retry(self, prompt: str, max_retries: int = 3) -> dict:
        """
        实际API调用 + 指数退避重试
        - 第1次失败：2秒后重试
        - 第2次失败：4秒后重试
        - 第3次失败：8秒后重试
        """
        pass
    
    def get_token_usage(self) -> dict:
        """获取Token使用统计"""
        pass
```

**设计要点**:
- 单线程 + 队列确保无并发
- 指数退避重试避免频繁轰炸API
- Token监控防止超额

---

### 2. 配置系统 (`src/config/config_manager.py`)

**职责**: 运行时加载、验证、缓存配置

```python
class ConfigManager:
    def __init__(self, config_dir: str = 'config'):
        self.config_dir = config_dir
        self.styles = {}
        self.prompts = {}
        self.system_config = {}
        self._last_modified = {}
        self.load_all()
    
    def load_all(self):
        """一次性加载所有配置"""
        self.load_styles()
        self.load_prompts()
        self.load_system_config()
    
    def check_and_reload(self) -> bool:
        """
        定期检查配置文件变化
        - 高效：仅检查mtime，不重复加载
        - 返回：是否有变化
        """
        pass
    
    def get_style(self, style_name: str) -> dict:
        """获取某风格配置，自动触发reload检查"""
        self.check_and_reload()
        return self.styles.get(style_name)
    
    def list_styles(self) -> list:
        """列出所有可用风格"""
        self.check_and_reload()
        return list(self.styles.keys())
```

**设计要点**:
- 动态加载：支持在线修改配置，下次查询生效
- 高效：仅在mtime变化时重新加载
- 线程安全：使用Lock保护读写

---

### 3. Prompt 管理系统 (`src/prompts/prompt_manager.py`)

**职责**: 管理Prompt模板，支持风格自定义和Prompt版本管理

```python
class PromptManager:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
    
    def get_prompt_template(self, style_name: str) -> str:
        """
        获取某风格的Prompt模板
        - 优先查找: style_templates[style_name]
        - 其次: default_template
        """
        pass
    
    def render_prompt(
        self,
        style_name: str,
        style_description: str,
        min_len: int,
        max_len: int,
        charset: str,
        count: int,
        recent_names: list = None
    ) -> str:
        """
        渲染Prompt：用实际值替换占位符
        - {style_description}: 风格文本描述
        - {min_len}/{max_len}: 长度范围
        - {charset}: 字符集
        - {count}: 生成数量
        - {recent_names}: 最近昵称（避免重复）
        """
        pass
```

**配置样式** (config/styles.yaml):
```yaml
prompts:
  default_template: |
    你是游戏昵称生成器...
  
  style_templates:
    古风: |
      生成{count}个古代诗词风格昵称...
    二次元: |
      生成{count}个ACG风格昵称...

styles:
  古风:
    description: "..."
    length_min: 2
    length_max: 6
    charset: "中文"
    prompt_template: "古风"
```

---

### 4. 去重模块 (`src/dedup/redis_dedup.py`)

**职责**: 实现高精度去重，支持降级和统计

```python
class RedisDedup:
    def __init__(self, redis_url: str = 'redis://localhost:6379'):
        self.redis = redis.from_url(redis_url)
        self._local_fallback = {}  # Redis不可用时的降级方案
        self.stats = {
            'total_checked': 0,
            'total_duplicated': 0
        }
    
    def is_duplicate(self, style: str, name: str) -> bool:
        """检查是否重复，O(1)操作"""
        try:
            return self.redis.sismember(f"{style}:names", name)
        except:
            # 降级：使用本地内存Set
            return name in self._local_fallback.get(style, set())
    
    def add(self, style: str, names: list[str]) -> int:
        """
        添加昵称到去重集合
        - 批量操作：使用pipeline提。高性能
        - 返回：新增成功数量（非重复）
        """
        pass
    
    def get_recent(self, style: str, count: int = 100) -> list:
        """获取最近N个昵称（用于Prompt中避免重复）"""
        pass
    
    def get_stats(self) -> dict:
        """获取去重统计信息"""
        return {
            'total_checked': self.stats['total_checked'],
            'total_duplicated': self.stats['total_duplicated'],
            'duplication_rate': self.stats['total_duplicated'] / max(1, self.stats['total_checked'])
        }
```

**设计要点**:
- Redis SETs：每个风格一个 `{style}:names`
- O(1)查询和添加
- 故障降级：Redis不可用时使用内存Set
- 统计信息：追踪去重率

---

### 5. 敏感词过滤 (`src/filters/sensitive_filter.py`)

**职责**: 过滤敏感词，支持多来源和动态扩展

```python
class SensitiveFilter:
    def __init__(self, base_dict_path: str = None, custom_blacklist: str = None):
        self.base_dict = set()  # 开源库词库
        self.custom_blacklist = set()  # 用户自定义
        self._last_modified = {}
        self.stats = {'total_filtered': 0}
        
        if base_dict_path:
            self.load_base_dict(base_dict_path)
        if custom_blacklist:
            self.load_custom_blacklist(custom_blacklist)
    
    def load_base_dict(self, path: str):
        """加载开源敏感词库"""
        pass
    
    def load_custom_blacklist(self, path: str):
        """加载用户自定义敏感词"""
        pass
    
    def check_and_reload(self) -> bool:
        """动态重载配置文件"""
        pass
    
    def filter_name(self, name: str) -> tuple[bool, str]:
        """
        检查和过滤昵称
        - 输入：昵称文本
        - 输出：(是否包含敏感词, 过滤后文本)
        """
        self.check_and_reload()
        # ...处理逻辑
        pass
    
    def contains_sensitive(self, name: str) -> bool:
        """仅检查，不修改"""
        is_sensitive, _ = self.filter_name(name)
        return is_sensitive
```

**配置** (config/blacklist.txt 或 config/config.yaml):
```yaml
sensitive_words:
  base_dict: "data/sensitive_words.txt"  # 开源库
  custom_blacklist: "config/custom_blacklist.txt"  # 用户自定义
  filter_mode: "remove"  # remove/replace/tag
```

---

### 6. 生成管道 (`src/pipeline/generation_pipeline.py`)

**职责**: 整合所有模块，实现完整的生成流程

```python
class GenerationPipeline:
    def __init__(
        self,
        glm_client: GLMClient,
        config_manager: ConfigManager,
        prompt_manager: PromptManager,
        dedup: RedisDedup,
        sensitive_filter: SensitiveFilter,
        storage: StorageManager
    ):
        self.glm_client = glm_client
        self.config_manager = config_manager
        self.prompt_manager = prompt_manager
        self.dedup = dedup
        self.sensitive_filter = sensitive_filter
        self.storage = storage
    
    def generate_for_style(self, style_name: str) -> dict:
        """
        为某个风格生成昵称
        
        流程:
        1. 获取配置
        2. 准备Prompt（含最近昵称）
        3. 调用API
        4. 处理结果 (解析 → 过滤 → 去重 → 验证)
        5. 存储持久化
        6. 返回统计信息
        """
        style_config = self.config_manager.get_style(style_name)
        
        recent_names = self.dedup.get_recent(style_name, count=100)
        
        prompt = self.prompt_manager.render_prompt(
            style_name=style_name,
            style_description=style_config['description'],
            min_len=style_config['length_min'],
            max_len=style_config['length_max'],
            charset=style_config['charset'],
            count=10000,
            recent_names=recent_names
        )
        
        # 调用API
        response = self.glm_client.generate(prompt)
        
        # 处理
        results = self._process_response(response, style_name, style_config)
        
        # 存储
        self.storage.append_names(style_name, results['valid_names'])
        
        return results
    
    def _process_response(self, response: dict, style_name: str, style_config: dict) -> dict:
        """
        结果处理管道：解析 → 过滤 → 去重 → 验证
        
        返回:
        {
            'valid_names': [...],  # 通过所有检验
            'filtered_sensitive': [...],  # 被敏感词过滤
            'duplicated': [...],  # 被去重检测
            'invalid_format': [...],  # 格式错误
            'stats': {...}
        }
        """
        stats = {
            'generated': 0,
            'passed_filter': 0,
            'passed_dedup': 0,
            'valid': 0,
            'filtered_sensitive': 0,
            'duplicated': 0,
            'invalid_format': 0
        }
        
        # 1. 解析JSON
        try:
            names = json.loads(response['content'])
            if not isinstance(names, list):
                names = [names]
        except:
            return {'valid_names': [], 'stats': stats, 'error': 'JSON解析失败'}
        
        stats['generated'] = len(names)
        
        valid_names = []
        filtered_names = []
        duplicated_names = []
        invalid_names = []
        
        for name in names:
            # 2. 格式验证
            if not isinstance(name, str) or not name.strip():
                invalid_names.append(name)
                stats['invalid_format'] += 1
                continue
            
            name = name.strip()
            
            # 3. 长度和字符集检验
            if not self._validate_format(name, style_config):
                invalid_names.append(name)
                stats['invalid_format'] += 1
                continue
            
            # 4. 敏感词过滤
            if self.sensitive_filter.contains_sensitive(name):
                filtered_names.append(name)
                stats['filtered_sensitive'] += 1
                continue
            
            stats['passed_filter'] += 1
            
            # 5. Redis去重
            if self.dedup.is_duplicate(style_name, name):
                duplicated_names.append(name)
                stats['duplicated'] += 1
                continue
            
            stats['passed_dedup'] += 1
            valid_names.append(name)
            stats['valid'] += 1
        
        # 添加到Redis
        if valid_names:
            self.dedup.add(style_name, valid_names)
        
        return {
            'valid_names': valid_names,
            'filtered': filtered_names,
            'duplicated': duplicated_names,
            'invalid': invalid_names,
            'stats': stats
        }
    
    def _validate_format(self, name: str, style_config: dict) -> bool:
        """验证长度和字符集"""
        # 长度检验
        min_len = style_config.get('length_min', 2)
        max_len = style_config.get('length_max', 6)
        if not (min_len <= len(name) <= max_len):
            return False
        
        # 如需要可加字符集验证
        # charset = style_config.get('charset', '中文')
        # ...
        
        return True
```

---

### 7. 存储管理 (`src/storage/storage_manager.py`)

**职责**: 管理文件输出、元数据记录、备份

```python
class StorageManager:
    def __init__(self, base_dir: str = 'data'):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
    
    def append_names(self, style: str, names: list[str]):
        """
        追加昵称到文件 {style}_names.txt
        - 增量写入（不覆盖）
        - 每行一个昵称
        """
        file_path = self.base_dir / f"{style}_names.txt"
        
        with open(file_path, 'a', encoding='utf-8') as f:
            for name in names:
                f.write(name + '\n')
    
    def write_metadata(self, style: str, stats: dict, timestamp: str):
        """
        写入元数据到文件头或单独文件
        格式: {生成时间} | 数量 | 去重率 | 敏感词过滤率
        """
        meta_file = self.base_dir / f"{style}_metadata.txt"
        
        with open(meta_file, 'a', encoding='utf-8') as f:
            meta_line = (
                f"{timestamp} | "
                f"count={stats['valid']} | "
                f"filter_rate={stats['filtered_sensitive']/max(1,stats['generated']):.2%} | "
                f"dedup_rate={stats['duplicated']/max(1,stats['generated']):.2%}\n"
            )
            f.write(meta_line)
    
    def export(self, style: str, output_path: str):
        """导出昵称到指定位置"""
        source = self.base_dir / f"{style}_names.txt"
        if source.exists():
            shutil.copy(source, output_path)
    
    def get_count(self, style: str) -> int:
        """获取某风格已生成的昵称总数"""
        file_path = self.base_dir / f"{style}_names.txt"
        if not file_path.exists():
            return 0
        return sum(1 for _ in open(file_path, encoding='utf-8'))
```

---

## 配置系统设计

### 目录结构

```
config/
├── config.yaml          # 系统配置（API Key、Redis地址等）
├── styles.yaml          # 风格定义 + Prompt模板
├── blacklist.txt        # 敏感词（可选，可在styles.yaml中定义路径）
└── advanced.yaml        # 高级配置（超时、重试次数等）
```

### config/config.yaml

```yaml
# 系统配置
system:
  log_level: DEBUG
  log_file: logs/app.log
  checkpoint_file: .checkpoint

# API 配置
api:
  provider: glm  # glm | openai | claude
  glm:
    api_key: ${GLM_API_KEY}  # 环境变量或直接配置
    org_id: null
    base_url: https://open.bigmodel.cn/api/paas/v4/chat/completions
  timeout: 30
  max_retries: 3
  retry_wait_base: 2  # 秒

# Redis 配置
redis:
  url: redis://localhost:6379
  db: 0
  fallback_to_memory: true  # Redis不可用时降级到内存

# 储存配置
storage:
  base_dir: data
  enable_backup: false
  backup_interval_hours: 24

# 调度配置
scheduler:
  interval_minutes: 60  # 每60分钟触发一次
  batch_size: 10000  # 单次生成数量
  max_concurrent_tasks: 1  # 确保单线程

# 敏感词配置
sensitive:
  enabled: true
  base_dict_path: data/sensitive_words.txt
  custom_blacklist_path: config/custom_blacklist.txt
  filter_mode: remove  # remove | replace | tag
  replacment_char: "*"
```

### config/styles.yaml

```yaml
# Prompt 模板
prompts:
  # 全局默认模板
  default_template: |
    你是一个专业的游戏昵称生成器。请按以下要求生成昵称：
    
    **生成要求：**
    - 风格特征：{style_description}
    - 昵称长度：{min_len}-{max_len}个字符
    - 字符集：{charset}
    - 数量：{count}个
    - **避免与以下已有昵称相似（编辑距离<2）**：{recent_names}
    
    **返回格式：**
    仅返回JSON数组，不包含其他文字。
    示例：["昵称1", "昵称2", "昵称3"]
  
  # 风格特定模板（可选）
  style_templates:
    古风: |
      生成{count}个古代诗词风格的游戏昵称。
      
      特点：
      - 优先使用诗经、楚辞、四书五经等古籍中的词汇
      - 体现古韵意境，如诗意、典雅、飘逸
      - 避免现代网络用语和符号
      - 常见词汇：风、月、雪、烟、云、溪、林、竹等
      
      示例：雪月风、林溪烟、竹海清音、古月长庚
      
      长度：{min_len}-{max_len}字符
      字符集：{charset}
      
      避免重复：{recent_names}
      
      仅返回JSON数组，无其他文字。
    
    二次元: |
      生成{count}个二次元/ACG风格的游戏昵称。
      
      特点：
      - 含有可爱、萌、神秘、日本风属性
      - 可合理使用日文假名或混合
      - 充满想象力和奇幻色彩
      - 常见元素：星、月、樱、琪、梦、魔、妖等
      
      示例：月之姫、星梦奇迹、樱花泪、琪妙幻想
      
      长度：{min_len}-{max_len}字符
      字符集：{charset}
      
      避免重复：{recent_names}
      
      仅返回JSON数组。
    
    赛博朋克: |
      生成{count}个赛博朋克/科幻未来风格的昵称。
      
      特点：
      - 充满未来感、科技感
      - 冷酷、机械、电子属性
      - 可混合英文数字和特殊符号（如- _ .）
      - 常见元素：Cyber、Neo、Shadow、Void、Phantom等
      
      示例：Neo-Shadow、Cyber-Phantom、VoidWalker、Omega-7
      
      长度：{min_len}-{max_len}字符
      字符集：{charset}
      
      避免重复：{recent_names}
      
      仅返回JSON数组。

# 风格定义
styles:
  古风:
    description: "古代诗词文化风格，参考诗经楚辞，体现诗意典雅"
    length_min: 2
    length_max: 6
    charset: "中文"
    prompt_template: "古风"  # 引用style_templates中的模板
    enabled: true
  
  二次元:
    description: "ACG二次元风格，含有可爱、萌、神秘、日本风属性"
    length_min: 3
    length_max: 8
    charset: "中文+假名"
    prompt_template: "二次元"
    enabled: true
  
  赛博朋克:
    description: "科幻未来感，机械冷酷风格，充满科技属性"
    length_min: 4
    length_max: 12
    charset: "英文+数字"
    prompt_template: "赛博朋克"
    enabled: true
  
  # 新风格可在此追加...
  # 不指定prompt_template的风格会使用default_template
```

### 配置加载机制

```python
# src/config/config_manager.py (关键部分)

class ConfigManager:
    def check_and_reload(self):
        """
        高效的动态加载机制：
        1. 检查文件mtime（毫秒级开销）
        2. 仅在文件变化时重新加载
        3. YAML解析和验证
        """
        current_mtime = Path('config/styles.yaml').stat().st_mtime
        if current_mtime > self._last_modified.get('styles', 0):
            self.load_styles()
            self._last_modified['styles'] = current_mtime
```

**运行时动态加载示例**：

用户想添加新风格"仙侠":
1. 编辑 `config/styles.yaml`，添加新风格定义
2. 保存文件（mtime更新）
3. 下次API调用时自动检测变化并加载
4. 下个调度周期（如下一小时）立即使用新风格

---

## 工作流程

### 日常运行流程

```
[启动应用]
    ↓
初始化所有模块（ConfigManager、RedisDedup、SensitiveFilter等）
    ↓
启动APScheduler
    ↓
[每小时触发]
    ├─ 检查配置变化（ConfigManager.check_and_reload）
    ├─ 获取所有启用的风格
    │
    └─ [对每个风格] （串行遍历）
        ├─ 调用 GenerationPipeline.generate_for_style(style_name)
        │   ├─ 获取相关配置
        │   ├─ 准备Prompt（包含最近昵称）
        │   ├─ 调用GLM API（如失败则重试最多3次）
        │   ├─ 处理结果（解析 → 过滤 → 去重 → 验证）
        │   ├─ 持久化到文件
        │   └─ 返回统计信息
        │
        └─ 记录日志和metrics
    ↓
汇总本轮统计（总生成数、去重率、过滤率、Token消耗）
    ↓
日志输出 + 监控告警
    ↓
[等待下个调度周期]
```

### 故障恢复流程

**场景1：API调用失败**
```
API调用失败
    ↓
捕获异常，进入重试逻辑
    ↓
第1次重试（等待2秒后）
    ↓
仍失败 → 第2次重试（等待4秒后）
    ↓
再失败 → 第3次重试（等待8秒后）
    ↓
完全失败 → 记录错误日志，该风格本轮放弃
    （下一轮正常继续）
```

**场景2：Redis不可用**
```
Redis SET/GET 异常
    ↓
捕获连接异常
    ↓
降级至本地内存Set（_local_fallback）
    ↓
去重检测继续正常工作
    ↓
日志告警："Redis不可用，已自动降级到内存"
    ↓
当Redis恢复时自动切回（下次健康检查）
```

**场景3：应用异常崩溃**
```
应用突然退出
    ↓
记录 checkpoint（最后处理的时间戳）
    ↓
重启应用
    ↓
检测checkpoint，判断是否需要补偿
    ↓
若上次未完成某风格，重新生成该风格（幂等）
```

---

## 数据流与去重机制

### 数据流向图

```
GLM API 响应
    ↓
JSON格式字符串
    ↓
[Pipeline 处理]
  1. JSON.parse → list[str]
  2. 逐条处理：
     ├─ 格式验证 → 去掉非法项
     ├─ 敏感词检测 → 调用 SensitiveFilter.contains_sensitive()
     │                → 是 ：放入 filtered_list
     │                → 否 ：继续
     ├─ Redis去重检测 → 调用 RedisDedup.is_duplicate()
     │                  → 是 ：放入 duplicated_list
     │                  → 否 ：加入 valid_names + Redis.SADD()
     └─ 返回统计
    ↓
StorageManager.append_names(style, valid_names)
    ↓
写入文件 data/{style}_names.txt
```

### 去重的三层机制

#### 第1层：Prompt主动避免（预防）
在生成时，Prompt中包含最近100条已生成的昵称：
```
避免与以下昵称相似（编辑距离<2）：雪月风、林溪烟、竹海云、...
```
LLM会尽量避免生成相似内容。**有效性**：30-40% 重复率降低

#### 第2层：Redis实时检测（防御）
每条生成的昵称都检查Redis Set：
```python
# O(1) 检查
if redis.sismember(f"{style}:names", name):  # 已存在
    skip(name)
else:  # 新昵称
    redis.sadd(f"{style}:names", name)
```
**效果**：精确检测，零漏洞

#### 第3层：文件内容去重（验证）
定期对已持久化的文件执行去重验证：
```python
def verify_and_deduplicate():
    """周期性验证，确保最终输出无重复"""
    for style in styles:
        with open(f"data/{style}_names.txt") as f:
            names = f.readlines()
        
        unique_names = list(set(name.strip() for name in names))
        if len(unique_names) < len(names):
            # 检测到重复，重写文件
            with open(f"data/{style}_names.txt", 'w') as f:
                f.write('\n'.join(unique_names))
```

**预期效果**：三层叠加，<1% 最终重复率

---

## 质量保证

### 单元测试 (`tests/`)

| 模块 | 测试项 | 验证内容 |
|------|--------|---------|
| **ConfigManager** | 动态加载 | 修改YAML后是否自动重载 |
| | 配置验证 | 非法配置是否被拒绝 |
| **PromptManager** | Prompt渲染 | 模板占位符是否正确填充 |
| | 风格特定模板 | 古风/二次元/赛博朋克模板是否分别调用 |
| **RedisDedup** | 去重检测 | is_duplicate() 准确率 100% |
| | 降级机制 | Redis不可用时内存Set是否接管 |
| | 统计信息 | 重复率计算是否正确 |
| **SensitiveFilter** | 敏感词识别 | 已知敏感词是否被检测 |
| | 过滤效果 | 过滤后文本是否干净 |
| **GLMClient** | 重试机制 | 失败后是否正确重试（3次） |
| | 指数退避 | 重试间隔是否为 2/4/8 秒 |
| **Pipeline** | 端到端流程 | 小规模生成(100条)完整流程是否正常 |
| | 统计准确性 | 生成数、过滤数、去重数是否匹配 |

### 集成测试

**场景1：完整生成周期**
```
设定：生成古风风格，数量100条
流程：
  ├─ 加载配置 ✓
  ├─ 渲染Prompt ✓
  ├─ 调用Mock API（传入100条假昵称）✓
  ├─ 解析结果 ✓
  ├─ 敏感词过滤 ✓
  ├─ Redis去重 ✓
  ├─ 写入文件 ✓
  └─ 验证输出文件存在且包含预期数量
```

**场景2：去重准确度**
```
设定：生成与前次相同的100条昵称
验证：
  - Redis中是否全部标记为重复
  - 统计信息中duplicated_count是否=100
  - 输出文件中是否不含任何重复
```

**场景3：敏感词检测**
```
设定：Prompt中故意注入10个已知敏感词
验证：
  - SensitiveFilter是否全部检测出
  - filtered_sensitive数是否=10
  - 输出文件中是否不含这些词
```

**场景4：配置热加载**
```
设定：应用运行中，修改styles.yaml添加新风格
验证：
  - ConfigManager是否自动检测变化
  - 下次调度是否使用新风格
  - 新风格Prompt是否正确渲染
```

**场景5：故障恢复**
```
设定：API调用失败，模拟网络异常
验证：
  - 系统是否自动重试3次
  - 重试间隔是否遵循指数退避
  - 最终失败后是否优雅降级（跳过该风格）
  - 下一轮是否正常继续
```

### 性能基准测试

```python
# tests/benchmark.py

def benchmark_dedup():
    """100万条数据的去重性能"""
    redis_dedup = RedisDedup()
    
    # 加载100万条
    names = [f"name_{i}" for i in range(1_000_000)]
    redis_dedup.add("test", names)
    
    # 检查性能
    import time
    start = time.time()
    for _ in range(10000):
        redis_dedup.is_duplicate("test", "name_500000")
    elapsed = time.time() - start
    
    avg_latency = elapsed / 10000 * 1000  # ms
    assert avg_latency < 5, f"去重检查延迟过高: {avg_latency}ms"
    print(f"✓ 去重检查平均延迟: {avg_latency:.2f}ms")

def benchmark_sensitive_filter():
    """敏感词检测性能"""
    filter = SensitiveFilter()
    
    import time
    names = [f"测试昵称_{i}" for i in range(10000)]
    
    start = time.time()
    for name in names:
        filter.contains_sensitive(name)
    elapsed = time.time() - start
    
    throughput = len(names) / elapsed
    print(f"✓ 敏感词检测吞吐量: {throughput:.0f} ops/s")

def benchmark_api_call():
    """API调用延迟"""
    glm_client = GLMClient()
    
    import time
    start = time.time()
    response = glm_client.generate("生成5个昵称")
    elapsed = time.time() - start
    
    print(f"✓ API调用延迟: {elapsed:.2f}s")
    assert elapsed < 30, "API响应超时"
```

### 数据质量验证

**抽样检查** (每周运行):
```python
def quality_check():
    """人工验证生成质量"""
    for style in styles:
        with open(f"data/{style}_names.txt") as f:
            # 随机抽样100条
            all_names = f.readlines()
            sample = random.sample(all_names, min(100, len(all_names)))
        
        # 人工检查清单
        print(f"\n【{style}】质量检查:")
        for name in sample[:5]:  # 打印前5条供人工检查
            print(f"  - {name.strip()}")
        
        # 自动检查
        ├─ 长度范围是否符合配置 ✓
        ├─ 字符集是否符合配置 ✓
        ├─ 是否包含敏感词 ✓
        ├─ 是否有明显重复 ✓
        └─ 是否符合风格描述 [需人工判断]
```

---

## 部署与运维

### 本地开发环境

**环境准备**:
```bash
# 1. 克隆项目
cd /Users/supermuscleman/Program/rand_names

# 2. 创建虚拟环境
python3.10 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动Redis（Docker）
docker-compose up -d redis

# 5. 配置API Key
export GLM_API_KEY="你的API Key"

# 6. 运行应用
python src/main.py
```

### Docker 部署

**docker-compose.yml**:
```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  app:
    build:
      context: .
      dockerfile: Dockerfile
    depends_on:
      - redis
    environment:
      - GLM_API_KEY=${GLM_API_KEY}
      - REDIS_URL=redis://redis:6379
      - LOG_LEVEL=INFO
    volumes:
      - ./config:/app/config
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped

volumes:
  redis_data:
```

**Dockerfile**:
```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "src/main.py"]
```

### 监控与告警

```python
# src/monitoring.py

class Monitor:
    def __init__(self, log_file: str = 'logs/app.log'):
        self.log_file = log_file
        self.metrics = {}
    
    def record_generation(self, style: str, stats: dict):
        """记录本轮生成统计"""
        self.metrics[style] = {
            'timestamp': datetime.now(),
            'generated': stats['generated'],
            'valid': stats['valid'],
            'duplicated': stats['duplicated'],
            'filtered': stats['filtered_sensitive'],
            'filter_rate': stats['filtered_sensitive'] / max(1, stats['generated']),
            'dedup_rate': stats['duplicated'] / max(1, stats['generated'])
        }
    
    def check_alarms(self):
        """检查是否需要告警"""
        alerts = []
        
        for style, metrics in self.metrics.items():
            # 1. 去重率异常高
            if metrics['dedup_rate'] > 0.2:
                alerts.append(f"⚠️ {style}去重率过高: {metrics['dedup_rate']:.1%}")
            
            # 2. 生成失败
            if metrics['generated'] == 0:
                alerts.append(f"❌ {style}生成失败: 0条")
            
            # 3. 过滤率异常
            if metrics['filter_rate'] > 0.1:
                alerts.append(f"⚠️ {style}敏感词过滤率: {metrics['filter_rate']:.1%}")
        
        # 4. Token使用告警
        token_usage = glm_client.get_token_usage()
        if token_usage['usage_rate'] > 0.8:
            alerts.append(f"⚠️ Token使用接近限额: {token_usage['usage_rate']:.1%}")
        
        return alerts
    
    def send_alert(self, message: str):
        """发送告警（可扩展为钉钉、企业微信等）"""
        # 当前：仅记录日志
        logger.warning(message)
        
        # 后期可添加：
        # - 钉钉机器人通知
        # - 短信告警
        # - Slack 通知
```

### 日志管理

```python
# src/logging_config.py

import logging
import logging.handlers

def setup_logging(log_file: str = 'logs/app.log', level: str = 'INFO'):
    """配置日志系统"""
    
    logger = logging.getLogger('rand_names')
    logger.setLevel(getattr(logging, level))
    
    # 文件处理器（日志轮转）
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    
    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
```

---

## 扩展性

### 如何添加新风格

**步骤1**: 编辑 `config/styles.yaml`
```yaml
styles:
  新风格名:
    description: "描述新风格的特征"
    length_min: 2
    length_max: 8
    charset: "中文"
    prompt_template: "新风格"  # 可选，不指定则用default

prompts:
  style_templates:
    新风格: |
      生成{count}个...新风格的描述...
```

**步骤2**: 下次调度时自动生效（无需重启）

### 如何添加新的LLM厂商

**设计**：抽象API客户端，支持多厂商

```python
# src/api/base_client.py
class BaseLLMClient(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> dict:
        pass

# src/api/glm_client.py
class GLMClient(BaseLLMClient):
    def generate(self, prompt: str) -> dict:
        # 智谱实现

# src/api/openai_client.py
class OpenAIClient(BaseLLMClient):
    def generate(self, prompt: str) -> dict:
        # OpenAI实现

# src/api/client_factory.py
def create_client(provider: str) -> BaseLLMClient:
    if provider == 'glm':
        return GLMClient()
    elif provider == 'openai':
        return OpenAIClient()
    else:
        raise ValueError(f"Unknown provider: {provider}")
```

**配置选择** (config/config.yaml):
```yaml
api:
  provider: glm  # 改为 openai 即可切换
```

### 如何升级去重存储

**当前**: Redis Set（内存)  
**后期升级方案**:

```python
# src/dedup/base_dedup.py
class BaseDedupBackend(ABC):
    @abstractmethod
    def is_duplicate(self, style: str, name: str) -> bool:
        pass
    
    @abstractmethod
    def add(self, style: str, names: list) -> int:
        pass

# 实现1: Redis
class RedisDedup(BaseDedupBackend):
    pass

# 实现2: PostgreSQL（大规模）
class PostgreSQLDedup(BaseDedupBackend):
    def __init__(self, connection_string):
        self.conn = psycopg2.connect(connection_string)
    
    def is_duplicate(self, style, name):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT EXISTS(SELECT 1 FROM names WHERE style=%s AND name=%s)",
            (style, name)
        )
        return cursor.fetchone()[0]

# 工厂
def create_dedup_backend(backend_type: str) -> BaseDedupBackend:
    if backend_type == 'redis':
        return RedisDedup()
    elif backend_type == 'postgresql':
        return PostgreSQLDedup('postgresql://...')
```

---

## 风险与缓解

| 风险 | 影响 | 概率 | 缓解方案 |
|------|------|------|---------|
| **API并发限制触发** | 生成拒绝/限流 | 中 | ✓ 严格串行调用，Queue控制 |
| **API频繁超时** | 本轮生成失败 | 低 | ✓ 重试机制（3次），告警 |
| **Redis宕机** | 去重降级 | 低 | ✓ 自动降级到内存Set |
| **敏感词库不全** | 敏感内容泄露 | 中 | ✓ 支持自定义扩展 + 定期更新 |
| **Prompt偏差** | 生成质量下降 | 中 | ✓ 配置化Prompt，便于快速调整 |
| **Token额度不足** | 生成中断 | 低 | ✓ 监控Token使用，主动告警 |
| **配置文件语法错误** | 应用无法启动 | 低 | ✓ YAML验证，错误反馈清晰 |
| **文件磁盘满** | 无法写入 | 低 | ✓ 监控磁盘空间，定期备份 |
| **大量重复昵称** | 去重有效性下降 | 中 | ✓ 三层去重 + 周期性验证文件 |
| **网络抖动** | 请求失败 | 中 | ✓ 重试机制 + 长超时设置 |

---

## 实现时间线

### 阶段1：基础框架 (3-4天)
- [ ] 项目初始化与结构搭建
- [ ] ConfigManager 动态加载实现
- [ ] GLMClient 封装与重试机制
- [ ] PromptManager 模板管理
- [ ] 基础单元测试

**交付**: 能生成100条昵称的小规模系统

### 阶段2：去重 + 敏感词 (3-4天)
- [ ] RedisDedup 实现与测试
- [ ] SensitiveFilter 集成开源库
- [ ] GenerationPipeline 完整流程
- [ ] StorageManager 文件输出
- [ ] 集成测试（小规模）

**交付**: 完整端到端流程，去重率<1%

### 阶段3：调度 + 监控 (2-3天)
- [ ] APScheduler 集成
- [ ] 监控与告警系统
- [ ] 日志系统
- [ ] 故障恢复机制
- [ ] 性能基准测试

**交付**: 自动化持续生成，每小时1w条

### 阶段4：测试 + 优化 (2-3天)
- [ ] 完整测试覆盖
- [ ] 质量验证（抽样检查）
- [ ] Prompt优化调整
- [ ] 性能优化（API响应时间、去重速度）
- [ ] 文档完善

**交付**: 生产就绪的系统

### 阶段5：上线与迭代
- [ ] 本地运行验证
- [ ] Docker部署
- [ ] 长期稳定性观察（2周）
- [ ] 根据实际运行调整参数
- [ ] 支持多风格、新风格快速接入

---

## 关键设计决策汇总

| 决策 | 方案 | 理由 |
|------|------|------|
| **API调用** | 单线程 + Queue | 遵守免费Key限制，简化并发管理 |
| **去重存储** | Redis Set | O(1)查询，易扩展，支持降级 |
| **持久化** | 纯文本(.txt) | 简单可靠，易导入，不需复杂DB |
| **敏感词** | 开源库 + 自定义 | 低成本，灵活扩展 |
| **配置** | YAML + 动态加载 | 易读易编辑，支持0停机更新 |
| **Prompt** | 配置化管理 | 快速迭代，便于A/B测试 |
| **调度** | APScheduler | 轻量级，满足定时任务需求 |
| **风格定义** | 自由文本 + LLM理解 | 灵活，用户友好，扩展性强 |
| **错误处理** | 指数退避重试 | 遵守API限制，避免频繁轰炸 |
| **故障隔离** | 风格独立处理 | 单风格失败不影响其他 |

---

## 总体评估

✅ **技术可行性**: 完全可行，无重大技术障碍  
💰 **成本**: 一次性实施投入<40小时，运行成本极低（仅GLM API）  
⏱️ **时间**: 2-3周完成生产级系统  
📈 **扩展性**: 后期易于添加新厂商、新风格、新存储  
🛡️ **可靠性**: 三层去重 + 故障降级，指标明确可追踪  

---

**下一步**: 开始阶段1的实现！

