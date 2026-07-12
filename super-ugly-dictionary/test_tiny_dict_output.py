"""
超级简陋小词典 - 输出验证测试用例

测试输出文件：
1. 验证输出文件存在
2. 验证 JSON 格式正确
3. 验证单词数量符合预期
"""

import pytest
import sys
import os
import json
import tempfile

# 确保可以导入同目录的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestTinyDictOutput:
    """测试输出功能"""

    def test_output_file_exists(self):
        """验证输出文件存在"""
        from build_tiny_dict import build_tiny_dict
        
        # 使用临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # 构建小量数据
            build_tiny_dict(output_path=temp_path, limit=5)
            
            # 验证文件存在
            assert os.path.exists(temp_path)
            
        finally:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_json_format_valid(self):
        """验证 JSON 格式正确"""
        from build_tiny_dict import build_tiny_dict
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # 构建小量数据
            build_tiny_dict(output_path=temp_path, limit=3)
            
            # 读取并验证 JSON 格式
            with open(temp_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 验证顶层结构
            assert "dict_name" in data
            assert "version" in data
            assert "word_count" in data
            assert "words" in data
            
            # 验证词条结构
            for entry in data["words"]:
                assert "word" in entry
                assert "frequency" in entry
                assert "definition" in entry
                assert "inflections" in entry
                
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_word_count_matches(self):
        """验证单词数量符合预期"""
        from build_tiny_dict import build_tiny_dict
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # 构建10个单词
            limit = 10
            build_tiny_dict(output_path=temp_path, limit=limit)
            
            # 读取验证
            with open(temp_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            assert data["word_count"] == limit
            assert len(data["words"]) == limit
            
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_first_word_is_the(self):
        """验证第一个单词是 the"""
        from build_tiny_dict import read_coca_words, process_words
        
        words = read_coca_words(limit=1)
        results = process_words(words)
        
        assert results[0]["word"] == "the"
        assert results[0]["frequency"] == 1

    def test_dict_metadata(self):
        """验证词典元数据"""
        from build_tiny_dict import build_tiny_dict
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            build_tiny_dict(output_path=temp_path, limit=2)
            
            with open(temp_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            assert data["dict_name"] == "超级简陋小词典"
            assert data["version"] == "1.0"
            
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])