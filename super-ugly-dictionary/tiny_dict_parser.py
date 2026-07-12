"""
超级简陋小词典 - HTML 解析模块

从词典 HTML 中提取：
1. 最高频释义 - 从 <div class="coca2"> 提取
2. 动词变形 - 从 <span class="frm"> 提取
3. 名词变形 - 从 <div class="lemmas"> 提取
"""

import re
from typing import Optional


def extract_definition(html: str) -> Optional[str]:
    """
    从 HTML 中提取最高频释义
    
    从 <div class="coca2">苹果(98%)，珍宝(1%)</div> 提取 "苹果"
    
    Args:
        html: 词典返回的 HTML 内容
        
    Returns:
        最高频释义字符串，或 None（未找到时）
    """
    if not html:
        return None
    
    # 查找 <div class="coca2"> 标签
    # 注意：内容中可能包含 HTML 标签如 <font>
    pattern = r'<div class="coca2">(.*?)</div>'
    match = re.search(pattern, html, re.DOTALL)
    
    if not match:
        return None
    
    # 获取标签内容
    content = match.group(1)
    
    # 提取第一个中文释义（取第一个逗号或顿号前的内容）
    # 去除 HTML 标签如 <font color="orangered">98%</font>
    content = re.sub(r'<[^>]+>', '', content)
    
    # 按逗号或顿号分割，取第一个
    parts = re.split(r'[,，]', content)
    if parts:
        # 去除百分比部分，如 "苹果(98%)" -> "苹果"
        definition = re.sub(r'\([^)]*\)', '', parts[0]).strip()
        if definition:
            return definition
    
    return None


def extract_verb_forms(html: str) -> list[str]:
    """
    从 HTML 中提取动词变形
    
    从 <span class="frm">stormed, storming, storms</span> 提取 
    ["stormed", "storming", "storms"]
    
    Args:
        html: 词典返回的 HTML 内容
        
    Returns:
        动词变形列表
    """
    if not html:
        return []
    
    # 查找 <span class="frm"> 标签
    pattern = r'<span class="frm">([^<]+)</span>'
    match = re.search(pattern, html)
    
    if not match:
        return []
    
    # 提取变形词列表
    content = match.group(1)
    forms = [f.strip() for f in content.split(',') if f.strip()]
    
    return forms


def extract_noun_forms(html: str) -> list[str]:
    """
    从 HTML 中提取名词变形
    
    从 <div class="lemmas">keyboards[390]</div> 提取 ["keyboards"]
    支持多个变形：<div class="lemmas">children[123] boxes[456]</div>
    
    Args:
        html: 词典返回的 HTML 内容
        
    Returns:
        名词变形列表
    """
    if not html:
        return []
    
    # 查找 <div class="lemmas"> 标签，提取 [ 之前的内容
    pattern = r'<div class="lemmas">([^<]+)</div>'
    match = re.search(pattern, html)
    
    if not match:
        return []
    
    # 提取内容
    content = match.group(1)
    
    # 提取每个变形词（[ 之前的内容）
    # 格式：keyboards[390] boxes[456]
    forms = []
    parts = content.split()
    for part in parts:
        # 取 [ 之前的内容
        lemma = part.split('[')[0].strip()
        if lemma:
            forms.append(lemma)
    
    return forms


def extract_all(html: str) -> dict:
    """
    提取所有需要的数据
    
    Args:
        html: 词典返回的 HTML 内容
        
    Returns:
        包含 definition, verb_forms, noun_forms 的字典
    """
    return {
        "definition": extract_definition(html),
        "verb_forms": extract_verb_forms(html),
        "noun_forms": extract_noun_forms(html),
    }


def extract_definition_fallback(html: str) -> Optional[str]:
    """
    从 <span class="dcn"> 提取备用释义
    
    当 <div class="coca2"> 不存在时使用
    从 <span class="dcn">通讯，传达；相通</span> 提取 "通讯"
    
    Args:
        html: 词典返回的 HTML 内容
        
    Returns:
        备用释义字符串，或 None（未找到时）
    """
    if not html:
        return None
    
    # 查找 <span class="dcn"> 标签
    pattern = r'<span class="dcn">(.*?)</span>'
    match = re.search(pattern, html, re.DOTALL)
    
    if not match:
        return None
    
    # 获取标签内容
    content = match.group(1)
    
    # 去除 HTML 标签
    content = re.sub(r'<[^>]+>', '', content)
    
    # 按逗号或分号分割，取第一个
    # 支持多种分隔符：逗号、顿号、分号
    parts = re.split(r'[,，;；]', content)
    if parts:
        definition = parts[0].strip()
        if definition:
            return definition
    
    return None


if __name__ == "__main__":
    # 简单测试
    test_html = '''
    <div class="coca2">苹果(98%)，珍宝(1%)，家伙(1%)</div>
    <span class="frm">stormed, storming, storms</span>
    <div class="lemmas">keyboards[390]</div>
    '''
    
    result = extract_all(test_html)
    print(result)