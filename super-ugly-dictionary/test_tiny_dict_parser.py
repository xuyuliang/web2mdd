"""
超级简陋小词典 - HTML 解析测试用例

测试从词典 HTML 中提取：
1. 最高频释义
2. 动词变形
3. 名词变形
"""

import pytest
import sys
import os

# 确保可以导入同目录的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestExtractDefinition:
    """测试提取最高频释义"""

    def test_extract_definition_basic(self):
        """从 coca2 标签提取第一个中文释义"""
        from tiny_dict_parser import extract_definition
        
        html = '<div class="coca2">苹果(98%)，珍宝(1%)，家伙(1%)</div>'
        result = extract_definition(html)
        assert result == "苹果"

    def test_extract_definition_single(self):
        """只有一个释义的情况"""
        from tiny_dict_parser import extract_definition
        
        html = '<div class="coca2">电脑(100%)</div>'
        result = extract_definition(html)
        assert result == "电脑"

    def test_extract_definition_no_coca2(self):
        """没有 coca2 标签时返回 None"""
        from tiny_dict_parser import extract_definition
        
        html = '<div class="other">some content</div>'
        result = extract_definition(html)
        assert result is None

    def test_extract_definition_empty_html(self):
        """空 HTML 时返回 None"""
        from tiny_dict_parser import extract_definition
        
        result = extract_definition("")
        assert result is None

    def test_extract_definition_none(self):
        """None 输入时返回 None"""
        from tiny_dict_parser import extract_definition
        
        result = extract_definition(None)
        assert result is None


class TestExtractVerbForms:
    """测试提取动词变形"""

    def test_extract_verb_forms_basic(self):
        """提取动词变形"""
        from tiny_dict_parser import extract_verb_forms
        
        html = '<span class="frm">stormed, storming, storms</span>'
        result = extract_verb_forms(html)
        assert result == ["stormed", "storming", "storms"]

    def test_extract_verb_forms_single(self):
        """只有一个变形的情况"""
        from tiny_dict_parser import extract_verb_forms
        
        html = '<span class="frm">walked</span>'
        result = extract_verb_forms(html)
        assert result == ["walked"]

    def test_extract_verb_forms_no_frm(self):
        """没有 frm 标签时返回空列表"""
        from tiny_dict_parser import extract_verb_forms
        
        html = '<div class="other">some content</div>'
        result = extract_verb_forms(html)
        assert result == []

    def test_extract_verb_forms_empty(self):
        """空 HTML 时返回空列表"""
        from tiny_dict_parser import extract_verb_forms
        
        result = extract_verb_forms("")
        assert result == []

    def test_extract_verb_forms_none(self):
        """None 输入时返回空列表"""
        from tiny_dict_parser import extract_verb_forms
        
        result = extract_verb_forms(None)
        assert result == []


class TestExtractNounForms:
    """测试提取名词变形"""

    def test_extract_noun_forms_basic(self):
        """提取名词变形"""
        from tiny_dict_parser import extract_noun_forms
        
        html = '<div class="lemmas">keyboards[390]</div>'
        result = extract_noun_forms(html)
        assert result == ["keyboards"]

    def test_extract_noun_forms_multiple(self):
        """提取多个名词变形"""
        from tiny_dict_parser import extract_noun_forms
        
        html = '<div class="lemmas">children[123] boxes[456]</div>'
        result = extract_noun_forms(html)
        assert result == ["children", "boxes"]

    def test_extract_noun_forms_no_lemmas(self):
        """没有 lemmas 标签时返回空列表"""
        from tiny_dict_parser import extract_noun_forms
        
        html = '<div class="other">some content</div>'
        result = extract_noun_forms(html)
        assert result == []

    def test_extract_noun_forms_empty(self):
        """空 HTML 时返回空列表"""
        from tiny_dict_parser import extract_noun_forms
        
        result = extract_noun_forms("")
        assert result == []

    def test_extract_noun_forms_none(self):
        """None 输入时返回空列表"""
        from tiny_dict_parser import extract_noun_forms
        
        result = extract_noun_forms(None)
        assert result == []


class TestExtractAll:
    """测试完整提取功能"""

    def test_extract_all_with_all_fields(self):
        """测试包含所有字段的 HTML"""
        from tiny_dict_parser import extract_definition, extract_verb_forms, extract_noun_forms
        
        html = '''
        <div class="coca2">苹果(98%)，珍宝(1%)</div>
        <span class="frm">stormed, storming, storms</span>
        <div class="lemmas">keyboards[390]</div>
        '''
        
        definition = extract_definition(html)
        verb_forms = extract_verb_forms(html)
        noun_forms = extract_noun_forms(html)
        
        assert definition == "苹果"
        assert verb_forms == ["stormed", "storming", "storms"]
        assert noun_forms == ["keyboards"]

    def test_extract_all_with_partial_fields(self):
        """测试只包含部分字段的 HTML"""
        from tiny_dict_parser import extract_definition, extract_verb_forms, extract_noun_forms
        
        html = '<div class="coca2">电脑(100%)</div>'
        
        definition = extract_definition(html)
        verb_forms = extract_verb_forms(html)
        noun_forms = extract_noun_forms(html)
        
        assert definition == "电脑"
        assert verb_forms == []
        assert noun_forms == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])