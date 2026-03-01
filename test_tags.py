"""
测试标签系统实现
"""
import sys
import os
sys.path.insert(0, 'E:/funny_project/nameforge')

# 设置UTF-8编码
if sys.platform == 'win32':
    os.system('chcp 65001 >nul')

from src.config.config_manager import ConfigManager
from src.tags.tag_manager import TagManager

# 初始化
config_manager = ConfigManager("E:/funny_project/nameforge/config")
tag_manager = TagManager(config_manager)

# 测试1: 获取二次元标签配置
print("=" * 50)
print("测试1: 获取二次元标签配置")
print("=" * 50)
tags_config = config_manager.get_style_tags("二次元")
print(f"可用标签: {tags_config.get('available', [])}")
print(f"冲突规则: {tags_config.get('conflicts', [])}")

# 测试2: 检查标签兼容性
print("\n" + "=" * 50)
print("测试2: 检查标签兼容性")
print("=" * 50)
test_cases = [
    (["冷色调", "元气"], "应该兼容"),
    (["冷色调", "暖色调"], "应该冲突"),
    (["暗色调", "治愈"], "应该冲突"),
    (["魔法", "科技"], "应该冲突"),
    (["魔法", "治愈"], "应该兼容"),
]

for tags, expected in test_cases:
    result = tag_manager.check_tag_compatibility(tags, [], "二次元")
    status = "[OK]" if result else "[FAIL]"
    print(f"{status} {tags} - {expected}: {'兼容' if result else '冲突'}")

# 测试3: 获取词根类别
print("\n" + "=" * 50)
print("测试3: 获取词根类别")
print("=" * 50)
categories = config_manager.get_word_root_categories("二次元")
for cat in categories:
    print(f"- {cat['name']}: {cat['description']} (数量: {cat.get('count_per_category', 0)})")

# 测试4: 获取模板
print("\n" + "=" * 50)
print("测试4: 获取模板")
print("=" * 50)
templates = config_manager.get_word_root_templates("二次元")
for i, template in enumerate(templates, 1):
    print(f"{i}. {template}")

print("\n[SUCCESS] 所有测试完成！")
