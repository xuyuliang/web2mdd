"""
超级简陋小词典 - 数据提取测试用例

测试数据提取流程：
1. 读取前10个单词并提取数据
2. 验证输出格式正确
3. 验证形变词的词频与原词相同
"""

import pytest
import sys
import os

# 确保可以导入同目录的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestBuildTinyDict:
    """测试数据提取功能"""

    def test_read_coca_words(self):
        """测试读取 COCA 词表"""
        from build_tiny_dict import read_coca_words
        
        # 读取前10个单词
        words = read_coca_words(limit=10)
        
        assert len(words) == 10
        # 验证前几个单词
        assert words[0] == "the"
        assert words[1] == "be"

    def test_build_dict_entry(self):
        """测试构建词典条目"""
        from build_tiny_dict import build_dict_entry
        from tiny_dict_parser import extract_definition, extract_verb_forms, extract_noun_forms
        
        # 模拟 HTML
        test_html = '''
        <div class="coca2">苹果(98%)</div>
        <span class="frm">stormed, storming, storms</span>
        <div class="lemmas">keyboards[390]</div>
        '''
        
        # 构建条目
        entry = build_dict_entry("storm", 100, test_html)
        
        assert entry["word"] == "storm"
        assert entry["frequency"] == 100
        assert entry["definition"] == "苹果"
        assert "stormed" in entry["inflections"]
        assert "storming" in entry["inflections"]
        assert "storms" in entry["inflections"]

    def test_build_dict_entry_without_html(self):
        """测试没有 HTML 时返回基础条目"""
        from build_tiny_dict import build_dict_entry
        
        entry = build_dict_entry("testword", 50, None)
        
        assert entry["word"] == "testword"
        assert entry["frequency"] == 50
        assert entry["definition"] is None
        assert entry["inflections"] == []

    def test_extract_inflections_frequency(self):
        """测试形变词的词频与原词相同"""
        from build_tiny_dict import build_dict_entry
        
        # 模拟 HTML 包含动词变形
        test_html = '''
        <div class="coca2">走(100%)</div>
        <span class="frm">walked, walking, walks</span>
        '''
        
        # 构建条目
        entry = build_dict_entry("walk", 200, test_html)
        
        # 验证主词条
        assert entry["word"] == "walk"
        assert entry["frequency"] == 200
        assert entry["definition"] == "走"
        
        # 验证形变词的词频与原词相同（通过 inflections 字段）
        # 形变词应该在同一个条目中，frequency 相同
        assert len(entry["inflections"]) == 3

    def test_process_words_sample(self):
        """测试处理少量单词"""
        from build_tiny_dict import process_words
        
        # 处理前5个单词
        words = ["the", "be", "and", "of", "a"]
        results = process_words(words)
        
        # 验证返回数量
        assert len(results) <= 5
        
        # 验证格式
        for entry in results:
            assert "word" in entry
            assert "frequency" in entry
            assert "definition" in entry
            assert "inflections" in entry


class TestDataStructure:
    """测试数据结构"""

    def test_entry_structure(self):
        """验证条目结构"""
        from build_tiny_dict import build_dict_entry
        
        entry = build_dict_entry("test", 1, None)
        
        # 验证必需字段
        assert "word" in entry
        assert "frequency" in entry
        assert "definition" in entry
        assert "inflections" in entry
        
        # 验证类型
        assert isinstance(entry["word"], str)
        assert isinstance(entry["frequency"], int)
        assert isinstance(entry["definition"], (str, type(None)))
        assert isinstance(entry["inflections"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])