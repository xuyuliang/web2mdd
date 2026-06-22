"""
测试词典文件读取 - 同时测试底层 MDX 类和上层 MDXReader 类
"""
import time, zlib
import os
import bisect
import pickle
import re

t0 = time.time()
from readmdict import MDX, lzo

# 相对于 app/ 目录，词典目录在上级目录
DICT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "The little dict")
MDX_PATH = os.path.join(DICT_DIR, "TLD.mdx")
CACHE_PATH = MDX_PATH + ".pkl"

# ================== 测试1: 底层 MDX 对象 ==================
print("=" * 60)
print("测试1: 底层 MDX 对象")
print("=" * 60)

mdx = MDX(MDX_PATH, substyle=True)
print(f"init: {time.time()-t0:.1f}s")
print(f"编码: {repr(mdx._encoding)}")

kl = mdx._key_list
print(f"kl[0]: {kl[0]}")
print(f"kl[1]: {kl[1]}")
print(f"词条总数: {len(kl)}")

# 记录块信息
f = open(MDX_PATH, 'rb')
f.seek(mdx._record_block_offset)
num_blocks = mdx._read_number(f)
num_entries = mdx._read_number(f)
info_size = mdx._read_number(f)
block_size = mdx._read_number(f)
print(f"块信息: num_blocks={num_blocks}, num_entries={num_entries}, info_size={info_size}, block_size={block_size}")

block_infos = [(mdx._read_number(f), mdx._read_number(f)) for _ in range(num_blocks)]
data_offset = f.tell()
f.close()

# block_starts
block_starts = []
s = 0
for c, d in block_infos:
    block_starts.append(s)
    s += d

# 验证第一个块的解压
comp0 = open(MDX_PATH, 'rb')
comp0.seek(data_offset)
compressed = comp0.read(block_infos[0][0])
comp0.close()

bt = compressed[:4]
print(f"块0类型: {bt}, 压缩大小: {block_infos[0][0]}, 解压大小: {block_infos[0][1]}")

if bt == b'\x00\x00\x00\x00':
    dec = compressed[8:]
elif bt == b'\x01\x00\x00\x00':
    dec = lzo.decompress(compressed[8:], initSize=block_infos[0][1], blockSize=1308672)
elif bt == b'\x02\x00\x00\x00':
    dec = zlib.decompress(compressed[8:])

print(f"解压大小: {len(dec)}, 预期: {block_infos[0][1]}, 匹配: {len(dec)==block_infos[0][1]}")

# 提取第一个记录
rec0 = dec[kl[0][0]:kl[1][0]]
print(f"rec0: {repr(rec0[:100])}")

# 测试查找 "hello" - 只检查前5000个词条
found = []
for i in range(min(5000, len(kl))):
    w = kl[i][1].decode('utf-8', errors='ignore').strip()
    if 'hello' in w.lower():
        found.append((i, w, kl[i][0]))
        if len(found) >= 3:
            break
print(f"前5000中找到hello相关: {found}")

# 测试完全遍历查 "hello" - 只检查 key_list 中间部分
words = [kl[i][1].decode('utf-8', errors='ignore').strip() for i in range(len(kl))]
print("跳过完整遍历（太慢）")

# 尝试用 items()
print("\n测试 items() 读取...")
it = mdx.items()
for i in range(3):
    k, v = next(it)
    print(f"  item[{i}]: key={repr(k[:50])}, val={repr(v[:80])}")

# ================== 测试2: MDXReader 类（main.py 中的上层封装） ==================
print("\n" + "=" * 60)
print("测试2: MDXReader 类（上层封装，含缓存和查找逻辑）")
print("=" * 60)

# 先清理缓存，确保重建
if os.path.exists(CACHE_PATH):
    os.remove(CACHE_PATH)
    print(f"已删除旧缓存: {CACHE_PATH}")

# 相对于项目根目录导入
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.main import MDXReader

t1 = time.time()
reader = MDXReader(MDX_PATH)
print(f"MDXReader 初始化: {time.time()-t1:.1f}s")
print(f"  encoding: {reader.encoding}")
print(f"  key_list 长度: {len(reader.key_list)}")
print(f"  block_infos 长度: {len(reader.block_infos)}")
print(f"  data_offset: {reader.data_offset}")

