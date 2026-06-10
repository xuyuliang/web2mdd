"""
数据清洗程序 - 从 mydata.anki2 中提取单词切分和相关单词

根据 plans/数据清洗计划.txt 实现：
- 第0项 = 单词本身
- 第3项 = 切分结果 + 相关单词

清洗逻辑：
1. 从 flds 第0项读出单词
2. 从第3项逐个字符扫描，过滤非字母符号，
   直到累计的纯字母字符串包含目标单词 -> 提取切分结果
3. 从第3项剩余文本中提取其他英文单词作为相关词

用法：
    python clean_anki_data.py
    python clean_anki_data.py --limit 100  (只处理前100条，用于测试)
"""
import sqlite3
import csv
import re
import os
import argparse
import html

# 数据库路径
ANKI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mydata.anki2")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plains", "cleaned_data.csv")


def is_english(ch: str) -> bool:
    """判断是否为英文字母（中文字符的 isalpha() 也是 True，必须排除）"""
    return ('a' <= ch <= 'z') or ('A' <= ch <= 'Z')


# 匹配 字母.字母[.字母...] 的模式
DOTTED_PATTERN = re.compile(r'[a-zA-Z]+(?:\.[a-zA-Z]+){1,}')

# HTML 标签剥离正则
HTML_TAG_RE = re.compile(r'<[^>]+>')


def clean_html(text: str) -> str:
    """
    清理 HTML 内容，保留文字部分：
    1. 解码 HTML 实体（&nbsp; > < 等）
    2. 将 HTML 标签替换为空格（防止标签前后单词合并）
    3. 规范化空白字符
    """
    # 解码 HTML 实体
    text = html.unescape(text)

    # 将 HTML 标签替换为空格（而非直接删除），防止 ly<br>re 变成 lyre
    text = HTML_TAG_RE.sub(' ', text)

    # 规范化空白：多个空格/制表符合并为一个空格
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def extract_segmentation(field3: str, word: str) -> tuple[str, str]:
    """
    从第3项中提取单词的切分结果和剩余文本。

    策略（优先级从高到低）：
    1. 先找带点号模式（如 re.spec.tive.ly），去点后匹配 word
    2. 如果没找到，用逐字符扫描法（兼容无点号的情况）

    返回: (切分结果, 剩余文本)
    """
    word_lower = word.lower().strip()
    if not word_lower:
        return ("", field3)

    # 策略1：找带点号切分模式
    dotted_matches = DOTTED_PATTERN.findall(field3)
    for dm in dotted_matches:
        if dm.replace('.', '').lower() == word_lower:
            # 找到精确匹配的切分
            remaining = _find_remaining_after(field3, dm)
            return (dm, remaining)

    # 策略2：逐字符扫描法
    raw_accum = ""        # 原始字符累计
    letter_accum = ""     # 只含字母的累计
    scan_chars = []       # 存储 (原始字符, 是否英文字母)
    found_idx = -1

    for ch in field3:
        eng = is_english(ch)
        scan_chars.append((ch, eng))
        raw_accum += ch
        if eng:
            letter_accum += ch
            # letter_accum 中是否已包含 word？
            pos = letter_accum.lower().find(word_lower)
            if pos != -1:
                found_idx = len(letter_accum)
                break

    if found_idx == -1:
        return ("", field3)

    # 映射 letter_accum 中的位置到 raw_accum 中的位置
    letter_to_raw = []
    for raw_idx, (ch, eng) in enumerate(scan_chars):
        if eng:
            letter_to_raw.append(raw_idx)

    # 找 word 在 letter_accum 中的起始位置 pos，映射回 raw
    pos = letter_accum.lower().find(word_lower)
    if pos >= len(letter_to_raw):
        return ("", field3)

    raw_start = letter_to_raw[pos]
    raw_end = letter_to_raw[found_idx - 1] + 1

    raw_segment = raw_accum[raw_start:raw_end]

    # 将非字母替换为 .
    seg_chars = []
    for ch in raw_segment:
        if is_english(ch):
            seg_chars.append(ch)
        else:
            if seg_chars and seg_chars[-1] != '.':
                seg_chars.append('.')

    while seg_chars and seg_chars[-1] == '.':
        seg_chars.pop()

    segmentation = ''.join(seg_chars)
    remaining = field3[raw_end:]

    return (segmentation, remaining)


def _find_remaining_after(field3: str, matched_text: str) -> str:
    """找到 matched_text 在 field3 中第一次出现的位置之后的内容"""
    idx = field3.find(matched_text)
    if idx == -1:
        return field3
    return field3[idx + len(matched_text):]


def _strip_phonetic(text: str) -> str:
    """去掉 [...] 音标内容，因为音标中的字母会被误认为英文单词"""
    return re.sub(r'\[[^\]]*\]', '', text)


