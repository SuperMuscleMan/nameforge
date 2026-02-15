"""
StorageManager 单元测试
"""

import pytest
import tempfile
from pathlib import Path
from src.storage.storage_manager import StorageManager


@pytest.fixture
def temp_data_dir():
    """创建临时数据目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def storage_manager(temp_data_dir):
    """创建StorageManager实例"""
    return StorageManager(base_dir=temp_data_dir)


class TestStorageManager:
    """StorageManager 测试类"""

    def test_init_creates_directory(self, temp_data_dir):
        """测试初始化创建目录"""
        storage = StorageManager(base_dir=temp_data_dir)
        assert Path(temp_data_dir).exists()

    def test_append_names_creates_file(self, storage_manager):
        """测试append_names创建文件"""
        names = ["昵称1", "昵称2", "昵称3"]
        result = storage_manager.append_names("古风", names)

        assert result == 3

        # 验证文件内容
        file_path = Path(storage_manager.base_dir) / "古风_names.txt"
        assert file_path.exists()

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip().split("\n")
            assert len(content) == 3
            assert content[0] == "昵称1"
            assert content[1] == "昵称2"
            assert content[2] == "昵称3"

    def test_append_names_appends_to_existing(self, storage_manager):
        """测试append_names追加到现有文件"""
        # 第一次追加
        names1 = ["昵称1", "昵称2"]
        storage_manager.append_names("古风", names1)

        # 第二次追加
        names2 = ["昵称3", "昵称4"]
        storage_manager.append_names("古风", names2)

        # 验证总数
        file_path = Path(storage_manager.base_dir) / "古风_names.txt"
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip().split("\n")
            assert len(content) == 4

    def test_append_names_empty_list(self, storage_manager):
        """测试追加空列表"""
        result = storage_manager.append_names("古风", [])
        assert result == 0

    def test_append_names_strips_whitespace(self, storage_manager):
        """测试追加时去除空白"""
        names = ["  昵称1  ", "昵称2\n", "\t昵称3"]
        storage_manager.append_names("古风", names)

        file_path = Path(storage_manager.base_dir) / "古风_names.txt"
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.read().strip().split("\n")
            assert lines[0] == "昵称1"
            assert lines[1] == "昵称2"
            assert lines[2] == "昵称3"

    def test_get_count(self, storage_manager):
        """测试获取昵称计数"""
        names = ["昵称1", "昵称2", "昵称3"]
        storage_manager.append_names("古风", names)

        count = storage_manager.get_count("古风")
        assert count == 3

    def test_get_count_nonexistent_style(self, storage_manager):
        """测试获取不存在风格的计数"""
        count = storage_manager.get_count("不存在的风格")
        assert count == 0

    def test_list_names(self, storage_manager):
        """测试列出昵称"""
        names = ["昵称1", "昵称2", "昵称3"]
        storage_manager.append_names("古风", names)

        result = storage_manager.list_names("古风")
        assert result == names

    def test_list_names_with_limit(self, storage_manager):
        """测试带限制的列出昵称"""
        names = [f"昵称{i}" for i in range(10)]
        storage_manager.append_names("古风", names)

        result = storage_manager.list_names("古风", limit=3)
        assert len(result) == 3
        # 返回最后3条
        assert result == ["昵称7", "昵称8", "昵称9"]

    def test_list_names_nonexistent(self, storage_manager):
        """测试列出不存在的风格"""
        result = storage_manager.list_names("不存在的风格")
        assert result == []

    def test_write_metadata(self, storage_manager):
        """测试写入元数据"""
        stats = {
            "generated": 100,
            "valid": 95,
            "filtered_sensitive": 3,
            "duplicated": 2,
            "invalid_format": 0,
        }
        storage_manager.write_metadata("古风", stats, timestamp="2026-02-14 10:00:00")

        meta_file = Path(storage_manager.base_dir) / "古风_metadata.txt"
        assert meta_file.exists()

        with open(meta_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "2026-02-14 10:00:00" in content
            assert "count=95" in content
            assert "filter_rate=3.0%" in content
            assert "dedup_rate=2.0%" in content

    def test_export(self, storage_manager, temp_data_dir):
        """测试导出文件"""
        # 创建源文件
        names = ["昵称1", "昵称2"]
        storage_manager.append_names("古风", names)

        # 导出到新位置
        output_path = Path(temp_data_dir) / "export.txt"
        result = storage_manager.export("古风", str(output_path))

        assert result is True
        assert output_path.exists()

        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "昵称1" in content
            assert "昵称2" in content

    def test_export_nonexistent(self, storage_manager, temp_data_dir):
        """测试导出不存在的风格"""
        output_path = Path(temp_data_dir) / "export.txt"
        result = storage_manager.export("不存在的风格", str(output_path))

        assert result is False
        assert not output_path.exists()

    def test_clear(self, storage_manager):
        """测试清空昵称"""
        names = ["昵称1", "昵称2"]
        storage_manager.append_names("古风", names)

        file_path = Path(storage_manager.base_dir) / "古风_names.txt"
        assert file_path.exists()

        result = storage_manager.clear("古风")
        assert result is True
        assert not file_path.exists()

    def test_clear_nonexistent(self, storage_manager):
        """测试清空不存在的风格"""
        result = storage_manager.clear("不存在的风格")
        assert result is True
