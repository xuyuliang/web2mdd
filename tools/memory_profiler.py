"""
内存分析脚本 - 诊断应用内存占用
"""
import os
import sys
import gc

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


def main():
    print("=" * 60)
    print("内存分析报告")
    print("=" * 60)
    
    # 强制垃圾回收
    gc.collect()
    
    print("\n[1/5] 加载 MDX 词典...")
    from app.main import mdx_reader
    
    # 分析 MDXReader 各属性的内存占用
    print("\n[2/5] 分析 MDXReader 属性内存占用:")
    print("-" * 40)
    
    attrs = {
        "key_offsets": mdx_reader.key_offsets,
        "key_lengths": mdx_reader.key_lengths,
        "word_to_idx": mdx_reader.word_to_idx,
        "lower_words": mdx_reader.lower_words,
        "block_infos": mdx_reader.block_infos,
        "block_starts": mdx_reader.block_starts,
    }
    
    total_size = 0
    for name, obj in attrs.items():
        size = get_size(obj)
        size_mb = size / 1024 / 1024
        total_size += size
        print(f"  {name:20s}: {size_mb:10.2f} MB")
    
    print(f"  {'总计':20s}: {total_size/1024/1024:10.2f} MB")
    
    print("\n[3/5] 检查缓存文件:")
    cache_path = r"F:\code\查词分词\web2mdd\The little dict\TLD.mdx.pkl"
    if os.path.exists(cache_path):
        cache_size = os.path.getsize(cache_path)
        print(f"  缓存文件大小: {cache_size / 1024 / 1024:.2f} MB")
    
    mdx_path = r"F:\code\查词分词\web2mdd\The little dict\TLD.mdx"
    if os.path.exists(mdx_path):
        mdx_size = os.path.getsize(mdx_path)
        print(f"  MDX文件大小: {mdx_size / 1024 / 1024:.2f} MB")
    
    print("\n[4/5] 加载其他数据:")
    from app.main import morphemes_loader, word_freq, related_words_searcher
    
    print("\n  MorphemesLoader:")
    print(f"    prefixes: {len(morphemes_loader.prefixes)} 条")
    print(f"    suffixes: {len(morphemes_loader.suffixes)} 条")
    print(f"    roots: {len(morphemes_loader.roots)} 条")
    
    print("\n  WordFreq:")
    print(f"    words: {len(word_freq.words)} 条")
    print(f"    rank_map: {len(word_freq.rank_map)} 条")
    
    print("\n  RelatedWordsSearcher:")
    print(f"    coca_word_set: {len(related_words_searcher.word_freq.word_set)} 条")
    
    print("\n[5/5] 总体内存使用:")
    import psutil
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    print(f"  RSS (常驻集大小): {mem_info.rss / 1024 / 1024:.2f} MB")
    print(f"  VMS (虚拟内存大小): {mem_info.vms / 1024 / 1024:.2f} MB")
    print(f"  RSS (MB): {mem_info.rss / 1024 / 1024:.2f}")
    
    print("\n" + "=" * 60)
    print("分析完成")
    print("=" * 60)


if __name__ == "__main__":
    main()