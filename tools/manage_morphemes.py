#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
morphemes.json 管理工具
功能：
  - 列出所有前缀、后缀、词根
  - 搜索词缀（按关键词、按 meaning）
  - 添加新的词缀条目
  - 保存修改到 morphemes.json
"""
import json
import os
import sys
from typing import Dict, List, Tuple, Optional

# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MORPHEMES_PATH = os.path.join(BASE_DIR, "数据资料", "morphemes.json")


class MorphemesManager:
    """管理 morphemes.json 数据的工具类"""

    def __init__(self, filepath: str = None):
        self.filepath = filepath or MORPHEMES_PATH
        self.data: Dict[str, dict] = {}
        self._load()

    def _load(self):
        """加载 morphemes.json"""
        if not os.path.exists(self.filepath):
            print(f"错误: 文件不存在 {self.filepath}")
            return
        with open(self.filepath, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        print(f"已加载 {len(self.data)} 个条目")

    def _save(self):
        """保存修改到 morphemes.json"""
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        print(f"已保存到 {self.filepath}")

    def get_all_parts(self) -> Tuple[List[Tuple[str, str, str, List]], List[Tuple[str, str, str, List]], List[Tuple[str, str, str, List]]]:
        """获取所有前缀、后缀、词根
        
        Returns:
            (prefixes, suffixes, roots) 每个元素是 (match_str, root, key, meaning)
        """
        prefixes = []
        suffixes = []
        roots = []

        for key, value in self.data.items():
            meaning = value.get("meaning", [])
            for form in value.get("forms", []):
                loc = form.get("loc", "")
                root = form.get("root", "")
                match_str = root.strip("-")
                if match_str and loc == "prefix":
                    prefixes.append((match_str, root, key, meaning))
                elif match_str and loc == "suffix":
                    suffixes.append((match_str, root, key, meaning))
                elif match_str and loc == "embedded":
                    roots.append((match_str, root, key, meaning))

        # 按长度降序
        prefixes.sort(key=lambda x: len(x[0]), reverse=True)
        suffixes.sort(key=lambda x: len(x[0]), reverse=True)
        roots.sort(key=lambda x: len(x[0]), reverse=True)

        return prefixes, suffixes, roots

    def search(self, keyword: str, part_type: str = "all") -> List[dict]:
        """搜索词缀
        
        Args:
            keyword: 搜索关键词（匹配 key 或 meaning）
            part_type: 类型过滤 - "prefix", "suffix", "root", "all"
        
        Returns:
            匹配结果列表
        """
        results = []
        keyword_lower = keyword.lower()

        prefixes, suffixes, roots = self.get_all_parts()

        def add_results(items, ptype):
            for match_str, root, key, meaning in items:
                if keyword_lower in key.lower() or keyword_lower in str(meaning).lower():
                    results.append({
                        "type": ptype,
                        "match_str": match_str,
                        "root": root,
                        "key": key,
                        "meaning": meaning
                    })

        if part_type == "all" or part_type == "prefix":
            add_results(prefixes, "prefix")
        if part_type == "all" or part_type == "suffix":
            add_results(suffixes, "suffix")
        if part_type == "all" or part_type == "root":
            add_results(roots, "root")

        return results

    def list_by_type(self, part_type: str = "all", limit: int = 100) -> List[dict]:
        """按类型列出词缀
        
        Args:
            part_type: "prefix", "suffix", "root", "all"
            limit: 最大显示数量
        """
        prefixes, suffixes, roots = self.get_all_parts()

        items = []
        if part_type == "all" or part_type == "prefix":
            items.extend([(m, r, k, mean, "prefix") for m, r, k, mean in prefixes])
        if part_type == "all" or part_type == "suffix":
            items.extend([(m, r, k, mean, "suffix") for m, r, k, mean in suffixes])
        if part_type == "all" or part_type == "root":
            items.extend([(m, r, k, mean, "root") for m, r, k, mean in roots])

        return [{"match_str": m, "root": r, "key": k, "meaning": mean, "type": t} for m, r, k, mean, t in items[:limit]]

    def add_entry(self, key: str, match_str: str, part_type: str, meaning: List[str],
                  origin: str = "", etymology: str = "", examples: List[str] = None):
        """添加新的词缀条目
        
        Args:
            key: 条目键名
            match_str: 匹配字符串（从 root 去除 "-" 后的值）
            part_type: 类型 - "prefix", "suffix", "embedded"
            meaning: 含义列表
            origin: 词源
            etymology: 词根词源
            examples: 示例单词列表
        """
        if part_type not in ("prefix", "suffix", "embedded"):
            print(f"错误: 无效的类型 '{part_type}'，必须是 prefix/suffix/embedded")
            return

        # 检查 key 是否已存在
        if key in self.data:
            print(f"警告: key '{key}' 已存在，将覆盖原有数据")

        # 构建 root
        if part_type == "embedded":
            root = f"-{match_str}-"
        elif part_type == "prefix":
            root = f"{match_str}-" if not match_str.startswith("-") else match_str
        else:  # suffix
            root = f"-{match_str}" if not match_str.startswith("-") else match_str

        entry = {
            "forms": [{
                "loc": part_type,
                "root": root,
                "form": match_str
            }],
            "meaning": meaning,
            "origin": origin,
            "etymology": etymology,
            "examples": examples or []
        }

        self.data[key] = entry
        print(f"已添加: key='{key}', type='{part_type}', match_str='{match_str}'")

    def check_duplicate_match_str(self, match_str: str, part_type: str, key_exclude: str = None) -> List[str]:
        """检查是否有多个 key 产生了相同的 match_str"""
        prefixes, suffixes, roots = self.get_all_parts()

        items = roots if part_type == "root" else (prefixes if part_type == "prefix" else suffixes)
        duplicates = []
        for m, r, k, mean in items:
            if m == match_str and k != key_exclude:
                duplicates.append(k)
        return duplicates


def print_table(rows, headers):
    """打印表格"""
    if not rows:
        print("  (无结果)")
        return
    # 计算列宽
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    # 打印表头
    header_line = "  ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    print(header_line)
    print("  ".join("-" * col_widths[i] for i in range(len(headers))))

    # 打印数据
    for row in rows:
        line = "  ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
        print(line)


def cmd_list(args):
    """处理 list 命令"""
    manager = MorphemesManager()
    part_type = args.get("type", "all")
    limit = int(args.get("limit", 100))

    items = manager.list_by_type(part_type, limit)
    print(f"\n{'='*60}")
    print(f"词缀列表 (类型: {part_type}, 共 {len(items)} 条)")
    print(f"{'='*60}")

    rows = [(i+1, item["type"], item["match_str"], item["key"], ", ".join(item["meaning"])) for i, item in enumerate(items)]
    print_table(rows, ["#", "类型", "匹配串", "key", "含义"])


def cmd_search(args):
    """处理 search 命令"""
    manager = MorphemesManager()
    keyword = " ".join(args.get("keyword", []))
    part_type = args.get("type", "all")

    if not keyword:
        print("用法: search <关键词> [--type prefix|suffix|root|all]")
        return

    results = manager.search(keyword, part_type)
    print(f"\n{'='*60}")
    print(f"搜索结果: '{keyword}' (类型: {part_type})")
    print(f"找到 {len(results)} 条匹配")
    print(f"{'='*60}")

    rows = [(i+1, r["type"], r["match_str"], r["key"], ", ".join(r["meaning"])) for i, r in enumerate(results)]
    print_table(rows, ["#", "类型", "匹配串", "key", "含义"])


def cmd_add(args):
    """处理 add 命令"""
    manager = MorphemesManager()

    key = args.get("key", args.get("KEY", ""))
    match_str = args.get("match", args.get("MATCH", ""))
    ptype = args.get("type", args.get("TYPE", ""))
    meaning = args.get("meaning", "").split(",") if args.get("meaning") else []
    origin = args.get("origin", "")
    etymology = args.get("etymology", "")
    examples = args.get("examples", "").split(",") if args.get("examples") else []

    if not key or not match_str or not ptype:
        print("用法: add --key <键名> --match <匹配串> --type <prefix|suffix|embedded> --meaning <含义1,含义2>")
        print("       [--origin <词源>] [--etymology <词根词源>] [--examples <例1,例2>]")
        return

    # 检查重复
    duplicates = manager.check_duplicate_match_str(match_str, ptype, key)
    if duplicates:
        print(f"注意: '{match_str}' 还来自以下 key: {', '.join(duplicates)}")

    manager.add_entry(key, match_str, ptype, meaning, origin, etymology, examples)
    manager._save()


def cmd_interactive(args):
    """交互式添加"""
    manager = MorphemesManager()

    print("\n交互式添加词缀")
    print("输入空值跳过使用默认值")
    print("-" * 40)

    key = input("条目键名 (key): ").strip()
    if not key:
        print("key 不能为空")
        return

    match_str = input("匹配字符串 (match): ").strip()
    if not match_str:
        print("match 不能为空")
        return

    print("类型: prefix (前缀) / suffix (后缀) / embedded (嵌入词根)")
    ptype = input("类型 (type): ").strip().lower()
    if ptype not in ("prefix", "suffix", "embedded"):
        print("无效类型")
        return

    meaning_input = input("含义 (用逗号分隔): ").strip()
    meaning = [m.strip() for m in meaning_input.split(",") if m.strip()] if meaning_input else []

    origin = input("词源 (origin, 可选): ").strip()
    etymology = input("词根词源 (etymology, 可选): ").strip()
    examples_input = input("示例单词 (用逗号分隔, 可选): ").strip()
    examples = [e.strip() for e in examples_input.split(",") if e.strip()] if examples_input else []

    manager.add_entry(key, match_str, ptype, meaning, origin, etymology, examples)
    manager._save()

    print("\n添加完成！")


def print_usage():
    """打印使用说明"""
    print("""
