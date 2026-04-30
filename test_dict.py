import time, struct, lzo, zlib
t0 = time.time()
from readmdict import MDX
mdx = MDX('The little dict/TLD.mdx', substyle=True)
print('init', '%.1fs'%(time.time()-t0))
print('编码:', repr(mdx._encoding))

kl = mdx._key_list
print(f'kl[0]: {kl[0]}')
print(f'kl[1]: {kl[1]}')

# 记录块信息
f = open('The little dict/TLD.mdx', 'rb')
f.seek(mdx._record_block_offset)
num_blocks = mdx._read_number(f)
num_entries = mdx._read_number(f)
info_size = mdx._read_number(f)
block_size = mdx._read_number(f)

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
comp0 = open('The little dict/TLD.mdx', 'rb')
comp0.seek(data_offset)
compressed = comp0.read(block_infos[0][0])
comp0.close()

bt = compressed[:4]
print(f'块0类型: {bt}, 压缩大小: {block_infos[0][0]}, 解压大小: {block_infos[0][1]}')

if bt == b'\x00\x00\x00\x00': dec = compressed[8:]
elif bt == b'\x01\x00\x00\x00': dec = lzo.decompress(b'\xf0' + struct.pack('>I', block_infos[0][1]) + compressed[8:])
elif bt == b'\x02\x00\x00\x00': dec = zlib.decompress(compressed[8:])

print(f'解压大小: {len(dec)}, 预期: {block_infos[0][1]}, 匹配: {len(dec)==block_infos[0][1]}')

# 提取第一个记录
rec0 = dec[kl[0][0]:kl[1][0]]
print(f'rec0: {repr(rec0[:100])}')

# 测试查找 "hello" - 只检查前5000个词条
found = []
for i in range(min(5000, len(kl))):
    w = kl[i][1].decode('utf-8', errors='ignore').strip()
    if 'hello' in w.lower():
        found.append((i, w, kl[i][0]))
        if len(found) >= 3:
            break
print(f'前5000中找到hello相关: {found}')

# 测试完全遍历查 "hello" - 只检查 key_list 中间部分
# 二分法找 hello
import bisect
words = [kl[i][1].decode('utf-8', errors='ignore').strip() for i in range(len(kl))]
# 只在样本中搜索, 太慢
print('跳过完整遍历')

# 尝试用 items()
print('\n测试 items() 读取...')
it = mdx.items()
for i in range(3):
    k, v = next(it)
    print(f'  item[{i}]: key={repr(k[:50])}, val={repr(v[:80])}')

print(f'\n总耗时: {time.time()-t0:.1f}s')
