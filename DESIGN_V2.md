# 游戏昵称生成系统 V2 - 词根模板方案设计文档

**版本**: 2.0  
**日期**: 2026年2月15日  
**状态**: 设计阶段  

---

## 1. 设计背景

### 1.1 原方案问题

原方案（V1）试图让AI直接生成海量（5000-10000条）昵称，存在以下根本性问题：

1. **上下文长度限制**：LLM无法在一次生成中保持对10000条昵称的记忆和去重
2. **重复率无法控制**：Prompt中只能注入最近20条，AI会大量重复生成
3. **API成本高昂**：生成10000条需要多次API调用，免费额度很快耗尽
4. **生成质量下降**：批量越大，AI越容易"偷懒"，生成低质量、相似昵称

### 1.2 V2方案核心思想

**"AI生成高质量词根 + 离线模板组合"**

- AI只需生成几百个高质量词根（1-2次API调用）
- 通过预定义模板离线组合生成海量昵称（零API消耗）
- 模板保证语义通顺，词根筛选保证质量

---

## 2. 系统架构

### 2.1 总体架构

```
┌──────────────────────────────────────────────────────────┐
│                     配置管理层                             │
│  - styles.yaml（风格定义 + 词根类别 + 组合模板）              │
│  - {style}_roots.yaml（词根存储）                          │
└────────────────────┬─────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│                   词根管理模块                             │
│  - WordRootManager                                       │
│    ├─ 检查词根是否存在                                     │
│    ├─ 调用AI生成词根（如不存在）                            │
│    ├─ 存储词根到YAML文件                                   │
│    └─ 加载词根到内存                                       │
└────────────────────┬─────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│                   昵称生成模块                             │
│  - NicknameGenerator                                     │
│    ├─ 读取词根和模板                                       │
│    ├─ 按模板组合生成候选昵称                                │
│    ├─ 应用过滤规则（长度、重复字）                          │
│    ├─ 去重处理                                            │
│    └─ 返回指定数量昵称                                     │
└────────────────────┬─────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│                   存储管理模块                             │
│  - StorageManager                                        │
│    ├─ 追加昵称到文件                                       │
│    └─ 记录生成统计                                         │
└──────────────────────────────────────────────────────────┘
```

### 2.2 核心处理流程

```
用户请求生成 {count} 条 {style} 风格昵称
              ↓
    WordRootManager.check_roots(style)
              ↓
    词根存在? ──否──→ 调用AI生成词根
              ↓           ↓
              是    存储到 {style}_roots.yaml
              ↓
    NicknameGenerator.generate(style, count)
              ↓
    加载词根类别A、B、C...
              ↓
    遍历所有模板组合
              ↓
    应用过滤规则
      ├─ 长度检查
      ├─ 重复字检查
      └─ 禁用组合检查
              ↓
    去重（使用Set）
              ↓
    随机采样 {count} 条
              ↓
    返回结果并存储
```

---

## 3. 配置设计

### 3.1 styles.yaml 扩展

