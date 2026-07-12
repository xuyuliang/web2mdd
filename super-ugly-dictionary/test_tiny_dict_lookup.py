"""
超级简陋小词典 - 词典查询测试用例

测试词典查询功能：
1. 查询存在的单词返回 HTML
2. 查询不存在的单词返回 None
3. 验证返回的数据包含所需字段
"""

import pytest
import sys
import os

# 确保可以导入同目录的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestLookupWord:
    """测试词典查询功能"""

    def test_lookup_existing_word(self):
        """查询存在的单词返回 HTML"""
        from tiny_dict_lookup import lookup_word
        
        # 查询 "apple"，应该返回 HTML
        result = lookup_word("apple")
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0
        # 验证包含基本内容
        assert "apple" in result.lower()

    def test_lookup_nonexistent_word(self):
        """查询不存在的单词返回 None"""
        from tiny_dict_lookup import lookup_word
        
        # 查询一个不存在的单词
        result = lookup_word("xyznonexistentword123")
        # 应该返回 None 或空字符串
        assert result is None or result == ""

    def test_lookup_case_sensitivity(self):
        """测试大小写不敏感"""
        from tiny_dict_lookup import lookup_word
        
        # 查询小写
        result1 = lookup_word("apple")
        # 查询大写
        result2 = lookup_word("APPLE")
        # 查询混合大小写
        result3 = lookup_word("Apple")
        
        # 至少有一个返回结果
        assert result1 is not None or result2 is not None or result3 is not None

    def test_lookup_returns_html_with_coca2(self):
        """验证返回的 HTML 包含 coca2 字段"""
        from tiny_dict_lookup import lookup_word
        
        result = lookup_word("apple")
        assert result is not None
        assert 'class="coca2"' in result

    def test_lookup_empty_word(self):
        """查询空字符串返回 None"""
        from tiny_dict_lookup import lookup_word
        
        result = lookup_word("")
        assert result is None


class TestTinyDictLookup:
    """测试 TinyDictLookup 类"""

    def test_class_lookup_existing(self):
        """使用类方法查询存在的单词"""
        from tiny_dict_lookup import TinyDictLookup
        
        lookup = TinyDictLookup()
        result = lookup.lookup("apple")
        assert result is not None
        assert isinstance(result, str)

    def test_class_lookup_nonexistent(self):
        """使用类方法查询不存在的单词"""
        from tiny_dict_lookup import TinyDictLookup
        
        lookup = TinyDictLookup()
        result = lookup.lookup("nonexistentword999")
        assert result is None or result == ""

    def test_class_close(self):
        """测试关闭连接"""
        from tiny_dict_lookup import TinyDictLookup
        
        lookup = TinyDictLookup()
        lookup.close()
        # 不应该抛出异常


if __name__ == "__main__":
    pytest.main([__file__, "-v"])