morphemes.json 管理工具

用法: python manage_morphemes.py <命令> [参数]

命令:
  list [选项]                    列出词缀
    --type <prefix|suffix|root|all>  按类型过滤 (默认: all)
    --limit <数量>                   显示数量限制 (默认: 100)

  search <关键词> [选项]         搜索词缀
    --type <prefix|suffix|root|all>  按类型过滤 (默认: all)

  add [选项]                     添加新词缀 (非交互式)
    --key <键名>
    --match <匹配串>
    --type <prefix|suffix|embedded>
    --meaning <含义1,含义2,...>
    --origin <词源>
    --etymology <词根词源>
    --examples <例1,例2,...>

  interactive                    交互式添加词缀

示例:
  python manage_morphemes.py list --type suffix --limit 10
  python manage_morphemes.py search age --type suffix
  python manage_morphemes.py add --key cleav --match cleav --type embedded --meaning "cleave,split" --origin "Old English" --examples "cleavage,cleave,clove,cloven"
""")


def parse_args(args):
    """解析命令行参数"""
    parsed = {"keyword": []}
    current_key = None
    current_value = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            # 保存上一个键值对
            if current_key:
                parsed[current_key] = " ".join(current_value) if len(current_value) > 1 else current_value[0] if current_value else ""
            current_key = arg[2:]
            current_value = []
        elif current_key:
            current_value.append(arg)
        else:
            # 位置参数（作为 keyword）
            if "keyword" not in parsed:
                parsed["keyword"] = []
            parsed["keyword"].append(arg)
        i += 1

    # 保存最后一个键值对
    if current_key:
        parsed[current_key] = " ".join(current_value) if len(current_value) > 1 else current_value[0] if current_value else ""

    return parsed


def main():
    if len(sys.argv) < 2:
        print_usage()
        return

    command = sys.argv[1]
    args = parse_args(sys.argv[2:])

    if command == "list":
        cmd_list(args)
    elif command == "search":
        cmd_search(args)
    elif command == "add":
        cmd_add(args)
    elif command == "interactive":
        cmd_interactive(args)
    elif command in ("-h", "--help"):
        print_usage()
    else:
        print(f"未知命令: {command}")
        print_usage()


if __name__ == "__main__":
    main()