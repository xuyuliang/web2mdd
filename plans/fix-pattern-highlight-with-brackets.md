# 修复模式搜索高亮问题

## 问题描述

当用户输入包含方括号的模式（如 `*.[A]tric*`）时，高亮功能失效。
原因是 `_pattern_highlight()` 方法没有正确识别方括号占位符（`[A]`, `[AA]` 等），
导致构建的正则表达式尝试匹配字面的 `.[A]tric` 序列，而不是实际的单词内容。

## 需求

**核心规则**：通配符部分（`*`, `.`, `[xxx]`）不显示不高亮，只有字面字符才高亮。

| 元素 | 类型 | 高亮 |
|------|------|------|
| `*` | 通配符 | 否 |
| `.` | 单字符通配 | 否 |
| `[A]`, `[T]` | 元音/辅音占位符 | 否 |
| `[AA]`, `[TT]`, `[TTT]` | 多字符组合占位符 | 否 |
| `[abc]`, `[^s]` | 字符类/否定字符类 | 否 |
| `a-z`, `A-Z` | 字面字符 | **是** |

## 示例

| pattern | 匹配单词 | 期望输出 |
|---------|---------|---------|
| `*.[A]tric*` | `atricos` | `<span class="hl-literal">tric</span>` |
| `d*.[A]n` | `dinam` | `<span class="hl-literal">d</span>n` |
| `per*.[A]` | `period` | `<span class="hl-literal">peri</span>` |

## 当前代码分析

[`_pattern_highlight()`](app/main.py:206-241) 当前实现：

```python
for c in pattern:
    if c == '*':
        group_parts.append('(.*)')
        is_literal.append(False)
    elif c == '.':
        group_parts.append('(.)')
        is_literal.append(False)
    else:
        group_parts.append(f'({re.escape(c)})')
        is_literal.append(True)  # 问题在这里！[ A ] 都被当作字面量
```

当 pattern 是 `*.[A]tric*` 时：
- `[` 被当作字面量 → 正则 `(\[)`
- `A` 被当作字面量 → 正则 `(A)`
- `]` 被当作字面量 → 正则 `(\])`
- 生成的正则会尝试匹配包含 `.[A]tric` 字面序列的单词

## 解决方案

### 修改 `_pattern_highlight()` 方法

```python
@staticmethod
def _pattern_highlight(pattern: str, word: str) -> str:
    """将匹配到的单词中的用户输入字面量部分用深蓝色高亮
    
    通配符部分（*, ., [...]）不显示不高亮，
    只有字面字符才会被 <span class="hl-literal"> 包裹高亮。
    """
    # 分段并构建正则
    regex_parts = ['^']
    segments = []  # [(type, regex_part), ...]  type: 'wildcard' or 'literal'
    
    i = 0
    while i < len(pattern):
        c = pattern[i]
        
        if c == '*':
            # 任意字符序列通配符
            regex_parts.append('.*')
            segments.append(('wildcard', None))
            i += 1
            
        elif c == '.':
            # 单字符通配符
            regex_parts.append('.')
            segments.append(('wildcard', None))
            i += 1
            
        elif c == '[':
            # 字符类/占位符
            j = pattern.find(']', i + 1)
            if j == -1:
                # 无闭合括号，当作普通字符
                regex_parts.append(re.escape(c))
                segments.append(('literal', c))
                i += 1
            else:
                # 找到闭合括号，整个 [...] 是通配符
                bracket_content = pattern[i+1:j]
                # 将 GLOB 字符类转换为正则
                # [A] -> [aeiou], [^s] -> [^s], [aeo] -> [aeo]
                glob_to_regex = MDXReader._glob_bracket_to_regex(bracket_content)
                regex_parts.append(f'({glob_to_regex})')
                segments.append(('wildcard', glob_to_regex))
                i = j + 1
        else:
            # 字面字符
            regex_parts.append(f'({re.escape(c)})')
            segments.append(('literal', c))
            i += 1
    
    regex_parts.append('$')
    regex_str = ''.join(regex_parts)
    
    try:
        regex = re.compile(regex_str, re.IGNORECASE)
    except re.error:
        return word
    
    m = regex.match(word)
    if not m:
        return word
    
    # 构建 HTML：只有字面字符才高亮
    html_parts = []
    for idx, (seg_type, _) in enumerate(segments):
        if seg_type == 'literal':
            matched = m.group(idx + 1) or ''
            html_parts.append(f'<span class="hl-literal">{re.escape(matched)}</span>')
        # wildcard 类型不渲染任何内容
    
    return ''.join(html_parts)


@staticmethod
def _glob_bracket_to_regex(bracket_content: str) -> str:
    """将 GLOB 方括号内容转换为正则表达式字符类
    
    处理高级占位符：
    - 'A' -> '[aeiou]'
    - 'T' -> '[bcdfghjklmnpqrstvwxyz]'
    - 'AA' -> '(ai|ay|ee|...)'  # 注意：AA 可能匹配多个字符，用非捕获组
    - 'aeo' -> '[aeo]'  # 普通字符类保持不变
    """
    # 加载替换表
    preprocessor = get_preprocessor()
    
    if bracket_content in preprocessor.replacements:
        replacement = preprocessor.replacements[bracket_content]
        if isinstance(replacement, list):
            # 多字符组合：如 AA -> ["ai", "ay", ...]
            # 转换为正则：(ai|ay|ee|...)
            return '(?:' + '|'.join(replacement) + ')'
        else:
            # 单字符类：如 A -> "aeiou"
            return f'[{replacement}]'
    else:
        # 不是高级占位符，直接作为字符类
        return f'[{bracket_content}]'
```

### 关键改动

1. **识别 `[...]` 方括号**：扫描到 `[` 时，找到匹配的 `]`，整个方括号区域视为通配符
2. **查询替换表**：对于 `[A]`, `[AA]` 等高级占位符，查询 `glob替换表.json` 得到实际的正则表达式
3. **不渲染通配符**：在构建 HTML 时，只有 `literal` 类型的段才会被渲染（带高亮标签）
4. **`re.escape()` 用于高亮文本**：确保高亮部分中的特殊字符被正确转义

## 需要导入的内容

在 `main.py` 顶部添加：
```python
from app.word_freq import get_preprocessor
```

## 测试用例

```python
def test_pattern_highlight():
    """测试 _pattern_highlight 方法"""
    # 基本测试
    assert MDXReader._pattern_highlight('*.[A]tric*', 'atricos') == '<span class="hl-literal">tric</span>'
    assert MDXReader._pattern_highlight('d*.[A]n', 'dinar') == '<span class="hl-literal">d</span>n'
    assert MDXReader._pattern_highlight('hello', 'hello') == '<span class="hl-literal">hello</span>'
    assert MDXReader._pattern_highlight('*hello*', 'worldhellothere') == '<span class="hl-literal">hello</span>'
    assert MDXReader._pattern_highlight('.*.', 'cat') == ''  # 全是通配符，没有字面量
    assert MDXReader._pattern_highlight('*.[^s]tric*', 'atricos') == '<span class="hl-literal">tric</span>'
```