```yaml
# 词根生成配置
word_roots:
  # 每风格需要生成的词根数量
  count_per_category: 100
  
  # 词根类别定义（每风格可定义2-3个类别）
  categories:
    古风:
      - name: "意象"
        description: "自然意象词，如山水、风月、云雾等"
        examples: ["云", "月", "风", "雪", "墨", "竹", "溪", "山"]
      - name: "建筑"
        description: "古建筑相关，如亭台楼阁、轩斋居庐等"
        examples: ["轩", "阁", "楼", "院", "亭", "台", "堂", "斋"]
    
    二次元:
      - name: "前缀"
        description: "萌系前缀，表达可爱、软、甜等感觉"
        examples: ["小", "软", "甜", "萌", "奶", "糯", "樱", "星"]
      - name: "元素"
        description: "二次元常见元素，如糖果、星星、樱花等"
        examples: ["糖", "星", "樱", "月", "梦", "雪", "花", "音"]
      - name: "后缀"
        description: "日系后缀，如酱、娘、姬、碳等"
        examples: ["酱", "娘", "姬", "碳", "酱", "球", "宝", "仔"]
    
    赛博朋克:
      - name: "科技"
        description: "科技相关词汇，如电子、网络、数据等"
        examples: ["Cyber", "Neo", "Data", "Net", "Tech", "Code", "Byte", "Pixel"]
      - name: "属性"
        description: "冷酷、机械属性词"
        examples: ["Shadow", "Void", "Phantom", "Ghost", "Steel", "Iron", "Core", "Node"]

  # 组合模板（每风格定义3-5个模板增加多样性）
  templates:
    古风:
      - "{意象}{建筑}"           # 云轩、月阁
      - "{意象}之{意象}"        # 云之月、风之雪
      - "{意象}{意象}"          # 云月、风雪
      - "{建筑}{意象}"          # 轩云、阁月
    
    二次元:
      - "{前缀}{元素}"          # 小糖、软星
      - "{元素}{后缀}"          # 糖酱、星娘
      - "{前缀}{元素}{后缀}"    # 小糖酱、软星娘
      - "{元素}の{元素}"        # 樱の星、梦の月
    
    赛博朋克:
      - "{科技}-{属性}"         # Cyber-Shadow
      - "{属性}{科技}"          # ShadowCyber
      - "{科技}_{属性}"         # Neo_Void
      - "{属性}_{编号}"         # Phantom_07

# 过滤规则
filters:
  # 禁止重复字（如"云云"、"月月"）
  forbid_duplicate_chars: true
  
  # 禁用组合（某些词根组合可能不通顺）
  forbidden_combinations:
    古风:
      - ["风", "风"]  # 避免"风风"
    二次元:
      - ["酱", "酱"]  # 避免"酱酱"

# 风格定义（继承V1）
styles:
  古风:
    description: "古代诗词文化风格，参考诗经楚辞，体现诗意典雅"
    length_min: 2
    length_max: 4
    charset: "中文"
    enabled: true
  
  二次元:
    description: "ACG二次元风格，含有可爱、萌、神秘、日本风属性"
    length_min: 2
    length_max: 4
    charset: "中文"
    enabled: true
  
  赛博朋克:
    description: "科幻未来感，机械冷酷风格，充满科技属性"
    length_min: 4
    length_max: 12
    charset: "英文+数字"
    enabled: true
```

### 3.2 词根存储格式 ({style}_roots.yaml)

```yaml
# data/古风_roots.yaml
metadata:
  style: "古风"
  generated_at: "2026-02-15T10:30:00"
  total_count: 200

categories:
  意象:
    - "云"
    - "月"
    - "风"
    - "雪"
    - "墨"
    - "竹"
    - "溪"
    - "山"
    - "星"
    - "霜"
    # ... 共100个
  
  建筑:
    - "轩"
    - "阁"
    - "楼"
    - "院"
    - "亭"
    - "台"
    - "堂"
    - "斋"
    - "居"
    - "庐"
    # ... 共100个
```

---

## 4. 模块设计

### 4.1 WordRootManager 词根管理器

```python
class WordRootManager:
    """
    管理词根的生成、存储和加载
    """
    
    def __init__(self, glm_client: GLMClient, config_manager: ConfigManager):
        self.glm_client = glm_client
        self.config_manager = config_manager
        self.roots_cache = {}  # 内存缓存
    
    def get_roots(self, style_name: str) -> Dict[str, List[str]]:
        """
        获取指定风格的词根
        
        流程:
        1. 检查内存缓存
        2. 检查文件是否存在
        3. 如不存在，调用AI生成
        4. 返回词根字典 {类别: [词根列表]}
        """
        pass
    
    def _load_roots_from_file(self, style_name: str) -> Optional[Dict]:
        """从YAML文件加载词根"""
        pass
    
    def _generate_roots(self, style_name: str) -> Dict[str, List[str]]:
        """
        调用AI生成词根
        
        为每个类别单独调用API（或一次生成所有类别）
        使用专门优化的Prompt确保词根质量
        """
        pass
    
    def _save_roots_to_file(self, style_name: str, roots: Dict):
        """保存词根到YAML文件"""
        pass
    
    def _build_generation_prompt(self, style_name: str, category: Dict) -> str:
        """
        构建词根生成Prompt
        
        要求:
        - 高质量、符合风格
        - 避免生僻字
        - 适合组合成昵称
        - 返回JSON格式
        """
        pass
```