def extract_related_words(text: str, word: str) -> list[str]:
    """
    从文本中提取相关单词。

    双策略：
    1. 优先找带点号模式（如 de.fect, dis.pose），去点后验证——这是最可靠的
    2. 回退策略：提取纯英文字母单词（长度≥4），排除主词
       用于处理相关词不带点号的情况（如 coral → corral, carol）

    注意：传入的 text 应是已经 clean_html() 处理过的纯文本。
    """
    word_lower = word.lower().strip()

    # ===== 策略1：带点号匹配 =====
    dotted_pattern = re.compile(r'[a-zA-Z]+(?:\.[a-zA-Z]+){1,}')
    dotted_matches = dotted_pattern.findall(text)

    related = []
    for m in dotted_matches:
        clean = m.replace('.', '').lower()
        if clean != word_lower and len(clean) >= 4:
            if m not in related:
                related.append(m)

    # ===== 策略2：纯单词回退 =====
    # 收集所有带点号匹配中的碎片（如 re.spec.tive → spec, tive）
    # 这些碎片不应被当作相关词
    dotted_components = set()
    for dm in dotted_matches:
        for part in dm.split('.'):
            if len(part) >= 4:
                dotted_components.add(part.lower())

    # 常见词源/注释噪声词（不是真正的相关词）
    NOISE_WORDS = {
        'vulgar', 'latin', 'greek', 'french', 'german', 'spanish',
        'italian', 'russian', 'arabic', 'hebrew', 'sanskrit',
        'prefix', 'suffix', 'synonym', 'antonym', 'plural',
        'singular', 'literally', 'figurative', 'ultimately',
    }

    # 剥离音标，避免 [ˈkɔrəl] 中的字母被误提取
    no_phonetic = _strip_phonetic(text)
    # 提取所有纯英文字母单词（4个字母以上）
    plain_words = re.findall(r'[a-zA-Z]{4,}', no_phonetic)

    for pw in plain_words:
        pw_lower = pw.lower()
        # 过滤条件：
        # 1. 不是主词本身
        # 2. 不是点号切分中的碎片（如 spec, tive, sover, eign）
        # 3. 不是常见词源噪声词
        # 4. 没有被带点号形式覆盖
        if pw_lower == word_lower:
            continue
        if pw_lower in dotted_components:
            continue
        if pw_lower in NOISE_WORDS:
            continue
        already_covered = False
        for r in related:
            if r.replace('.', '').lower() == pw_lower:
                already_covered = True
                break
        if not already_covered:
            if pw not in related:
                related.append(pw)

    return related


def clean_data(limit: int = None):
    """主清洗逻辑"""
    conn = sqlite3.connect(ANKI_PATH)
    cursor = conn.cursor()

    # 读取所有 notes
    query = 'SELECT id, flds FROM notes'
    cursor.execute(query)
    all_notes = cursor.fetchall()
    conn.close()

    total = len(all_notes)
    if limit:
        all_notes = all_notes[:limit]

    results = []
    stats = {
        "total": 0,
        "with_segmentation": 0,
        "with_related": 0,
        "no_segmentation": 0,
    }

    for i, (nid, flds) in enumerate(all_notes):
        parts = flds.split('\x1f')
        if len(parts) < 4:
            # 不足4个字段，跳过
            continue

        word = parts[0].strip()
        field3_raw = parts[3]

        stats["total"] += 1

        # 先清理 HTML：解码实体 + 剥离标签，只看纯文本内容
        field3 = clean_html(field3_raw)

        # 提取切分结果
        segmentation, remaining = extract_segmentation(field3, word)

        # 提取相关单词
        related_words = extract_related_words(field3, word)

        # 如果从切分提取中未找到，也可以从剩余文本和历史探索中找更多相关词
        if remaining.strip():
            more_related = extract_related_words(remaining, word)
            for r in more_related:
                if r not in related_words:
                    related_words.append(r)

        row = {
            "word": word,
            "segmentation": segmentation,
            "related_words": "; ".join(related_words),
        }

        if segmentation:
            stats["with_segmentation"] += 1
        else:
            stats["no_segmentation"] += 1

        if related_words:
            stats["with_related"] += 1

        results.append(row)

        if (i + 1) % 200 == 0:
            print(f"  进度: {i+1}/{total if not limit else limit}")

    # 输出清洗结果
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["word", "segmentation", "related_words"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\n清洗完成！共处理 {stats['total']} 条数据")
    print(f"  有切分: {stats['with_segmentation']} ({stats['with_segmentation']/stats['total']*100:.1f}%)")
    print(f"  无切分: {stats['no_segmentation']} ({stats['no_segmentation']/stats['total']*100:.1f}%)")
    print(f"  有相关词: {stats['with_related']} ({stats['with_related']/stats['total']*100:.1f}%)")
    print(f"\n输出文件: {OUTPUT_PATH}")

    # 打印一些样例
    print("\n--- 前10条样例 ---")
    for r in results[:10]:
        print(f"  {r['word']:20s} -> seg: {r['segmentation']:25s} related: {r['related_words']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从 Anki 数据库清洗提取切分数据")
    parser.add_argument("--limit", type=int, default=None,
                        help="只处理前 N 条（用于测试）")
    args = parser.parse_args()
    clean_data(limit=args.limit)
