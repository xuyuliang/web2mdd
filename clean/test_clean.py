"""
测试运行器 - 从 test_data.txt 读取用例，验证 clean_anki_data.py 核心函数

用法： python clean\test_clean.py
"""
import sys, os
# 项目根目录加入 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from clean.clean_anki_data import extract_segmentation, extract_related_words, _collapse_chinese


def load_cases(path):
    """读取 test_data.txt，返回用例列表"""
    cases = []
    with open(path, 'r', encoding='utf-8') as f:
        lines = [l.rstrip('\n') for l in f if not l.startswith('#')]

    i = 0
    while i < len(lines):
        if lines[i].strip() == '':
            i += 1
            continue
        if i + 3 >= len(lines):
            break
        word = lines[i].strip()
        field3 = lines[i+1].replace('field3: ', '', 1).strip()
        seg = lines[i+2].replace('seg: ', '', 1).strip()
        rel = lines[i+3].replace('rel: ', '', 1).strip()
        cases.append({
            'word': word,
            'field3': field3,
            'expected_seg': seg if seg else None,
            'expected_related': [r.strip() for r in rel.split(';') if r.strip()] if rel else [],
        })
        i += 4
    return cases


def main():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_data.txt')
    cases = load_cases(path)

    print(f'共 {len(cases)} 个测试用例\n')

    ok = 0
    fail = 0
    for c in cases:
        word = c['word']
        field3 = c['field3']
        exp_seg = c['expected_seg']
        exp_rel = c['expected_related']

        field3 = _collapse_chinese(field3)

        seg, _ = extract_segmentation(field3, word)
        related = extract_related_words(field3, word)

        seg_ok = (seg == exp_seg) if exp_seg else (seg == '')
        rel_ok = (related == exp_rel)

        if seg_ok and rel_ok:
            ok += 1
            icon = '✅'
        else:
            fail += 1
            icon = '❌'

        seg_str = seg if seg else '(空)'
        rel_str = '; '.join(related) if related else '(空)'
        print(f'  {icon} {word}')
        print(f'      seg: {seg_str}')
        print(f'      rel: {rel_str}')

    print(f'\n通过: {ok}/{len(cases)}，失败: {fail}')
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