### 4.2 NicknameGenerator 昵称生成器

```python
class NicknameGenerator:
    """
    基于词根和模板生成昵称
    """
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
    
    def generate(
        self, 
        style_name: str, 
        roots: Dict[str, List[str]], 
        count: int
    ) -> List[str]:
        """
        生成指定数量的昵称
        
        流程:
        1. 获取模板列表
        2. 生成所有可能的组合（笛卡尔积）
        3. 应用过滤规则
        4. 去重
        5. 随机采样指定数量
        
        Args:
            style_name: 风格名称
            roots: 词根字典 {类别: [词根列表]}
            count: 需要生成的数量
            
        Returns:
            昵称列表
        """
        pass
    
    def _apply_template(self, template: str, roots: Dict[str, List[str]]) -> List[str]:
        """
        应用单个模板生成候选昵称
        
        例如: template="{意象}{建筑}"
        生成: ["云轩", "云阁", "月轩", "月阁", ...]
        """
        pass
    
    def _apply_filters(
        self, 
        names: List[str], 
        style_config: Dict,
        filters_config: Dict
    ) -> List[str]:
        """
        应用过滤规则
        
        - 长度检查
        - 重复字检查
        - 禁用组合检查
        """
        pass
    
    def _has_duplicate_chars(self, name: str) -> bool:
        """检查是否有重复字（如"云云"）"""
        pass
    
    def _is_forbidden_combination(self, name: str, forbidden: List) -> bool:
        """检查是否是禁用组合"""
        pass
```

### 4.3 修改 GenerationPipeline

```python
class GenerationPipeline:
    def __init__(...):
        # 新增
        self.root_manager = WordRootManager(glm_client, config_manager)
        self.nickname_generator = NicknameGenerator(config_manager)
    
    def generate_for_style(self, style_name: str, count: int = 100) -> Dict:
        """
        V2版本生成流程
        """
        # 1. 获取词根（如不存在则生成）
        roots = self.root_manager.get_roots(style_name)
        
        # 2. 使用模板组合生成昵称
        names = self.nickname_generator.generate(style_name, roots, count)
        
        # 3. 存储结果
        self.storage.append_names(style_name, names)
        
        return {
            'valid_names': names,
            'stats': {
                'generated': len(names),
                'valid': len(names),
            }
        }
```

---

## 5. 关键算法

### 5.1 模板组合算法

```python
def generate_from_template(template: str, roots: Dict) -> List[str]:
    """
    根据模板和词根生成所有组合
    
    示例:
    template = "{意象}{建筑}"
    roots = {
        "意象": ["云", "月"],
        "建筑": ["轩", "阁"]
    }
    
    返回: ["云轩", "云阁", "月轩", "月阁"]
    """
    import re
    from itertools import product
    
    # 提取模板中的类别占位符
    categories = re.findall(r'\{(\w+)\}', template)
    
    # 获取每个类别的词根列表
    root_lists = [roots[cat] for cat in categories]
    
    # 笛卡尔积生成所有组合
    combinations = product(*root_lists)
    
    # 替换模板生成昵称
    results = []
    for combo in combinations:
        name = template
        for i, cat in enumerate(categories):
            name = name.replace(f"{{{cat}}}", combo[i])
        results.append(name)
    
    return results
```

### 5.2 智能采样算法

当组合数量 > 需求数量时，需要智能采样：

