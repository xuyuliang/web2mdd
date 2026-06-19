import re

def _pattern_highlight(pattern: str, word: str) -> str:
    group_parts = []
    is_literal = []
    for c in pattern:
        if c == '*':
            group_parts.append('(.*)')
            is_literal.append(False)
        elif c == '.':
            group_parts.append('(.)')
            is_literal.append(False)
        else:
            group_parts.append(f'({re.escape(c)})')
            is_literal.append(True)
    regex_str = '^' + ''.join(group_parts) + '$'
    regex = re.compile(regex_str, re.IGNORECASE)

    m = regex.match(word)
    if not m:
        return word

    html_parts = []
    i = 0
    while i < len(is_literal):
        if is_literal[i]:
            literal_chars = []
            while i < len(is_literal) and is_literal[i]:
                literal_chars.append(m.group(i + 1))
                i += 1
            html_parts.append('<span class="hl-literal">' + "".join(literal_chars) + '</span>')
        else:
            matched = m.group(i + 1) or ''
            html_parts.append(matched)
            i += 1
    return ''.join(html_parts)

# Test cases
print('pl.d -> plod:', repr(_pattern_highlight('pl.d', 'plod')))
print('p.d -> pad:', repr(_pattern_highlight('p.d', 'pad')))
print('a* -> abc:', repr(_pattern_highlight('a*', 'abc')))
print('a* -> a:', repr(_pattern_highlight('a*', 'a')))
print('a.. -> able:', repr(_pattern_highlight('a..', 'able')))
print('ab* -> ab:', repr(_pattern_highlight('ab*', 'ab')))
print('ab* -> abc:', repr(_pattern_highlight('ab*', 'abc')))
print('.at -> cat:', repr(_pattern_highlight('.at', 'cat')))
