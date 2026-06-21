"""
测试 readmdict.MDdict 的内存占用和功能兼容性
"""
import os
import sys
import gc
import types

# ⚠️ 先注入 lzo stub
_lzo_stub = types.ModuleType("lzo")
def _lzo_decompress(data, initSize=None, blockSize=None):
    raise RuntimeError("lzo decompress called unexpectedly")
_lzo_stub.decompress = _lzo_decompress
sys.modules["lzo"] = _lzo_stub

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_size(obj, seen=set()):
    """递归计算对象的内存占用"""
    rid = id(obj)
    if rid in seen:
        return 0
    seen.add(rid)
    
    size = sys.getsizeof(obj)
    if isinstance(obj, dict):
        size += sum(get_size(k, seen) + get_size(v, seen) for k, v in obj.items())
    elif hasattr(obj, '__dict__'):
        size += get_size(obj.__dict__, seen)
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
        size += sum(get_size(item, seen) for item in obj)
    return size


def test_mddict():
    """测试 MDdict 类的内存占用和基本功能"""
    print("=" * 60)
    print("MDdict 测试")
    print("=" * 60)
    
    mdx_path = r"F:\code\查词分词\web2mdd\The little dict\TLD.mdx"
    
    # 强制垃圾回收
    gc.collect()
    
    print(f"\n[1] 使用 MDdict 加载词典...")
    from readmdict import MDdict
    
    t0 = __import__('time').time()
    mdx = MDdict(mdx_path)
    load_time = __import__('time').time() - t0
    print(f"    加载耗时: {load_time:.1f}s")
    
    # 分析 MDdict 对象的内存占用
    print(f"\n[2] MDdict 对象内存占用:")
    print(f"    总大小: {get_size(mdx) / 1024 / 1024:.2f} MB")
    
    # 检查内部属性
    print(f"\n[3] MDdict 内部属性:")
    for attr in dir(mdx):
        if not attr.startswith('_'):
            continue
        val = getattr(mdx, attr)
        if isinstance(val, (list, dict, tuple)):
            print(f"    {attr}:")
            if isinstance(val, list):
                print(f"      长度: {len(val)}")
                if len(val) > 0:
                    sample = val[0]
                    if isinstance(sample, tuple) and len(sample) == 2:
                        print(f"      示例: ({type(sample[0]).__name__}, {type(sample[1]).__name__})")
                        if isinstance(sample[1], bytes):
                            print(f"      字节长度: {len(sample[1])}")
            elif isinstance(val, dict):
                print(f"      键数: {len(val)}")
    
    # 检查索引相关属性
    print(f"\n[4] 索引信息:")
    if hasattr(mdx, '_keys'):
        keys = mdx._keys
        print(f"    _keys 数量: {len(keys) if keys else 0}")
        if keys and len(keys) > 0:
            print(f"    _keys 内存: {get_size(keys) / 1024 / 1024:.2f} MB")
    
    if hasattr(mdx, '_record_offsets'):
        offsets = mdx._record_offsets
        print(f"    _record_offsets 数量: {len(offsets) if offsets else 0}")
        if offsets:
            print(f"    _record_offsets 内存: {get_size(offsets) / 1024 / 1024:.2f} MB")
    
    if hasattr(mdx, '_data_blocks'):
        blocks = mdx._data_blocks
        print(f"    _data_blocks 数量: {len(blocks) if blocks else 0}")
        if blocks:
            print(f"    _data_blocks 内存: {get_size(blocks) / 1024 / 1024:.2f} MB")
    
    # 测试基本功能
    print(f"\n[5] 功能测试:")
    
    # 测试 in 操作符
    test_word = "the"
    t0 = __import__('time').time()
    exists = test_word in mdx
    print(f"    '{test_word}' in mdx: {exists} (耗时 {(__import__('time').time()-t0)*1000:.1f}ms)")
    
    # 测试字典式访问
    test_word2 = "hello"
    t0 = __import__('time').time()
    if test_word2 in mdx:
        result = mdx[test_word2]
        print(f"    mdx['{test_word2}']: {len(result)} 条释义 (耗时 {(__import__('time').time()-t0)*1000:.1f}ms)")
        if result:
            first_def = result[0]
            print(f"    第一条: key='{first_def[0][:50]}...', value_len={len(first_def[1])}")
    else:
        print(f"    '{test_word2}' 不在词典中")
    
    # 测试大小写变体
    test_word3 = "The"
    print(f"\n    测试大小写变体:")
    for word in [test_word3, test_word3.lower(), test_word3.upper()]:
        exists = word in mdx
        print(f"      '{word}' in mdx: {exists}")
    
    # 测试不存在的词
    test_word4 = "xyznonexistent"
    exists = test_word4 in mdx
    print(f"      '{test_word4}' in mdx: {exists}")
    
    # 总体内存使用
    print(f"\n[6] 总体内存使用:")
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        print(f"    RSS: {mem_info.rss / 1024 / 1024:.2f} MB")
    except ImportError:
        print(f"    (psutil 未安装，跳过总体内存检测)")
    
    print(f"\n{'=' * 60}")
    print(f"测试完成")
    print(f"{'=' * 60}")


def test_mdx_comparison():
    """对比 MDX 类和 MDdict 类的内存占用"""
    print("\n" + "=" * 60)
    print("MDX vs MDdict 对比测试")
    print("=" * 60)
    
    mdx_path = r"F:\code\查词分词\web2mdd\The little dict\TLD.mdx"
    
    gc.collect()
    
    # 测试 MDX 类
    print(f"\n[1] 使用 MDX 类:")
    from readmdict import MDX
    t0 = __import__('time').time()
    mdx_obj = MDX(mdx_path, substyle=True)
    mdx_time = __import__('time').time() - t0
    
    mdx_size = get_size(mdx_obj) / 1024 / 1024
    key_list_size = get_size(mdx_obj._key_list) / 1024 / 1024 if hasattr(mdx_obj, '_key_list') else 0
    
    print(f"    加载耗时: {mdx_time:.1f}s")
    print(f"    总内存: {mdx_size:.2f} MB")
    print(f"    _key_list 内存: {key_list_size:.2f} MB")
    print(f"    _key_list 条目数: {len(mdx_obj._key_list) if hasattr(mdx_obj, '_key_list') and mdx_obj._key_list else 0}")
    
    # 测试 MDdict 类
    print(f"\n[2] 使用 MDdict 类:")
    from readmdict import MDdict
    t0 = __import__('time').time()
    mddict_obj = MDdict(mdx_path)
    mddict_time = __import__('time').time() - t0
    
    mddict_size = get_size(mddict_obj) / 1024 / 1024
    
    print(f"    加载耗时: {mddict_time:.1f}s")
    print(f"    总内存: {mddict_size:.2f} MB")
    
    # 对比
    print(f"\n[3] 对比:")
    print(f"    内存差异: {mdx_size - mddict_size:.2f} MB ({((mdx_size - mddict_size) / mdx_size * 100):.1f}%)")
    print(f"    速度差异: {mdx_time - mddict_time:.1f}s")


if __name__ == "__main__":
    test_mddict()
    test_mdx_comparison()