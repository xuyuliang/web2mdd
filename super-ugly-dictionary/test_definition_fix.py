"""
步骤6：数据补救 - 测试用例

测试从 <span class="dcn"> 提取释义
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestExtractDefinitionFallback:
    """测试备用释义提取"""

    def test_extract_definition_fallback_basic(self):
        """从 dcn 标签提取第一个释义"""
        from tiny_dict_parser import extract_definition_fallback
        
        html = '<span class="dcn">通讯，传达；相通；交流；感染</span>'
        result = extract_definition_fallback(html)
        assert result == "通讯"

    def test_extract_definition_fallback_semicolon(self):
        """使用分号分隔的情况"""
        from tiny_dict_parser import extract_definition_fallback
        
        html = '<span class="dcn">通讯；传达；相通</span>'
        result = extract_definition_fallback(html)
        assert result == "通讯"

    def test_extract_definition_fallback_no_dcn(self):
        """没有 dcn 标签时返回 None"""
        from tiny_dict_parser import extract_definition_fallback
        
        html = '<div class="other">some content</div>'
        result = extract_definition_fallback(html)
        assert result is None

    def test_extract_definition_fallback_empty(self):
        """空 HTML 时返回 None"""
        from tiny_dict_parser import extract_definition_fallback
        
        result = extract_definition_fallback("")
        assert result is None

    def test_extract_definition_fallback_none(self):
        """None 输入时返回 None"""
        from tiny_dict_parser import extract_definition_fallback
        
        result = extract_definition_fallback(None)
        assert result is None


class TestFixNullDefinitions:
    """测试修复空释义"""

    def test_fix_word_with_dcn(self):
        """测试有 dcn 标签的单词"""
        from tiny_dict_parser import extract_definition, extract_definition_fallback
        
        # 模拟 HTML：有 dcn 但没有 coca2
        html = '<span class="dcn">通讯，传达；相通</span>'
        
        # 先尝试从 coca2 提取
        definition = extract_definition(html)
        
        # 如果为 None，再从 dcn 提取
        if definition is None:
            definition = extract_definition_fallback(html)
        
        assert definition == "通讯"

    def test_fix_word_without_dcn(self):
        """测试没有 dcn 标签的单词"""
        from tiny_dict_parser import extract_definition, extract_definition_fallback
        
        # 模拟 HTML：既没有 coca2 也没有 dcn
        html = '<div class="other">some content</div>'
        
        definition = extract_definition(html)
        if definition is None:
            definition = extract_definition_fallback(html)
        
        assert definition is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])