# System Patterns

## 整体架构

```
┌─────────────┐     HTMX 请求      ┌──────────────────┐
│  浏览器      │ ──────────────────>│  FastAPI 后端     │
│  (HTML+HTMX) │                   │  (app/main.py)   │
│              │ <──────────────────│                  │
└─────────────┘    HTML 片段       │  ┌──────────────┐│
                                    │  │ MDXReader    ││
                                    │  │ (词典读取器)  ││
                                    │  ├──────────────┤│
                                    │  │ AffixLoader  ││
                                    │  │ (词根词缀分析)││
                                    │  └──────────────┘│
                                    └──────────────────┘
```

- **API 风格**: 异步优先 (async/await)
- **模板引擎**: Jinja2（通过 FastAPI 的 `Jinja2Templates`）
- **数据流**: 前端通过 HTMX 请求后端 API，后端返回 HTML 片段（使用 Jinja2 片段模板）
- **前端交互**: HTMX 驱动的单页应用，无 JavaScript 框架

## 词典读取模式 (MDXReader)

- **启动时**: 读取 TLD.mdx 文件，构建单词索引（`word_to_idx` 字典）
- **缓存机制**: 索引构建完成后序列化为 pickle 文件（`.pkl`），后续启动直接从缓存加载（~30s -> ~2s）
- **查询方式**: 精确匹配（字典查找）-> 前缀匹配（二分查找 + 拼写建议）
- **记录读取**: 按需定位记录块 -> zlib/lzo 解压 -> 样式替换 -> 返回 HTML
- **词频提取**: 从结果 HTML 中正则提取 `<span class="rank">` 数字，取最小值

## 词根词缀分析模式 (AffixLoader)

- **数据源**: `_prefixes.txt`（149个前缀）和 `_suffixes.txt`（198个后缀），纯文本每行一个
- **匹配策略**: 
  - 前缀和后缀均按**长度降序**排列，优先匹配更长的
  - 前缀从单词开头匹配，后缀从单词结尾匹配
- **词干验证**: 
  - 支持 `is_valid_word` 回调函数，验证切分后的词干是否是词典中的有效单词
  - 可避免误切（如 "beautiful" 不被切掉 "be-" 剩下 "autiful"）
- **单字符后缀保护**: 对于单字符后缀（如 -a, -o, -y），如果原词本身是有效单词则不切分
  - 避免 "hello" 被切 "-o" 剩下 "hell"

## 请求处理流程

```
用户输入单词
    │
    ▼
GET /api/lookup?word=xxx
    │
    ├── 精确匹配? ──> 读取词典记录
    │   │               │
    │   │               ▼
    │   │         词根词缀分析 (AffixLoader.analyze)
    │   │               │
    │   │               ▼
    │   │         查询词干释义 (MDXReader.lookup)
    │   │               │
    │   │               ▼
    │   │         渲染 _lookup_result.html (词典内容 + 词根词缀分析)
    │   │
    └── 前缀匹配? ──> 渲染 _suggestions.html (拼写建议列表)
         │
         └── 无结果 ──> 渲染 _suggestions.html (空列表)
```

## 目录结构

```
/app
├── __init__.py
├── main.py          # FastAPI 应用 + MDXReader
├── affix_loader.py  # 词根词缀分析
└── test_dict.py     # 测试脚本

/static
└── style.css        # 页面样式

/templates
├── index.html       # 首页
└── partials/
    ├── _lookup_result.html   # 查词结果片段
    ├── _suggestions.html     # 拼写建议片段
    └── _affix_result.html    # 词根词缀分析片段

/ (根目录)
├── _prefixes.txt    # 前缀列表
├── _suffixes.txt    # 后缀列表
├── .clinerules
├── .gitignore
└── 使用方法.txt
```