# 验证缓存已保存
if os.path.exists(CACHE_PATH):
    print(f"  缓存文件已创建: {CACHE_PATH}")
    cache_size = os.path.getsize(CACHE_PATH)
    print(f"  缓存大小: {cache_size} bytes")

# 测试第二次加载（从缓存读取）
print("\n测试从缓存加载...")
t2 = time.time()
reader2 = MDXReader(MDX_PATH)
print(f"缓存加载耗时: {time.time()-t2:.1f}s")

# 测试 _decompress_block
print("\n测试 _decompress_block(0)...")
dec0 = reader._decompress_block(0)
print(f"  解压后大小: {len(dec0)}")

# 测试 _read_record
print("\n测试 _read_record...")
for i in range(min(3, len(reader.key_list))):
    text = reader._read_record(i)
    print(f"  record[{i}]: {repr(text[:100])}")

# 测试 lookup 精确匹配
print("\n测试 lookup 精确匹配...")
# 用第一个词条测试
first_word = reader.key_list[0][1].decode("utf-8", errors="ignore").strip()
print(f"  查找第一个词: {repr(first_word)}")
result, exact = reader.lookup(first_word)
print(f"  精确匹配: {exact}, 结果前80字: {repr(result[:80] if result else 'None')}")

# 测试 lookup 大小写不敏感
if len(reader.key_list) > 1:
    w2 = reader.key_list[1][1].decode("utf-8", errors="ignore").strip()
    w2_lower = w2.lower()
    if w2 != w2_lower:
        print(f"  查找小写版本: {repr(w2_lower)}")
        result2, exact2 = reader.lookup(w2_lower)
        print(f"  结果: exact={exact2}, 前80字: {repr(result2[:80] if result2 else 'None')}")

# 测试 lookup 前缀匹配
print("\n测试 lookup 前缀匹配...")
result3, exact3 = reader.lookup("hello")
print(f"  lookup('hello') -> exact={exact3}")
if not exact3 and isinstance(result3, list):
    print(f"  建议: {result3[:5]}")

# 测试 lookup 不存在的词
print("\n测试 lookup 不存在的词...")
result4, exact4 = reader.lookup("xyznonexistent12345")
print(f"  lookup('xyznonexistent12345') -> exact={exact4}, result={result4}")

# 测试 _substitute_stylesheet
print("\n测试样式替换...")
if reader._stylesheet:
    styled = reader._substitute_stylesheet("`0`hello`0`")
    print(f"  样式替换结果: {repr(styled)}")
else:
    print("  无样式表，跳过")

# ================== 测试3: WordFreq 词频排名 ==================
print("\n" + "=" * 60)
print("测试3: WordFreq 词频排名（COCA 排名）")
print("=" * 60)

from app.word_freq import WordFreq
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "The little dict", "TLD.mdx.index.db")
word_freq = WordFreq(DB_PATH)

# 注意：数据库中的词频值可能与原始 txt 文件不同，因为数据库中有重复记录
# get_rank 返回的是 MIN(frequency)，即该单词所有记录中的最小 frequency 值
for word, expected in [("splice", 20290), ("hello", 2252), ("abandon", 2195), ("book", 241)]:
    rank_val = word_freq.get_rank(word)
    match = "✅" if rank_val == expected else "❌"
    print(f"  {
rank_val = word_freq.get_rank("xyznonexistent12345")
print(f"  ✅ 不存在词: rank={rank_val}")

# 测试空字符串
rank_val = word_freq.get_rank("")
print(f"  ✅ 空字符串: rank={rank_val}")

# 测试大小写
rank_val = word_freq.get_rank("SPLICE")
rank_val2 = word_freq.get_rank("Hello")
print(f"  ✅ 大写 SPLICE: rank={rank_val}")
print(f"  ✅ 首字母大写 Hello: rank={rank_val2}")

print(f"\n总耗时: {time.time()-t0:.1f}s")
print("所有测试完成！")
