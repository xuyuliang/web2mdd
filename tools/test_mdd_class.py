"""
测试 readmdict.MDD 类的内存占用和功能
"""
import os
import sys
import gc
import types

# 先注入 lzo stub
_lzo_stub = types.ModuleType("lzo")
def _lzo_decompress(data, initSize=None, blockSize=None):
    raise RuntimeError("lzo decompress called unexpectedly")
_lzo_stub.decompress = _lzo_decompress
sys.modules["lzo"] = _lzo_stub

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


def test_mdd():
    """测试 MDD 类"""
    print("=" * 60)
    print("MDD 类测试")
    print("=" * 60)
    
    mdx_path = r"F:\code\查词分词\web2mdd\The little dict\TLD.mdx"
    
    gc.collect()
    
    print(f"\n[1] 使用 MDD 加载词典...")
    from readmdict import MDD
    
    t0 = __import__('time').time()
    mdd = MDD(mdx_path)
    load_time = __import__('time').time() - t0
    print(f"    加载耗时: {load_time:.1f}s")
    
    # 分析内存占用
    print(f"\n[2] MDD 对象内存占用:")
    print(f"    总大小: {get_size(mdd) / 1024 / 1024:.2f} MB")
    
    # 检查内部属性
    print(f"\n[3] MDD 内部属性:")
    for attr in ['_key_list', '_value_list', '_records', '_index', 'words']:
        if hasattr(mdd, attr):
            val = getattr(mdd, attr)
            if isinstance(val, (list, dict)):
                print(f"    {attr}: 长度={len(val)}, 内存={get_size(val)/1024/1024:.2f} MB")
            else:
                print(f"    {attr}: {type(val).__name__}")
    
    # 测试基本功能
    print(f"\n[4] 功能测试:")
    
    # 测试 in 操作符
    test_word = "the"
    t0 = __import__('time').time()
    exists = test_word in mdd
    print(f"    '{test_word}' in mdd: {exists} (耗时 {(__import__('time').time()-t0)*1000:.1f}ms)")
    
    # 测试字典式访问
    test_word2 = "hello"
    t0 = __import__('time').time()
    if test_word2 in mdd:
        result = mdd[test_word2]
        print(f"    mdd['{test_word2}']: {type(result)} (耗时 {(__import__('time').time()-t0)*1000:.1f}ms)")
    else:
        print(f"    '{test_word2}' 不在词典中")
    
    # 测试查询
    t0 = __import__('time').time()
    definition = mdd.get(test_word)
    print(f"    mdd.get('{test_word}'): {type(definition)} (耗时 {(__import__('time').time()-t0)*1000:.1f}ms)")
    
    # 总体内存使用
    print(f"\n[5] 总体内存使用:")
    import psutil
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    print(f"    RSS: {mem_info.rss / 1024 / 1024:.2f} MB")
    
    print(f"\n{'=' * 60}")


def compare_approaches():
    """对比不同方法的内存占用"""
    print("\n" + "=" * 60)
    print("内存对比测试")
    print("=" * 60)
    
    mdx_path = r"F:\code\查词分词\web2mdd\The little dict\TLD.mdx"
    
    from readmdict import MDX, MDD
    
    # 测试 MDX
    gc.collect()
    print(f"\n[1] MDX 类:")
    t0 = __import__('time').time()
    mdx = MDX(mdx_path, substyle=True)
    mdx_time = __import__('time').time() - t0
    mdx_mem = __import__('psutil').Process(os.getpid()).memory_info().rss / 1024 / 1024
    print(f"    加载耗时: {mdx_time:.1f}s")
    print(f"    当前 RSS: {mdx_mem:.0f} MB")
    print(f"    _key_list 条目: {len(mdx._key_list) if mdx._key_list else 0}")
    del mdx
    
    # 测试 MDD
    gc.collect()
    print(f"\n[2] MDD 类:")
    t0 = __import__('time').time()
    mdd = MDD(mdx_path)
    mdd_time = __import__('time').time() - t0
    mdd_mem = __import__('psutil').Process(os.getpid()).memory_info().rss / 1024 / 1024
    print(f"    加载耗时: {mdd_time:.1f}s")
    print(f"    当前 RSS: {mdd_mem:.0f} MB")
    del mdd
    
    # 对比
    print(f"\n[3] 对比:")
    print(f"    MDX 比 MDD 多占用: {mdx_mem - mdd_mem:.0f} MB")


if __name__ == "__main__":
    test_mdd()
    compare_approaches()