```python
def smart_sample(candidates: List[str], count: int) -> List[str]:
    """
    智能采样，确保多样性
    
    策略:
    1. 先按模板分组
    2. 每组按比例采样
    3. 组内随机采样
    """
    pass
```

---

## 6. 质量保障

### 6.1 词根质量要求

AI生成词根时的Prompt要求：

```
请为{风格}生成{数量}个高质量的{类别}词根。

要求：
1. 必须符合{风格}特征，体现{描述}
2. 避免生僻字，常用字优先
3. 适合与其他词根组合成昵称
4. 词根长度1-2字为宜
5. 高质量、有美感、无攻击性
6. 参考示例：{examples}

返回JSON数组格式，仅返回词根列表，无其他文字。
例如：["云", "月", "风", "雪", ...]
```

### 6.2 过滤规则

| 规则 | 说明 | 示例 |
|------|------|------|
| 长度过滤 | 过滤超出风格长度限制的昵称 | "云之月轩"（4字）被过滤（限制2-4字） |
| 重复字过滤 | 过滤含重复字的昵称 | "云云"、"月月"被过滤 |
| 禁用组合 | 过滤特定不通顺组合 | "风风"、"酱酱"被过滤 |

### 6.3 去重机制

```python
# 使用Set确保唯一性
unique_names = list(set(candidates))

# 如仍不足，可考虑与已生成文件去重（V2暂不实现，V3可加入）
```

---

## 7. 预期效果

### 7.1 生成能力估算

| 风格 | 类别数 | 每类词根 | 模板数 | 理论组合数 |
|------|--------|---------|--------|-----------|
| 古风 | 2 | 100 | 4 | 100×100×4 = 40,000 |
| 二次元 | 3 | 100 | 4 | 100×100×100×4 = 4,000,000 |
| 赛博朋克 | 2 | 100 | 4 | 100×100×4 = 40,000 |

**实际可用**（经长度、重复字过滤后约70%）：
- 古风：~28,000条
- 二次元：~2,800,000条
- 赛博朋克：~28,000条

### 7.2 API调用估算

| 阶段 | 调用次数 | 说明 |
|------|---------|------|
| 词根生成 | 每风格1-3次 | 每类别1次，或一次生成所有类别 |
| 昵称生成 | 0次 | 纯离线组合 |
| **总计** | **3-9次** | 即可生成50万+昵称 |

---

## 8. 实现计划

### Phase 1: 核心实现
- [ ] 更新 styles.yaml 配置结构
- [ ] 实现 WordRootManager 模块
- [ ] 实现 NicknameGenerator 模块
- [ ] 修改 GenerationPipeline 集成新流程
- [ ] 编写基础单元测试

### Phase 2: 验证优化
- [ ] 运行生成测试，检查质量
- [ ] 调整词根Prompt优化质量
- [ ] 优化过滤规则
- [ ] 完善错误处理

### Phase 3: 文档交付
- [ ] 更新使用文档
- [ ] 记录生成示例
- [ ] 性能测试报告

---

## 9. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 词根质量不佳 | 中 | 高 | 优化Prompt，增加示例，允许手动编辑词根文件 |
| 组合结果单一 | 低 | 中 | 增加模板数量，引入更多词根类别 |
| 过滤过于严格 | 低 | 中 | 提供配置调整过滤规则 |
| 词根文件损坏 | 低 | 中 | YAML解析错误时重新生成 |

---

## 10. 关键设计决策

| 决策 | 方案 | 理由 |
|------|------|------|
| **词根存储格式** | YAML文件 | 人类可读，便于手动调整 |
| **组合方式** | 模板替换 | 简单可靠，保证通顺 |
| **去重时机** | 生成后去重 | 实现简单，V3可加入前置去重 |
| **API调用策略** | 按需生成词根 | 节省API调用，词根可复用 |
| **过滤规则** | 配置化 | 便于调整，适应不同风格 |

---

**下一步**: 开始Phase 1实现
